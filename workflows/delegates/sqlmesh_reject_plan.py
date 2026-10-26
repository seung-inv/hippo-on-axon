"""Record that a SQLMesh plan was not approved."""

from __future__ import annotations

from axon.lib import Context, Variable, delegate


@delegate(
    description="Record that a SQLMesh plan was not approved. Changes nothing.",
    outputs=[Variable(name="applied", type="Boolean"), Variable(name="message", type="String")],
)
def run_sqlmesh_reject_plan(context: Context, plan_fingerprint: str) -> dict:
    """Return applied = false so the workflow ends with an explicit outcome."""
    message = f"Plan {plan_fingerprint} was not approved; nothing was applied."
    context.status_message(message)
    context.save_variable("applied", False)
    context.save_variable("message", message)
    return {"applied": False, "message": message}
