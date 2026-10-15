# Axon Learning Notes

## Axon Components

Based on SDK v1.3.0 (`.venv/lib/python*/site-packages/axon/lib/dsl/`).

```
Tenant
└── Namespace                      (deploy target; entity names must be unique here)
    └── Workflow                   name, inputs, outputs, steps[]
        └── Step                   runs one of the entities below; inputs{} mapping, edges[]
            ├── Delegate           fixed code: def main(context, ...) → output variables
            ├── Team               goal, agents[], termination, max_turns, team_skills[]
            │   └── Agent          persona, model, tools[], mcp_servers[], output_type
            │       └── Tool       function the agent decides to call
            ├── Workflow           (subflow, so the tree can recurse)
            ├── Map                iterator: Delegate → entity: Team|Workflow (in parallel)
            │                      → reduce: Delegate (optional)
            └── Loop               entity: Team|Delegate|Workflow, repeats while `variable`
                                   is truthy, up to max_iterations
```

- **Workflow → Step:** `steps` is an ordered list.
  Bare entities are auto-wrapped in a `Step`; use an explicit `Step(...)` only for input mapping or conditional `Edge`s.
  Without edges, steps run in list order.
- **Delegate vs. Tool:** a delegate is a fixed workflow step (no LLM); a tool is a function an agent chooses to call while reasoning.
- **Team → Agent:** the first agent must be a `speaker_selector` (`Agent.speaker_selector()`).
  Agents converse until a termination pattern matches or `max_turns` is reached.
- **Data flow:** steps read and write named variables in a shared workflow context rather than passing data directly.
- **Cross-cutting resources:**
  - MCP servers attach to Agents, Tools, and Delegates.
  - Packages (`file`) attach to Tools and Delegates.
  - Secrets, long-term memory, and conversations are reached from delegate or tool code via `context`.

### Delegate Constraints

- The platform runs Python 3.11, so avoid 3.12+ syntax.
- Delegates run as sync `def main(context, ...)`; `async def` is wrapped at deploy time.
- Don't call `asyncio.run()` (the event loop is already running); use `axon.lib.utils.run_async`.
- Outputs must be declared explicitly, and the returned dict's keys must match them.

## Delegate Dependencies (Third-Party Packages)

Verified on prod with SDK v1.3.0 by running `sqlmesh --help` in a delegate (`workflows/delegates/sqlmesh_help.py`).

### Declaring Dependencies

```python
@delegate(
    description="...",
    outputs=[Variable(name="sqlmesh_output", type="String")],
    dependencies=["sqlmesh[databricks,duckdb]==0.236.3"],
)
def run_sqlmesh(context: Context) -> dict: ...
```

- Declare pip requirements with `dependencies=[...]` on `@delegate`.
  Any PEP 508 spec works, including extras and version pins.
- The project's own `pyproject.toml` does not matter: it only affects the local venv, not the platform.
- Pin the version so the platform runs the same version you tested locally.

### What Happens at Deploy and Run Time

1. **Deploy** (`axon/lib/package_builder.py`): a non-empty `dependencies` list always makes the SDK build a package zip with `main.py`, any bundled local modules, and a generated `pyproject.toml`.
   That file has `requires-python = ">=3.11,<3.12"`, the dependencies, and `[invisible] main = "./main.py"`.
   The zip goes to the Files API, and the delegate's `file` field points to it.
2. **Run** (platform `subprocess_manager.py`): each execution creates a fresh venv (`uv venv /tmp/venv`), installs the package with `uv pip install -e` (resolving from PyPI), then runs `main` with `/tmp/venv/bin/python`.
   - Nothing is cached between runs unless the platform's `PYTHON_MODULE_CACHING` flag is on, so the install is repeated every time.
   - In practice `sqlmesh[databricks,duckdb]` installed and ran in about 15 s total.

### Auto-Detection Is Limited — Be Explicit

- The SDK scans **only top-level imports** (`top_level_only=True`); imports inside the function body are ignored.
- Third-party imports alone do **not** trigger packaging.
  Only local (project) imports or explicit `dependencies` do.
  So `import requests` without `dependencies=["requests"]` may fail on the platform with `ModuleNotFoundError`.
- A module that is only reached via a subprocess (e.g., `sqlmesh` invoked as a CLI) is invisible to the scan, so `dependencies` is the only way to install it.

### Running a Package's CLI from a Delegate

