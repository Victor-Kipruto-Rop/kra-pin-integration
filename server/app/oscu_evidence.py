"""Helpers for producing privacy-preserving OSCU test evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def response_shape(value: Any, depth: int = 0) -> dict[str, Any]:
    """Describe response structure without retaining values or object keys.

    Object keys can themselves contain taxpayer identifiers in map-shaped API
    responses, so evidence records only key counts and anonymous child shapes.
    """
    if isinstance(value, dict):
        result: dict[str, Any] = {"type": "object", "key_count": len(value)}
        if depth < 2:
            result["field_shapes"] = [
                response_shape(item, depth + 1)
                for _, item in sorted(value.items(), key=lambda pair: str(pair[0]))[:50]
            ]
        return result
    if isinstance(value, list):
        result = {"type": "array", "length": len(value)}
        if value and depth < 2:
            result["first_item"] = response_shape(value[0], depth + 1)
        return result
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, (int, float)):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string", "length": len(value)}
    return {"type": type(value).__name__}


def build_evidence(
    *,
    operation_id: str,
    endpoint_path: str,
    payload: dict[str, Any],
    response: Any,
    tenant_context: dict[str, str],
    change_reference: str | None,
    timestamp: str,
) -> dict[str, Any]:
    """Build evidence that never contains request/response values or secrets."""
    return {
        "schema_version": "1.0",
        "timestamp_utc": timestamp,
        "environment": "sandbox",
        "provider": "KRA direct eTIMS OSCU",
        "operation_id": operation_id,
        "method": "POST",
        "endpoint_path": endpoint_path,
        "outcome": "success",
        "request": {
            "payload_sha256": canonical_sha256(payload),
            "payload_top_level_key_count": len(payload),
        },
        "tenant_context": {
            "tin_present": bool(tenant_context.get("tin")),
            "branch_id_present": bool(tenant_context.get("bhfId")),
            "cmc_key_present": bool(tenant_context.get("cmcKey")),
        },
        "change_reference_sha256": canonical_sha256(change_reference) if change_reference else None,
        "response": {
            "sha256": canonical_sha256(response),
            "shape": response_shape(response),
        },
        "redaction": {
            "request_body_stored": False,
            "response_body_stored": False,
            "credentials_stored": False,
            "tenant_identifiers_stored": False,
            "authorization_headers_stored": False,
            "object_keys_stored": False,
        },
    }
