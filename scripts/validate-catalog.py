#!/usr/bin/env python3
"""Validate that all seven runtimes declare every canonical KRA service ID."""
import json
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

print(f"Validated {len(ids)} KRA services across {len(runtime_files)} runtimes.")
