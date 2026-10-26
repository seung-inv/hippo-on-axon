#!/usr/bin/env bash
# Run an `axon` CLI command authenticated with the PAT in .env.
#
# An `api` PAT is an exchange-only credential: the platform rejects it as a
# direct Bearer token (on pr5866 with `revocation_check_failed`). This script
# exchanges it at /v1/pat/exchange for a short-lived token (up to 1 hour) and
# passes that token to `axon` as AXON_API_KEY, overriding .env for this command
# only. SDK 1.3.0 does not perform this exchange itself.
#
# Usage:
#   scripts/axon_pat.sh deploy sqlmesh_info -n default
#   scripts/axon_pat.sh run sqlmesh_info -n default --wait
#
# Reads AXON_API_URL, AXON_TENANT_ID, and AXON_API_KEY (the PAT) from .env.
# Set AXON_PAT_NAMESPACE to scope the token to a namespace other than `default`.
set -euo pipefail

cd "$(dirname "$0")/.."

jit="$(AXON_PAT_NAMESPACE="${AXON_PAT_NAMESPACE:-default}" .venv/bin/python - <<'PY'
import os
import sys
import time

import httpx
from dotenv import dotenv_values

v = dotenv_values(".env")
missing = [k for k in ("AXON_API_URL", "AXON_TENANT_ID", "AXON_API_KEY") if not v.get(k)]
if missing:
    sys.exit(f"Missing in .env: {', '.join(missing)}")

base = v["AXON_API_URL"].split("/graphql")[0]
body = {
    "tenant_id": v["AXON_TENANT_ID"],
    "namespace": os.environ["AXON_PAT_NAMESPACE"],
    "use_case": "api",
    "ttl_seconds": 3600,  # server-side maximum
}
for attempt in range(5):
    r = httpx.post(
        f"{base}/v1/pat/exchange",
        json=body,
        headers={"Authorization": "Bearer " + v["AXON_API_KEY"]},
        timeout=30,
    )
    if r.status_code == 200:
        print(r.json()["jit"])
        break
    # 503 pool_saturated was observed to be transient; anything else is fatal.
    if r.status_code != 503:
        sys.exit(f"PAT exchange failed: {r.status_code} {r.text[:200]}")
    time.sleep(5 * (attempt + 1))
else:
    sys.exit("PAT exchange failed: server kept returning 503")
PY
)"

AXON_API_KEY="$jit" PYTHONDONTWRITEBYTECODE=1 exec .venv/bin/axon "$@"
