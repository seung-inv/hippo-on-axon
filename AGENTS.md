# Agent Instruction

In this project, we are going to build Axon workflows that run sqlmesh commands such as `plan` and `run`.

Check out `axon_learning_notes.md`, in which I accumulate my knowledge on Axon.

## Running the Axon CLI

Run `axon` commands through `scripts/axon_pat.sh` instead of calling `axon` directly:

```sh
scripts/axon_pat.sh deploy sqlmesh_info -n default
scripts/axon_pat.sh run sqlmesh_info -n default --wait --json
```

- `AXON_API_KEY` in `.env` holds a personal access token (PAT) for the `api` use case.
  The platform does not accept such a PAT as a direct Bearer token; it must first be exchanged at `/v1/pat/exchange` for a short-lived token.
  SDK 1.3.0 does not perform this exchange, so plain `axon` commands fail with HTTP 401 (`revocation_check_failed` on pr5866).
- The script performs the exchange (1-hour token, retrying on transient `503 pool_saturated`) and runs `axon` with the exchanged token as `AXON_API_KEY`, overriding `.env` for that command only.
- The token is scoped to namespace `default`; set `AXON_PAT_NAMESPACE` to use another namespace.
- Writing secrets with an exchanged token has not been tested.
  If it is rejected, fall back to the Playwright browser-login procedure in `docs/sqlmesh_info_delegate.md`.
- Never print or log the PAT or the exchanged token.

## Axon SDK Source Repo

This project depends on the Axon SDK (`invisible-tech-axon-sdk`, imported as `axon`).
The SDK source, user guide, and examples live in a sibling repo: `~/repos/_axon/agentic-core`.
It is a large platform monorepo (backend, frontend, infra, etc.), so go straight to the paths below instead of exploring it broadly.
Treat it as read-only reference material unless I ask you to change it.

### Version Matching

- This project pins the SDK in `pyproject.toml`; the installed version is in `.venv/lib/python*/site-packages/invisible_tech_axon_sdk-*.dist-info`.
- `agentic-core` may be checked out at a newer commit than the installed version.
  Releases are tagged `sdk-vX.Y.Z` (e.g., `sdk-v1.3.0`).
  When behavior matters, compare against the matching tag (`git -C ~/repos/_axon/agentic-core show sdk-v1.3.0:<path>`) or read the installed package under `.venv/lib/python*/site-packages/axon/`.

### SDK Source — `backend/packages/sdk/`

| Path | Contents |
|---|---|
| `README.md`, `CLAUDE.md` | SDK overview and package-internal constraints |
| `CHANGELOG.md` | Release history |
| `src/axon/agent_context/WHATS_NEW.md` | FDE-facing new capabilities per release |
| `src/axon/lib/dsl/` | Workflow-authoring DSL: `workflow.py`, `step.py`, `agent.py`, `team.py`, `team_skill.py`, `delegate.py`, `tool.py`, `loop.py`, `map.py`, `pause.py`, `graph.py`, `output_type.py`, `validation.py` |
| `src/axon/lib/client/` | Platform API client (flows, executions, delegates, teams, tools, secrets, files, MCP, namespaces, etc.) |
| `src/axon/lib/client/graphql/` | Bundled GraphQL queries and mutations |
| `src/axon/lib/platform/` | Runtime helpers used from delegate code (auth, execution, files, MCP, records) |
| `src/axon/lib/testing/` | `axon test` support (`expect.py`, `judge.py`, `run.py`) |
| `src/axon/lib/project/`, `src/axon/lib/settings.py` | Project config (`[tool.axon]`) and settings |
| `src/axon/cli/` | `axon` CLI commands, one module per command (`deploy.py`, `run.py`, `logs.py`, `inspect.py`, `init.py`, `doctor.py`, ...) |
| `src/axon/cli/templates/project/` | Copier template used by `axon init` (this project was generated from it) |
| `src/axon/skills/` | Source of the bundled agent skills copied into `.agents/skills/` and `.claude/skills/` here |
| `examples/` | SDK examples (e.g., `pause_resume_demo.py`) |
| `tests/unit/` | SDK unit tests — useful as usage examples |

### User Guide — `user-docs/` (Sphinx RST)

| Path | Contents |
|---|---|
| `sdk/getting-started/` | Install, first workflow, deploy and run |
| `sdk/concepts/` | Tenant vs. namespace, testing concepts |
| `sdk/guides/` | Task guides: workflows, teams, tools and delegates, functions, loops, maps, subflows, files and variables, secrets, MCP servers, conversations, long-term memory, packages, deploy, debugging, testing, performance testing |
| `sdk/reference/` | Builder API, executions, GraphQL schema, testing reference |
| `guide/` | Platform (UI) user guide: agentic teams, connectors, MCP, skills, structured outputs, conditional edges, map-reduce, etc. |
| `examples/` | `axon_client.py`, `run_workflow_example.py` |
| `quickstart.rst`, `api-integration.rst`, `common-issues.rst` | Top-level guides and troubleshooting |

### Other Useful Locations

- `schemas/graphql/` — the platform's GraphQL schema (source of truth for the API surface).
- `examples/` (repo root) — platform API examples (flow execution, WebSocket monitoring).

### Search Tips

- Use `rg` with an explicit path to stay out of unrelated directories, e.g., `rg "def map" ~/repos/_axon/agentic-core/backend/packages/sdk/src`.
- Skip build output and generated files: `user-docs/_build/`, `user-docs/_generated/`.
- Prefer the user guide for intended usage and the SDK source for exact signatures and behavior.
