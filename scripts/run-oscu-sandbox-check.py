#!/usr/bin/env python3
"""Run one explicitly approved direct OSCU sandbox operation and save redacted evidence.

No network call occurs unless BOTH --execute and --confirm-sandbox are supplied.
Request/response bodies, credentials and tenant identifiers are never written
to the evidence artifact.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
sys.path.insert(0, str(SERVER))

from app.config import Settings  # noqa: E402
from app.kra_client import KraError  # noqa: E402
from app.oscu_client import DirectOscuClient  # noqa: E402
from app.oscu_evidence import build_evidence  # noqa: E402


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--operation", required=True, help="Stable operation ID from the direct OSCU manifest")
    result.add_argument("--payload", required=True, type=Path, help="Path to a locally prepared JSON object")
    result.add_argument("--output", type=Path, help="Evidence JSON path; defaults to artifacts/oscu-evidence/")
    result.add_argument("--change-reference", help="Required approval/ticket reference for operations marked mutating; not sent to KRA")
    result.add_argument("--execute", action="store_true", help="Allow a real outbound sandbox request")
    result.add_argument("--confirm-sandbox", action="store_true", help="Explicitly confirm this is an approved sandbox test")
    return result


def read_payload(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read payload JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Payload must be a JSON object")
    return payload


def require_environment() -> dict[str, str]:
    names = (
        "ETIMS_OSCU_CONSUMER_KEY",
        "ETIMS_OSCU_CONSUMER_SECRET",
        "ETIMS_OSCU_APP_ID",
        "ETIMS_OSCU_TIN",
        "ETIMS_OSCU_BHF_ID",
        "ETIMS_OSCU_CMC_KEY",
    )
    values = {name: os.environ.get(name, "") for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise SystemExit("Missing required environment variables: " + ", ".join(missing))
    return values


def evidence_path(path: Path | None, operation_id: str) -> Path:
    if path is not None:
        return path
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ROOT / "artifacts" / "oscu-evidence" / f"{stamp}-{operation_id}.json"


async def execute(args: argparse.Namespace, payload: dict, env: dict[str, str], operation: dict) -> dict:
    settings = Settings(
        environment="sandbox",
        timeout_seconds=float(os.environ.get("ETIMS_OSCU_TIMEOUT_SECONDS", "20")),
        etims_oscu_enabled=True,
        etims_oscu_consumer_key=env["ETIMS_OSCU_CONSUMER_KEY"],
        etims_oscu_consumer_secret=env["ETIMS_OSCU_CONSUMER_SECRET"],
        etims_oscu_app_id=env["ETIMS_OSCU_APP_ID"],
    )
    context = {
        "tin": env["ETIMS_OSCU_TIN"],
        "bhfId": env["ETIMS_OSCU_BHF_ID"],
        "cmcKey": env["ETIMS_OSCU_CMC_KEY"],
    }
    client = DirectOscuClient(settings)
    try:
        result = await client.invoke(args.operation, payload, context)
    except KraError as exc:
        # Do not persist exception text, upstream body, credentials, or identifiers.
        raise SystemExit(f"Sandbox call failed; sanitized error code: {exc.code}") from None
    finally:
        await client.aclose()

    return build_evidence(
        operation_id=args.operation,
        endpoint_path=operation["path"],
        payload=payload,
        response=result.get("data"),
        tenant_context=context,
        change_reference=args.change_reference,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def write_private_evidence(path: Path, evidence: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def main() -> int:
    args = parser().parse_args()
    payload = read_payload(args.payload)
    manifest_path = SERVER / "app" / "etims_oscu_endpoints.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    operation = next((item for item in manifest["operations"] if item["id"] == args.operation), None)
    if operation is None:
        raise SystemExit(f"Unknown operation ID: {args.operation}")
    if operation.get("mutates") and (not args.idempotency_key or not 16 <= len(args.idempotency_key) <= 128):
        raise SystemExit("This operation is classified as mutating; provide --idempotency-key (16-128 characters)")
    if not args.execute or not args.confirm_sandbox:
        print("DRY RUN: payload parsed and operation found. No network request was made.")
        print(f"Operation: {args.operation} ({operation['method']} {operation['path']})")
        print(f"Payload top-level keys: {', '.join(sorted(payload.keys())) or '(none)'}")
        print("To make an approved sandbox call, supply BOTH --execute and --confirm-sandbox.")
        return 0

    env = require_environment()
    evidence = asyncio.run(execute(args, payload, env, operation))
    output = evidence_path(args.output, args.operation)
    write_private_evidence(output, evidence)
    print(f"Sandbox operation succeeded. Redacted evidence written to: {output}")
    print("No request body, response body, credentials, tenant identifiers or authorization headers were saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
