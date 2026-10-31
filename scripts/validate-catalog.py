#!/usr/bin/env python3
"""Validate that all seven runtimes declare every canonical KRA service ID."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
catalog = json.loads((ROOT / "contracts/kra-services.json").read_text(encoding="utf-8"))
services = catalog["services"]
ids = [item["id"] for item in services]
assert len(ids) == 22, f"Expected 22 services, found {len(ids)}"
assert len(set(ids)) == 22, "Service IDs must be unique"

runtime_files = {
    "Python": "server/app/main.py",
    "Go": "languages/go/main.go",
    "Java": "languages/java/src/main/java/ke/co/krapin/Application.java",
    "JavaScript": "languages/javascript/src/server.js",
    "TypeScript": "languages/typescript/src/server.ts",
    "PHP": "languages/php/public/index.php",
    "Ruby": "languages/ruby/app.rb",
}
for language, relative_path in runtime_files.items():
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    missing = [service_id for service_id in ids if service_id not in source]
    assert not missing, f"{language} is missing catalog IDs: {missing}"

mapping = json.loads((ROOT / "contracts/kra-service-mappings.template.json").read_text(encoding="utf-8"))
expected_mapping_ids = set(ids) - {"authorization"}
assert set(mapping["paths"]) == expected_mapping_ids, "Mapping template must enumerate every non-authorization service"
assert set(mapping["methods"]) == expected_mapping_ids, "Method template must enumerate every non-authorization service"
assert all(value == "" for value in mapping["paths"].values()), "Unverified upstream paths must remain blank"
assert all(value == "POST" for value in mapping["methods"].values()), "POST values are placeholders; review before enabling"

openapi = (ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
for service_id in ids:
    assert f"              - {service_id}" in openapi, f"OpenAPI enum is missing {service_id}"

status_doc = (ROOT / "docs/kra-service-contract-status.md").read_text(encoding="utf-8")
for service_id in ids:
    assert f"`{service_id}`" in status_doc, f"Service status document is missing {service_id}"

print(f"Validated {len(ids)} unique services, {len(expected_mapping_ids)} explicit upstream mapping slots, OpenAPI parity, and {len(runtime_files)} runtime registrations.")
