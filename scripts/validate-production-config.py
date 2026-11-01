#!/usr/bin/env python3
"""Fail-closed preflight for a fully mapped KRA production deployment.

This validates configuration shape only. It does not authenticate to KRA,
prove API subscription, validate schemas, or replace sandbox/certification tests.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "contracts/kra-services.json").read_text(encoding="utf-8"))
SERVICES = {item["id"]: item for item in CATALOG["services"]}
MUTATING = {service_id for service_id, item in SERVICES.items() if item["mutating"]}
REQUIRED_UPSTREAM = set(SERVICES) - {"authorization"}


def validate(env: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if env.get("KRA_ENVIRONMENT") != "production":
        errors.append("KRA_ENVIRONMENT must be production")
    if env.get("KRA_MOCK", "true").lower() != "false":
        errors.append("KRA_MOCK must be false")
    for name in ("KRA_PIN_CONSUMER_KEY", "KRA_PIN_CONSUMER_SECRET", "PROXY_API_KEYS"):
        if not env.get(name, "").strip():
            errors.append(f"{name} must be configured")
    redis_url = env.get("IDEMPOTENCY_REDIS_URL", "").strip()
    if not redis_url:
        errors.append("IDEMPOTENCY_REDIS_URL must be configured")
    else:
        parsed_redis = urlparse(redis_url)
        if parsed_redis.scheme != "rediss" or not parsed_redis.hostname:
            errors.append("IDEMPOTENCY_REDIS_URL must be a valid rediss:// TLS URL")
    encryption_key = env.get("IDEMPOTENCY_ENCRYPTION_KEY", "").strip()
    if not encryption_key:
        errors.append("IDEMPOTENCY_ENCRYPTION_KEY must be configured")
    else:
        try:
            if len(base64.b64decode(encryption_key.encode("ascii"), altchars=b"-_", validate=True)) != 32:
                errors.append("IDEMPOTENCY_ENCRYPTION_KEY must decode to 32 bytes for a Fernet key")
        except (ValueError, UnicodeEncodeError, binascii.Error):
            errors.append("IDEMPOTENCY_ENCRYPTION_KEY must be a valid URL-safe base64 Fernet key")
    try:
        if int(env.get("IDEMPOTENCY_TTL_SECONDS", "604800")) < 3600:
            errors.append("IDEMPOTENCY_TTL_SECONDS must be at least 3600")
    except ValueError:
        errors.append("IDEMPOTENCY_TTL_SECONDS must be an integer")
    try:
        paths = json.loads(env.get("KRA_SERVICE_PATHS_JSON", "{}"))
        methods = json.loads(env.get("KRA_SERVICE_METHODS_JSON", "{}"))
        if not isinstance(paths, dict) or not isinstance(methods, dict):
            raise ValueError("mapping values must be JSON objects")
    except (json.JSONDecodeError, ValueError):
        return errors + ["KRA_SERVICE_PATHS_JSON and KRA_SERVICE_METHODS_JSON must be valid JSON objects"]

    missing_paths = sorted(service_id for service_id in REQUIRED_UPSTREAM if not isinstance(paths.get(service_id), str) or not paths[service_id].startswith("/") or paths[service_id].startswith("//"))
    if missing_paths:
        errors.append("Missing or unsafe KRA_SERVICE_PATHS_JSON entries: " + ", ".join(missing_paths))
    missing_methods = sorted(service_id for service_id in REQUIRED_UPSTREAM if service_id not in methods or not isinstance(methods.get(service_id), str) or methods[service_id].upper() not in {"GET", "POST"})
    if missing_methods:
        errors.append("Missing or unsupported explicit KRA_SERVICE_METHODS_JSON entries for: " + ", ".join(missing_methods))
    unknown_ids = sorted((set(paths) | set(methods)) - REQUIRED_UPSTREAM)
    if unknown_ids:
        errors.append("Unknown mapping service IDs: " + ", ".join(unknown_ids))
    unsafe_get = sorted(service_id for service_id in MUTATING if isinstance(methods.get(service_id), str) and methods[service_id].upper() == "GET")
    if unsafe_get:
        errors.append("Mutating services cannot use GET: " + ", ".join(unsafe_get))

    for service_id in REQUIRED_UPSTREAM:
        path = paths.get(service_id)
        if isinstance(path, str) and path.startswith("/") and (".." in path.split("/") or chr(92) in path):
            errors.append(f"Unsafe path configured for {service_id}")

    return errors


if __name__ == "__main__":
    problems = validate(dict(os.environ))
    if problems:
        print("Production configuration rejected:")
        for problem in problems:
            print(f"- {problem}")
        sys.exit(1)
    print(f"Production configuration shape valid for {len(REQUIRED_UPSTREAM)} mapped KRA services. Sandbox, approval and certification evidence are still required.")
