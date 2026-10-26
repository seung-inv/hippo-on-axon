"""Compute or apply a SQLMesh plan; run as a subprocess by the plan delegates.

Not an Axon module: workflows/sqlmesh_plan_apply.py embeds this file's source
in the compute and apply delegates, which write it to disk and run it with the
delegate venv's Python (see axon_learning_notes.md, "Running a Package's CLI
from a Delegate"). The project's config.yaml reads connections from env vars
the delegate sets.

Usage:
    python sqlmesh_plan_runner.py compute <project> <environment>
    python sqlmesh_plan_runner.py apply <project> <environment> <plan_fingerprint>

An empty <environment> uses the project's default_target_environment.
The last stdout line is ``RESULT_MARKER`` followed by a JSON result.
"""

from __future__ import annotations

import hashlib
import json
import sys

RESULT_MARKER = "SQLMESH_PLAN_RESULT="


def summarize(environment: str, plan) -> dict:
    """Describe a plan's changes plus a fingerprint identifying exactly those changes."""
    if plan is None or not plan.has_changes:
        summary = {"added": [], "modified": [], "downstream": [], "removed": []}
    else:
        diff = plan.context_diff
        added = {snapshot_id.name for snapshot_id in diff.added}
        # SQLMesh also counts a model new to the environment as directly modified.
        directly = {snapshot_id.name for snapshot_id in plan.directly_modified} - added
        summary = {
            "added": sorted(added),
            "modified": sorted(directly),
            "downstream": sorted(set(diff.modified_snapshots) - directly - added),
            "removed": sorted(snapshot_id.name for snapshot_id in diff.removed_snapshots),
        }
    snapshots = [] if plan is None else sorted(s.snapshot_id.identifier for s in plan.new_snapshots)
    fingerprint_source = json.dumps({"environment": environment, **summary, "snapshots": snapshots})
    summary["environment"] = environment
    summary["has_changes"] = any(summary[key] for key in ("added", "modified", "downstream", "removed"))
    summary["plan_fingerprint"] = hashlib.sha256(fingerprint_source.encode()).hexdigest()[:16]
    return summary


def diff_text(summary: dict) -> str:
    if not summary["has_changes"]:
        return f"No changes to apply in `{summary['environment']}`."
    lines = [f"Plan for `{summary['environment']}` (fingerprint {summary['plan_fingerprint']}):"]
    for label in ("added", "modified", "downstream", "removed"):
        lines += [f"  {label}: {name}" for name in summary[label]]
    return "\n".join(lines)


def main(argv: list[str]) -> dict:
    from sqlmesh import Context
    from sqlmesh.utils.errors import NoChangesPlanError

    action, project, environment = argv[0], argv[1], argv[2]
    context = Context(paths=project)
    environment = environment or context.config.default_target_environment
    try:
        plan = context.plan_builder(environment, skip_tests=True).build()
    except NoChangesPlanError:
        plan = None
    summary = summarize(environment, plan)

    if action == "compute":
        return {**summary, "diff_summary": diff_text(summary)}

    approved = argv[3]
    if summary["plan_fingerprint"] != approved:
        message = (
            f"Not applied: the plan changed after approval "
            f"(approved {approved}, current {summary['plan_fingerprint']}). Re-run the plan."
        )
        return {"applied": False, "message": message}
    if plan is None or not summary["has_changes"]:
        return {"applied": False, "message": f"Nothing to apply in `{environment}`."}
    context.apply(plan)
    return {"applied": True, "message": f"Applied plan {approved} to `{environment}`."}


if __name__ == "__main__":
    print(RESULT_MARKER + json.dumps(main(sys.argv[1:])))
