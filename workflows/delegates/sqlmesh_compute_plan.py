"""Compute a SQLMesh plan for a project snapshot supplied at deployment."""

from __future__ import annotations

from axon.lib import Context, Variable, delegate
from axon.lib.dsl.types import SecretStr


# workflows/sqlmesh_plan_apply.py appends both snapshots to the shipped source.
PROJECT_FILES: dict[str, str] = {}
RUNNER_SOURCE = ""


@delegate(
    description="Compute a SQLMesh plan for the TPCH project and summarize the changes for approval (SQLMesh 0.231.1).",
    outputs=[
        Variable(name="plan_fingerprint", type="String"),
        Variable(name="diff_summary", type="String"),
        Variable(name="has_changes", type="Boolean"),
    ],
    dependencies=[
        # Matches the shared TPCH state DB (SQLMesh refuses to plan against older
        # state; sqlmesh_info does not check). Bump with `sqlmesh migrate`.
        "sqlmesh[databricks,duckdb]==0.231.1",
        "databricks-sdk==0.154.0",
        "psycopg2-binary==2.9.13",
    ],
)
def run_sqlmesh_compute_plan(
    context: Context,
    environment: str,
    DBR_RESEARCH_HOST: SecretStr,
    DBR_RESEARCH_HTTP_PATH: SecretStr,
    DBR_HDM_TPCH_OAUTH_ID: SecretStr,
    DBR_HDM_TPCH_OAUTH_SECRET: SecretStr,
    PG_SM_STATE_HOST: SecretStr,
    PG_SM_STATE_PORT: SecretStr,
    PG_SM_STATE_TPCH_DB: SecretStr,
    PG_SM_STATE_TPCH_USER: SecretStr,
    PG_SM_STATE_TPCH_PASSWORD: SecretStr,
) -> dict:
    """Run the plan runner in a subprocess and return its plan summary."""
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys

    settings = {
        "DBR_RESEARCH_HOST": DBR_RESEARCH_HOST,
        "DBR_RESEARCH_HTTP_PATH": DBR_RESEARCH_HTTP_PATH,
        "DBR_HDM_TPCH_OAUTH_ID": DBR_HDM_TPCH_OAUTH_ID,
        "DBR_HDM_TPCH_OAUTH_SECRET": DBR_HDM_TPCH_OAUTH_SECRET,
        "PG_SM_STATE_HOST": PG_SM_STATE_HOST,
        "PG_SM_STATE_PORT": PG_SM_STATE_PORT,
        "PG_SM_STATE_TPCH_DB": PG_SM_STATE_TPCH_DB,
        "PG_SM_STATE_TPCH_USER": PG_SM_STATE_TPCH_USER,
        "PG_SM_STATE_TPCH_PASSWORD": PG_SM_STATE_TPCH_PASSWORD,
    }
    if not PROJECT_FILES or "config.yaml" not in PROJECT_FILES or not RUNNER_SOURCE:
        raise RuntimeError("The deployed SQLMesh project or plan runner snapshot is missing.")

    project = Path("tmp/sqlmesh_plan").resolve()
    for name, content in PROJECT_FILES.items():
        destination = (project / name).resolve()
        if not destination.is_relative_to(project):
            raise ValueError(f"Invalid project snapshot path: {name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    runner = project.parent / "sqlmesh_plan_runner.py"
    runner.write_text(RUNNER_SOURCE, encoding="utf-8")

    env = {
        **os.environ,
        **settings,
        "SQLMESH__DISABLE_ANONYMIZED_ANALYTICS": "1",
        # config.yaml uses user(); the sandbox UID has no passwd entry.
        "USER": "axon",
        "LOGNAME": "axon",
        # Sequential model loading avoids unavailable sandbox semaphores.
        "MAX_FORK_WORKERS": "1",
        "NO_COLOR": "1",
        "TERM": "dumb",
    }
    result = subprocess.run(
        [sys.executable, str(runner), "compute", str(project), environment],
        capture_output=True,
        input="",
        text=True,
        env=env,
        timeout=1200,
    )
    marker = "SQLMESH_PLAN_RESULT="
    lines = [line for line in result.stdout.splitlines() if line.startswith(marker)]
    if result.returncode != 0 or not lines:
        output = f"exit={result.returncode}\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        # Connection errors can contain connection strings; redact before raising.
        for value in sorted(set(settings.values()), key=len, reverse=True):
            if value:
                output = output.replace(value, "[REDACTED]")
        raise RuntimeError(f"SQLMesh plan failed.\n{output}")

    summary = json.loads(lines[-1].removeprefix(marker))
    context.status_message(summary["diff_summary"])
    context.save_variable("plan_fingerprint", summary["plan_fingerprint"])
    context.save_variable("diff_summary", summary["diff_summary"])
    context.save_variable("has_changes", summary["has_changes"])
    return {
        "plan_fingerprint": summary["plan_fingerprint"],
        "diff_summary": summary["diff_summary"],
        "has_changes": summary["has_changes"],
    }
