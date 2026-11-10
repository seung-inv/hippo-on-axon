"""Validate (and with --create, create) the nightly schedule for Sqlmesh_Run_Playground.

Run from ~/code/hippo-on-axon with prod AXON_* env vars. Secret inputs carry the
secret *names*; Axon resolves values at run time.
"""

import json
import sys

from axon.lib.client.client import AxonClient
from workflows.sqlmesh_run_playground import DEFAULT_INPUT, workflow

TENANT = "b9588ee9-43dc-4fb9-a65f-a15ea89818ae"
NAMESPACE = "9b652148-2c92-4d97-ab86-78f0b4ddf393"  # hippo-playground
FLOW_ID = "2a076298-87e8-4415-bde9-f880b9f0f5d2"
VERSION_ID = "d62abb95-fa27-4c6e-9dc9-750e0f6f4984"  # latest published (streaming logs)

client = AxonClient()
declared = client.flows.get_unmatched_inputs(VERSION_ID)
step_ids = {v.variable_name: v.step_id for v in declared}
types = {v.name: v.type for v in workflow.inputs}
# Scheduler input format: {"name", "type", "value"} or, for secrets, "secret_ref" (the secret name).
variables = [
    {"name": k, "type": "Secret", "secret_ref": v}
    if types.get(k) == "Secret"
    else {"name": k, "type": types.get(k, "String"), "value": v}
    for k, v in DEFAULT_INPUT.items()
]
missing = [k for k in DEFAULT_INPUT if k not in step_ids]
if missing:
    sys.exit(f"Inputs without a step id: {missing}")

target = {"flow_id": FLOW_ID, "tenant_id": TENANT, "input_variables": variables}
t = client.execution._transport  # same authenticated GraphQL transport the SDK uses
check = t.query(
    "query V($n: String!, $v: JSON!) { validateScheduleTarget(target_operation_name: $n, target_variables: $v)"
    " { valid errors resolved_target_schema_hash } }",
    {"n": "executeFlow", "v": target},
)["validateScheduleTarget"]
print("validate:", json.dumps(check))
if not check["valid"] or "--create" not in sys.argv:
    sys.exit(0 if check["valid"] else 1)

created = t.query(
    "mutation C($input: CreateScheduleInput!) { createSchedule(input: $input)"
    " { id name state cron_expr timezone next_fire_at } }",
    {
        "input": {
            "namespace_id": NAMESPACE,
            "name": "sqlmesh-run-playground-nightly",
            "description": "Nightly `sqlmesh run prod` for anusha_playground (replaces the GitHub Actions SQLMesh Run job, 15 5 * * * UTC).",
            "schedule_kind": "Cron",
            "cron_expr": "15 5 * * *",
            "timezone": "UTC",
            "target_operation_name": "executeFlow",
            "target_variables": target,
            "misfire_policy": "FireOnceNow",
            "max_concurrent_runs": 1,
            "tags": ["hippo", "sqlmesh"],
        }
    },
)["createSchedule"]
print("created:", json.dumps(created))
