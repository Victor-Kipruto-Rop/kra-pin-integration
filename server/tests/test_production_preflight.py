import importlib.util
import json
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate-production-config.py"
SPEC = importlib.util.spec_from_file_location("production_preflight", SCRIPT)
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


def valid_environment():
    catalog = json.loads((ROOT / "contracts" / "kra-services.json").read_text(encoding="utf-8"))
    service_ids = {item["id"] for item in catalog["services"]} - {"authorization"}
    return {
        "KRA_ENVIRONMENT": "production",
        "KRA_MOCK": "false",
        "KRA_PIN_CONSUMER_KEY": "consumer",
        "KRA_PIN_CONSUMER_SECRET": "secret",
        "PROXY_API_KEYS": "high-entropy-test-key",
        "KRA_SERVICE_PATHS_JSON": json.dumps({item: f"/verified/{item}" for item in service_ids}),
        "KRA_SERVICE_METHODS_JSON": json.dumps({item: "POST" for item in service_ids}),
        "IDEMPOTENCY_REDIS_URL": "rediss://redis.example.invalid:6379/0",
        "IDEMPOTENCY_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
        "IDEMPOTENCY_TTL_SECONDS": "604800",
    }


def test_production_preflight_accepts_tls_redis_and_valid_fernet_key():
    assert PREFLIGHT.validate(valid_environment()) == []


def test_production_preflight_rejects_plaintext_redis():
    env = valid_environment()
    env["IDEMPOTENCY_REDIS_URL"] = "redis://redis.example.invalid:6379/0"
    assert any("rediss:// TLS" in error for error in PREFLIGHT.validate(env))


def test_production_preflight_rejects_invalid_encryption_key():
    env = valid_environment()
    env["IDEMPOTENCY_ENCRYPTION_KEY"] = "not-a-fernet-key"
    assert any("Fernet key" in error for error in PREFLIGHT.validate(env))


def test_production_preflight_rejects_short_idempotency_retention():
    env = valid_environment()
    env["IDEMPOTENCY_TTL_SECONDS"] = "300"
    assert any("at least 3600" in error for error in PREFLIGHT.validate(env))
