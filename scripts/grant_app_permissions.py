#!/usr/bin/env python3
"""
Grant the brfss-analytics app's service principal SELECT access on the gold layer.

Run after the app is deployed — the SP is auto-created by Databricks Apps the
first time the app is deployed. Idempotent; safe to re-run.
"""

from __future__ import annotations

import json
import subprocess
import sys

PROFILE      = "school"
APP_NAME     = "brfss-analytics"
WAREHOUSE_ID = "8a0ddda80f05d456"
CATALOG      = "data_engineering"
SCHEMA       = "gold"


def cli(*args: str) -> str:
    """Run a `databricks` CLI command and return stdout."""
    return subprocess.run(
        ["databricks", *args, "--profile", PROFILE],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def sql(stmt: str) -> dict:
    """Submit a SQL statement via the Statement Execution API and return the response."""
    payload = json.dumps({
        "statement": stmt,
        "warehouse_id": WAREHOUSE_ID,
        "wait_timeout": "50s",
    })
    out = cli("api", "post", "/api/2.0/sql/statements", "--json", payload)
    return json.loads(out)


def main() -> None:
    print(f"==> Looking up service principal for app '{APP_NAME}'...")
    app = json.loads(cli("apps", "get", APP_NAME, "--output", "json"))

    # The SP identifier is named differently across CLI versions — probe.
    sp = (
        app.get("service_principal_client_id")
        or app.get("oauth2_application_client_id")
        or app.get("service_principal_name")
    )
    if not sp:
        print("ERROR: Could not find a service-principal identifier on the app object.")
        print("       Available top-level fields:")
        for k in sorted(app):
            print(f"         {k!r}: {app[k]!r}")
        sys.exit(1)

    print(f"    SP identifier: {sp}\n")

    grants = [
        f"GRANT USE CATALOG ON CATALOG `{CATALOG}` TO `{sp}`",
        f"GRANT USE SCHEMA  ON SCHEMA  `{CATALOG}`.`{SCHEMA}` TO `{sp}`",
        f"GRANT SELECT      ON SCHEMA  `{CATALOG}`.`{SCHEMA}` TO `{sp}`",
    ]

    print(f"==> Granting SELECT on {CATALOG}.{SCHEMA} ...")
    failed = False
    for stmt in grants:
        print(f"    {stmt}")
        resp = sql(stmt)
        state = resp.get("status", {}).get("state")
        if state != "SUCCEEDED":
            failed = True
            err = resp.get("status", {}).get("error", {})
            print(f"      FAILED — state={state}, error={err}")

    if failed:
        sys.exit(2)

    print(f"\n==> Done. The SP can now SELECT every current and future table in {CATALOG}.{SCHEMA}.")


if __name__ == "__main__":
    main()
