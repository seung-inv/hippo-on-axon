"""SQLMesh smoke test.

A single Delegate that runs `sqlmesh --help` on the platform to verify that
sqlmesh installs and executes inside a delegate.

Usage:
    uv run axon deploy sqlmesh_smoke -n <your-namespace>
    uv run axon run    sqlmesh_smoke -n <your-namespace> --wait
"""

from __future__ import annotations

from axon.lib import Variable, Workflow
from workflows.delegates.sqlmesh_help import run_sqlmesh

workflow = Workflow(
    name="Sqlmesh_Smoke",
    description="Run sqlmesh --help inside a delegate.",
    steps=[run_sqlmesh],
    outputs=[Variable(name="sqlmesh_output", type="String", direction="Output")],
)
