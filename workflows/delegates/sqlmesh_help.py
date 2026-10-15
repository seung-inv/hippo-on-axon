"""Delegate that runs `sqlmesh --help` on the platform.

This module must contain exactly one delegate and nothing else at module
level that depends on `axon.lib`. The SDK treats a module with a single
`@delegate` as a "dedicated entity module" and ships its entire source,
with `from axon.lib` imports stripped. Any module-level `Workflow(...)`
here would then fail on the platform with `NameError`.
"""

from __future__ import annotations

from axon.lib import Context, Variable, delegate


# Notes on the delegate below:
# - The venv's `bin/` is not on PATH, and `sqlmesh.cli.main` has no
#   `__main__` guard, so the CLI is invoked via `sys.executable -c`.
# - File descriptor 1 is the JSON protocol pipe to the engine, so the child
#   must never inherit stdout or stdin: always capture output and feed an
#   empty stdin via `input=""`. `subprocess.DEVNULL` does not work because
#   the sandbox has no `/dev`.
# - The platform clears the environment, so telemetry must be disabled
#   explicitly in the child's env.
@delegate(
    description="Run `sqlmesh --help` to verify sqlmesh works on the platform.",
    outputs=[Variable(name="sqlmesh_output", type="String")],
    dependencies=["sqlmesh[databricks,duckdb]==0.236.3"],
)
def run_sqlmesh(context: Context) -> dict:
    """Run `sqlmesh --help` in a subprocess and capture its output."""
    import os
    import subprocess
    import sys

    env = {**os.environ, "SQLMESH__DISABLE_ANONYMIZED_ANALYTICS": "1"}
    result = subprocess.run(
        [sys.executable, "-c", "from sqlmesh.cli.main import cli; cli()", "--help"],
        capture_output=True,
        input="",
        text=True,
        env=env,
        timeout=600,
    )
    output = f"exit={result.returncode}\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    context.save_variable("sqlmesh_output", output)
    if result.returncode != 0:
        raise RuntimeError(f"SQLMesh smoke test failed:\n{output}")
    return {"sqlmesh_output": output}
