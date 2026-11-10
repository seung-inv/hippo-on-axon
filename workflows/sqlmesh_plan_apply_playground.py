"""Plan the anusha_playground SQLMesh project, wait for human approval, then apply or reject.

compute_plan -> plan_approval (Pause) -> apply_plan if approved == true,
otherwise reject_plan. The engine, not an agent, evaluates the edge. A person
reviews diff_summary and resumes the Pause with approved = true or false;
apply_plan re-plans and applies only if the plan fingerprint still matches.

Usage:
    uv run axon deploy sqlmesh_plan_apply_playground -n hippo-playground
    uv run axon run sqlmesh_plan_apply_playground -n hippo-playground
    # resume the Pause: client.execution.resume_paused_step(execution_id, step_id,
    #     [FlowExecutionVariableInput(variable_name="approved", variable_type="Boolean", variable_value="true")])

Re-deploy after changing project files to refresh the embedded snapshots.
"""

from __future__ import annotations

from pathlib import Path

from axon.lib import Edge, Pause, Step, Variable, Workflow
from workflows.delegates.sqlmesh_apply_plan_playground import run_sqlmesh_apply_plan_playground
from workflows.delegates.sqlmesh_compute_plan_playground import run_sqlmesh_compute_plan_playground
from workflows.delegates.sqlmesh_reject_plan import run_sqlmesh_reject_plan


project = Path(__file__).resolve().parents[1] / "hdm-anusha_playground/tenants/anusha_playground/sqlmesh"
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
runner_source = (Path(__file__).resolve().parent / "delegates/sqlmesh_plan_runner.py").read_text(encoding="utf-8")


def with_snapshots(wrapper):
    """Copy a delegate with the project and runner snapshots appended to its shipped source.

    The snapshots become part of main.py and its package hash, so asset changes
    trigger a redeploy just like Python source changes.
    """
    copied = wrapper.delegate.model_copy(deep=True)
    copied.code = f"{copied.code}\nPROJECT_FILES = {project_files!r}\nRUNNER_SOURCE = {runner_source!r}\n"
    return copied


compute_delegate = with_snapshots(run_sqlmesh_compute_plan_playground)
apply_delegate = with_snapshots(run_sqlmesh_apply_plan_playground)

plan_approval = Pause(
    name="sqlmesh_plan_approval",
    description="A human reviews diff_summary and resumes with approved = true to apply, or false to reject.",
    outputs=[Variable(name="approved", type="Boolean")],
)

secret_names = [variable.name for variable in compute_delegate.inputs if variable.type == "Secret"]
DEFAULT_INPUT = {"environment": "prod", **{name: name for name in secret_names}}

workflow = Workflow(
    name="Sqlmesh_Plan_Apply_Playground",
    description="Plan the anusha_playground SQLMesh project, wait for human approval, then apply or reject it.",
    steps=[
        Step(name="compute_plan", entity=compute_delegate),
        Step(
            name="plan_approval",
            entity=plan_approval,
            edges=[
                Edge(
                    to="apply_plan",
                    condition={"==": [{"var": "approved"}, True]},
                    description="approved",
                    priority=1,
                ),
                Edge(to="reject_plan", description="not approved or ambiguous", priority=10),
            ],
        ),
        Step(name="apply_plan", entity=apply_delegate, edges=[]),
        Step(name="reject_plan", entity=run_sqlmesh_reject_plan),
    ],
    inputs=[
        Variable(
            name="environment",
            type="String",
            direction="Input",
            description="SQLMesh environment to plan, e.g. dev_axon or prod",
        ),
        *(Variable(name=name, type="Secret", direction="Input") for name in secret_names),
    ],
    outputs=[
        Variable(name="applied", type="Boolean", direction="Output"),
        Variable(name="message", type="String", direction="Output"),
    ],
)
