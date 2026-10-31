#!/usr/bin/env python3
"""Fail-closed preflight for a fully mapped KRA production deployment.

This validates configuration shape only. It does not authenticate to KRA,
prove API subscription, validate schemas, or replace sandbox/certification tests.
"""
from __future__ import annotations

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
    missing_methods = sorted(service_id for service_id in REQUIRED_UPSTREAM if methods.get(service_id, "POST").upper() not in {"GET", "POST"})
    if missing_methods:
        errors.append("Unsupported methods for: " + ", ".join(missing_methods))
    unsafe_get = sorted(service_id for service_id in MUTATING if methods.get(service_id, "POST").upper() == "GET")
    if unsafe_get:
        errors.append("Mutating services cannot use GET: " + ", ".join(unsafe_get))

    for service_id in REQUIRED_UPSTREAM:
        path = paths.get(service_id)
        if isinstance(path, str) and path.startswith("/") and (".." in path.split("/") or "\\\\" in path):
            errors.append(f"Unsafe path configured for {service_id}")

    etims = urlparse(env.get("KRA_ETIMS_BASE_URL", ""))
    if etims.scheme != "https" or etims.hostname != "etims-api.kra.go.ke":
        errors.append("KRA_ETIMS_BASE_URL must use the approved production HTTPS host etims-api.kra.go.ke")
    return errors


if __name__ == "__main__":
    problems = validate(dict(os.environ))
    if problems:
        print("Production configuration rejected:")
        for problem in problems:
            print(f"- {problem}")
        sys.exit(1)
    print(f"Production configuration shape valid for {len(REQUIRED_UPSTREAM)} mapped KRA services. Sandbox, approval and certification evidence are still required.")
