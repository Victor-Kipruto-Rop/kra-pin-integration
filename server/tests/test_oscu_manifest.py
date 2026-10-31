import json
from pathlib import Path

from app.config import Settings
from app.oscu_client import DirectOscuClient


def test_packaged_manifest_contains_all_23_operations():
    path = Path(__file__).parents[1] / "app" / "etims_oscu_endpoints.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    operations = manifest["operations"]
    assert len(operations) == 23
    assert len({item["id"] for item in operations}) == 23
    assert len({item["path"] for item in operations}) == 23
    assert all(item["method"] == "POST" for item in operations)


def test_initialize_has_only_documented_application_id_header():
    path = Path(__file__).parents[1] / "app" / "etims_oscu_endpoints.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    initialize = next(item for item in manifest["operations"] if item["id"] == "oscu-initialization")
    assert initialize["headers"] == ["apigee_app_id"]


def test_direct_oscu_rejects_production_environment():
    settings = Settings(environment="production", mock=True)
    try:
        DirectOscuClient(settings)
    except ValueError as exc:
        assert "sandbox-only" in str(exc)
    else:
        raise AssertionError("production environment must be rejected")
