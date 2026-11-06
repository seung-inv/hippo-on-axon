"""Run `sqlmesh run` for a project snapshot supplied at deployment."""

from __future__ import annotations

from axon.lib import Context, Variable, delegate
from axon.lib.dsl.types import SecretStr


# workflows/sqlmesh_run_playground.py appends the snapshot to the shipped source.
PROJECT_FILES: dict[str, str] = {}


@delegate(
    description="Run `sqlmesh run` on the anusha_playground project to process new and missing intervals (SQLMesh 0.236.3).",
    outputs=[Variable(name="sqlmesh_output", type="String")],
    dependencies=[
        # Matches uv.lock in inv-hippo/hdm-anusha_playground (its GitHub jobs share this state DB).
        "sqlmesh[databricks,duckdb]==0.236.3",
        "databricks-sdk==0.162.0",
        "psycopg2-binary==2.9.13",
    ],
)
def run_sqlmesh_run_playground(
    context: Context,
    environment: str,
    DBR_RESEARCH_HOST: SecretStr,
    DBR_RESEARCH_HTTP_PATH: SecretStr,
    DBR_HDM_ANUSHA_PLAYGROUND_OAUTH_ID: SecretStr,
    DBR_HDM_ANUSHA_PLAYGROUND_OAUTH_SECRET: SecretStr,
    PG_SM_STATE_HOST: SecretStr,
    PG_SM_STATE_PORT: SecretStr,
    PG_SM_STATE_ANUSHA_PLAYGROUND_DB: SecretStr,
    PG_SM_STATE_ANUSHA_PLAYGROUND_USER: SecretStr,
    PG_SM_STATE_ANUSHA_PLAYGROUND_PASSWORD: SecretStr,
) -> dict:
    """Capture CLI output; fail if `sqlmesh run` exits non-zero."""
    import os
    from pathlib import Path
    import subprocess
    import sys

    settings = {
        "DBR_RESEARCH_HOST": DBR_RESEARCH_HOST,
        "DBR_RESEARCH_HTTP_PATH": DBR_RESEARCH_HTTP_PATH,
        "DBR_HDM_ANUSHA_PLAYGROUND_OAUTH_ID": DBR_HDM_ANUSHA_PLAYGROUND_OAUTH_ID,
        "DBR_HDM_ANUSHA_PLAYGROUND_OAUTH_SECRET": DBR_HDM_ANUSHA_PLAYGROUND_OAUTH_SECRET,
        "PG_SM_STATE_HOST": PG_SM_STATE_HOST,
        "PG_SM_STATE_PORT": PG_SM_STATE_PORT,
        "PG_SM_STATE_ANUSHA_PLAYGROUND_DB": PG_SM_STATE_ANUSHA_PLAYGROUND_DB,
        "PG_SM_STATE_ANUSHA_PLAYGROUND_USER": PG_SM_STATE_ANUSHA_PLAYGROUND_USER,
        "PG_SM_STATE_ANUSHA_PLAYGROUND_PASSWORD": PG_SM_STATE_ANUSHA_PLAYGROUND_PASSWORD,
    }
    if not PROJECT_FILES or "config.yaml" not in PROJECT_FILES:
        raise RuntimeError("The deployed SQLMesh project snapshot is missing.")
    if not environment:
        raise ValueError("environment is required, e.g. prod or dev_axon.")

    project = Path("tmp/sqlmesh_run_playground").resolve()
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
        # Matches the GitHub Actions SQLMesh Run job.
        "COLUMNS": "200",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from sqlmesh.cli.main import cli; cli()",
            "-p",
            str(project),
            "run",
            environment,
        ],
        capture_output=True,
        input="",
        text=True,
        env=env,
        timeout=3600,
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
    if result.returncode != 0:
        raise RuntimeError(f"SQLMesh run failed.\n{output}")
    return {"sqlmesh_output": output}
