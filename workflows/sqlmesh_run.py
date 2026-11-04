"""Run `sqlmesh run` on the TPCH project: the Axon replacement for the nightly
GitHub Actions *SQLMesh Run* job (cron 15 5 * * *).

Usage:
    uv run axon deploy sqlmesh_run -n default
    uv run axon run sqlmesh_run -n default --wait

Nightly schedule: create it once with the Axon `createSchedule` mutation, e.g.
    schedule_kind: Cron, cron_expr: "15 5 * * *", timezone: UTC,
    target_operation_name: executeFlow, misfire_policy: FireOnceNow,
    max_concurrent_runs: 1,
    target_variables: {flow: Sqlmesh_Run, environment: prod, <secret inputs>}
Check the exact target_variables shape with `validateScheduleTarget` first.

Re-deploy after changing project files to refresh the embedded snapshot.
"""

from __future__ import annotations

from pathlib import Path

from axon.lib import Variable, Workflow
from workflows.delegates.sqlmesh_run import run_sqlmesh_run


project = Path(__file__).resolve().parents[1] / "hdm-tpch/tenants/tpch/sqlmesh"
project_files = {"config.yaml": (project / "config.yaml").read_text(encoding="utf-8")}
for folder in ("models", "macros", "audits", "seeds", "tests"):
    for path in sorted((project / folder).rglob("*")):
        relative = path.relative_to(project)
        if (
            path.is_file()
            and not any(part.startswith(".") or part == "__pycache__" for part in relative.parts)
            and path.suffix != ".pyc"
        ):
            project_files[relative.as_posix()] = path.read_text(encoding="utf-8")

# The snapshot becomes part of main.py and its package hash, so asset changes
# trigger a redeploy just like Python source changes.
run_delegate = run_sqlmesh_run.delegate.model_copy(deep=True)
run_delegate.code = f"{run_delegate.code}\nPROJECT_FILES = {project_files!r}\n"

secret_names = [variable.name for variable in run_delegate.inputs if variable.type == "Secret"]
DEFAULT_INPUT = {"environment": "dev_axon", **{name: name for name in secret_names}}

workflow = Workflow(
    name="Sqlmesh_Run",
    description="Run `sqlmesh run` on the TPCH project to process new and missing intervals.",
    steps=[run_delegate],
    inputs=[
        Variable(
            name="environment",
            type="String",
            direction="Input",
            description="SQLMesh environment to run, e.g. prod (nightly) or dev_axon",
        ),
        *(Variable(name=name, type="Secret", direction="Input") for name in secret_names),
    ],
    outputs=[Variable(name="sqlmesh_output", type="String", direction="Output")],
)
