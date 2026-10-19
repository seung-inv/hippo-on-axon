"""Run SQLMesh info against a project snapshot supplied at deployment."""

from __future__ import annotations

from axon.lib import Context, Variable, delegate
from axon.lib.dsl.types import SecretStr


# workflows/sqlmesh_info.py appends the snapshot to the shipped source.
PROJECT_FILES: dict[str, str] = {}


@delegate(
    description="Check the TPCH SQLMesh warehouse and state backend connections.",
    outputs=[Variable(name="sqlmesh_output", type="String")],
    dependencies=[
        "sqlmesh[databricks,duckdb]==0.236.3",
        "databricks-sdk==0.154.0",
        "psycopg2-binary==2.9.13",
    ],
)
def run_sqlmesh_info(
    context: Context,
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
    """Capture CLI output; fail on connection errors even if the CLI exits zero."""
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
    if not PROJECT_FILES or "config.yaml" not in PROJECT_FILES:
        raise RuntimeError("The deployed SQLMesh project snapshot is missing.")

    project = Path("tmp/sqlmesh_info").resolve()
    for name, content in PROJECT_FILES.items():
        destination = (project / name).resolve()
        if not destination.is_relative_to(project):
            raise ValueError(f"Invalid project snapshot path: {name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")

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
        [
            sys.executable,
            "-c",
            "from sqlmesh.cli.main import cli; cli()",
            "-p",
            str(project),
            "info",
        ],
        capture_output=True,
        input="",
        text=True,
        env=env,
        timeout=600,
    )
    output = (
        f"exit={result.returncode}\n--- stdout ---\n{result.stdout}"
        f"\n--- stderr ---\n{result.stderr}"
    )
    # Connection errors can contain connection strings; redact before persistence.
    for value in sorted(set(settings.values()), key=len, reverse=True):
        if value:
            output = output.replace(value, "[REDACTED]")
    context.save_variable("sqlmesh_output", output)
    combined = result.stdout + result.stderr
    if "State backend connection failed" in combined:
        raise RuntimeError(f"SQLMesh state backend connection failed; stopping.\n{output}")
    if result.returncode != 0 or "Data warehouse connection succeeded" not in combined:
        raise RuntimeError(f"SQLMesh warehouse check failed.\n{output}")
    return {"sqlmesh_output": output}
