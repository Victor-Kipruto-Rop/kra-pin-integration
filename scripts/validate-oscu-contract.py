#!/usr/bin/env python3
"""Validate the direct eTIMS OSCU endpoint inventory and packaged runtime manifest.

This checks transcription consistency only. It does not certify KRA behavior,
request schemas, response schemas, or mutation semantics.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "contracts" / "etims-oscu-direct.endpoints.json"
BUNDLED = ROOT / "server" / "app" / "etims_oscu_endpoints.json"
GUIDE = ROOT / "docs" / "etims-oscu-direct-integration.md"
OPENAPI = ROOT / "contracts" / "etims-oscu-openapi.yaml"
SDK_MANIFESTS = [
    ROOT / "languages/python/etims_oscu_endpoints.json",
    ROOT / "languages/go/oscu/etims_oscu_endpoints.json",
    ROOT / "languages/java/src/main/resources/etims_oscu_endpoints.json",
    ROOT / "languages/javascript/src/etims_oscu_endpoints.json",
    ROOT / "languages/typescript/src/etims_oscu_endpoints.json",
    ROOT / "languages/php/src/etims_oscu_endpoints.json",
    ROOT / "languages/ruby/etims_oscu_endpoints.json",
]


def fail(message: str) -> None:
    raise SystemExit(f"OSCU contract validation failed: {message}")


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot load {path.relative_to(ROOT)}: {exc}")


def main() -> None:
    source = load(SOURCE)
    bundled = load(BUNDLED)
    operations = source.get("operations")
    if not isinstance(operations, list) or len(operations) != 23:
        fail(f"expected exactly 23 operations; found {len(operations) if isinstance(operations, list) else 'invalid'}")

    ids: set[str] = set()
    paths: set[str] = set()
    mutating = 0
    expected_headers = {"tin", "bhfId", "cmcKey", "apigee_app_id"}
    for operation in operations:
        operation_id = operation.get("id")
        path = operation.get("path")
        method = operation.get("method")
        headers = operation.get("headers")
        if not isinstance(operation_id, str) or not operation_id:
            fail("every operation must have a non-empty stable id")
        if operation_id in ids:
            fail(f"duplicate operation id: {operation_id}")
        ids.add(operation_id)
        if not isinstance(path, str) or not path.startswith("/") or "://" in path:
            fail(f"{operation_id}: path must be a relative absolute-path reference")
        if path in paths:
            fail(f"duplicate endpoint path: {path}")
        paths.add(path)
        if method != "POST":
            fail(f"{operation_id}: expected documented POST method, got {method!r}")
        if not isinstance(headers, list) or "apigee_app_id" not in headers:
            fail(f"{operation_id}: apigee_app_id header must be documented")
        if operation_id == "oscu-initialization":
            if set(headers) != {"apigee_app_id"}:
                fail("initialize must retain its collection-specific app-id-only header list")
        elif not expected_headers.issubset(set(headers)):
            fail(f"{operation_id}: missing one or more common tenant context headers")
        if not isinstance(operation.get("mutates"), bool):
            fail(f"{operation_id}: mutates must be explicitly classified")
        mutating += int(operation["mutates"])

    bundled_operations = bundled.get("operations")
    if not isinstance(bundled_operations, list):
        fail("bundled runtime manifest has no operations list")
    project = lambda items: [
        {key: item.get(key) for key in ("id", "method", "path", "headers", "mutates")}
        for item in items
    ]
    if project(operations) != project(bundled_operations):
        fail("bundled runtime manifest differs from the canonical contract manifest")

    for sdk_manifest in SDK_MANIFESTS:
        sdk = load(sdk_manifest)
        if project(operations) != project(sdk.get("operations", [])):
            fail(f"SDK manifest differs from canonical contract: {sdk_manifest.relative_to(ROOT)}")

    openapi = OPENAPI.read_text(encoding="utf-8")
    for operation in operations:
        if f"  {operation['path']}:\\n" not in openapi or f"      operationId: {operation['id']}\\n" not in openapi:
            fail(f"OpenAPI contract is missing {operation['id']} ({operation['path']})")

    guide = GUIDE.read_text(encoding="utf-8")
    if "isr ccCd" not in guide or "Confirm that field with KRA" not in guide:
        fail("known malformed sales sample field must remain explicitly documented as unresolved")

    print(
        f"Validated {len(ids)} unique direct OSCU operations, {len(paths)} paths, "
        f"{mutating} currently classified writes, canonical/runtime/7-SDK manifest parity, "
        "and OpenAPI operation parity."
    )
    print("This is static contract-inventory validation, not live KRA certification.")


if __name__ == "__main__":
    main()