```python
result = subprocess.run(
    [sys.executable, "-c", "from sqlmesh.cli.main import cli; cli()", "--help"],
    capture_output=True, input="", text=True, timeout=600,
    env={**os.environ, "SQLMESH__DISABLE_ANONYMIZED_ANALYTICS": "1"},
)
```

- **Console scripts are not on `PATH`.**
  They install to `/tmp/venv/bin`, which isn't on the delegate's `PATH`, so `["sqlmesh", ...]` fails.
  Use `sys.executable` (the venv's Python) to call the CLI entry point.
  Find the entry point in the package's `*.dist-info/entry_points.txt` (`sqlmesh = sqlmesh.cli.main:cli`).
  `python -m sqlmesh.cli.main` does not work because that module has no `__main__` guard.
- **Always capture stdout and feed stdin.**
  File descriptor 1 is the JSON protocol pipe to the engine, so a child that inherits stdout or stdin can corrupt it.
- **`subprocess.DEVNULL` fails** with `FileNotFoundError: '/dev/null'`: the sandbox has no `/dev`.
  Use `input=""` instead.
- **The environment is cleared.**
  Pass any env vars the child needs (config values, telemetry opt-outs) explicitly through `env=`.

### Gotchas

- **Single-delegate modules ship whole.**
  If a file contains exactly one `@delegate(`/`@tool(` and a `from axon.lib` import, the SDK treats it as a "dedicated entity module".
  It ships the **entire file** with the `from axon.lib` lines stripped.
  A `Workflow(...)` in the same file then fails on the platform with `NameError: name 'Workflow' is not defined`.
  Fix: put such a delegate in its own module (e.g., `workflows/delegates/`) and import it from the workflow file.
  To preview the code that will be shipped, print `run_sqlmesh.code` (the decorated function's `.code`).
- **Deploy can skip dependency changes.**
  `axon deploy` decides whether a delegate changed by comparing only code, description, type, and variables (`axon/cli/deploy.py:65`).
  Changing just `dependencies` prints "Skipping delegate (unchanged)".
  Touch the code or description to force a redeploy.
- **Resource limits.**
  Worker pods default to 1 CPU and 1 GiB of memory, with about 29.5 minutes per task (chart defaults; prod may differ).
  The per-run install counts against that budget.

## Deploying, Running, and Checking Results

Verified on prod with SDK v1.3.0.

### Deploy and Run

```sh
uv run axon graph  sqlmesh_smoke                  # preview the flow (no deploy)
uv run axon deploy sqlmesh_smoke -n default
uv run axon run    sqlmesh_smoke -n default --wait
```

- The workflow name passed to these commands is the module name under `workflow_dir` (`workflows/sqlmesh_smoke.py`).
- `--wait` blocks until the run finishes and prints the execution ID, the workflow outputs, and a link to the run in the UI.
  On failure, it prints the reason and a stack trace instead.

### Finding an Execution ID

```sh
uv run axon executions list -f Sqlmesh -l 5       # filter by flow name (substring)
uv run axon executions list -s failed --since 24h
```

- The list includes a truncated error message for each failed run.

### Checking the Output

| Command | What it shows |
|---|---|
| `axon inspect <ID> --step 1` | **Best for outputs.** A step's input and output variables, with multi-line strings printed with real line breaks. |
| `axon inspect <ID>` | Overview: steps timeline, durations, tokens. For a failed run: the failed step, stack trace, and variable state. |
| `axon inspect <ID> --json` | Machine-readable version (`execution`, `steps`, `summary`). |
| `axon status <ID>` | Only status and start/end times (`-w` polls until done). |
| `axon logs <ID> -v` | Step summary; output is truncated even with `-v`. `-s` streams live while running. |

To extract a single output value in a script:

```sh
uv run axon inspect <ID> --json \
  | jq -r '.steps[0].output_variables | fromjson | .sqlmesh_output.value'
```

- `.steps[].output_variables` is a JSON **string**, so it needs `fromjson`.
  Each variable is an object with a `value` key.
- `axon inspect <ID> --variables` printed "No variables found" for a run that did have outputs.
  Use `--step N` instead.
- In the browser: `https://prod.agentic.inv.tech/namespaces/<ns>/history/<ID>`.

### Iterating on Failures

- Each fix is deploy → run → inspect.
  The failure reason from `--wait` or `axon inspect <ID>` is usually enough to pinpoint the problem.
- Errors during module load (e.g., `NameError` at top level) surface as `CompileError: compile_error`.
  Errors inside `main` surface as `RuntimeExceptionFailure: runtime_exception`, with the delegate's traceback (`File "<delegate>", line N`).
