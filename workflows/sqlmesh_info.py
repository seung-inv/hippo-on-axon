"""Check TPCH connections with a single SQLMesh delegate.

Usage:
    uv run axon deploy sqlmesh_info -n default
    uv run axon run sqlmesh_info -n default --wait

Re-deploy after changing project files to refresh the embedded snapshot.
"""

from __future__ import annotations

from pathlib import Path

from axon.lib import Variable, Workflow
from workflows.delegates.sqlmesh_info import run_sqlmesh_info


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
info_delegate = run_sqlmesh_info.delegate.model_copy(deep=True)
info_delegate.code = f"{info_delegate.code}\nPROJECT_FILES = {project_files!r}\n"

DEFAULT_INPUT = {variable.name: variable.name for variable in info_delegate.inputs}

workflow = Workflow(
    name="Sqlmesh_Info",
    description="Run SQLMesh info on the TPCH project with Axon-managed secrets.",
    steps=[info_delegate],
    inputs=[Variable(name=name, type="Secret", direction="Input") for name in DEFAULT_INPUT],
    outputs=[Variable(name="sqlmesh_output", type="String", direction="Output")],
)
