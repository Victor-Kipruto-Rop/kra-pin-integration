#!/usr/bin/env python3
"""Validate catalog parity and fail-closed upstream mapping configuration."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
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

    mapping = json.loads(
        (ROOT / "contracts/kra-service-mappings.template.json").read_text(encoding="utf-8")
    )
    expected_mapping_ids = set(ids) - {"authorization"}
    paths = mapping["paths"]
    methods = mapping["methods"]
    assert set(paths) == expected_mapping_ids, (
        "Mapping template must enumerate every non-authorization service"
    )
    assert set(methods) == expected_mapping_ids, (
        "Method template must enumerate every non-authorization service"
    )

    services_by_id = {item["id"]: item for item in services}
    configured_paths = 0
    for service_id in sorted(expected_mapping_ids):
        path = paths[service_id]
        method = methods[service_id]
        assert isinstance(path, str), f"{service_id}: path must be a string"
        assert method in {"GET", "POST"}, (
            f"{service_id}: method must be GET or POST, got {method!r}"
        )
        if path:
            assert path.startswith("/") and not path.startswith("//"), (
                f"{service_id}: upstream path must be a relative absolute path"
            )
            assert "://" not in path and "?" not in path and "#" not in path, (
                f"{service_id}: path must not contain a URL, query, or fragment"
            )
            assert ".." not in path.split("/"), (
                f"{service_id}: path traversal segments are not allowed"
            )
            configured_paths += 1
        if services_by_id[service_id].get("mutating"):
            assert method != "GET", (
                f"{service_id}: mutating operations cannot use GET"
            )

    openapi = (ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    for service_id in ids:
        assert f"              - {service_id}" in openapi, (
            f"OpenAPI enum is missing {service_id}"
        )

    status_doc = (ROOT / "docs/kra-service-contract-status.md").read_text(encoding="utf-8")
    for service_id in ids:
        assert f"`{service_id}`" in status_doc, (
            f"Service status document is missing {service_id}"
        )

    print(
        f"Validated {len(ids)} unique services, {configured_paths} documented upstream "
        f"paths, {len(expected_mapping_ids) - configured_paths} fail-closed mapping slots, "
        f"OpenAPI parity, and {len(runtime_files)} runtime registrations."
    )


if __name__ == "__main__":
    main()
