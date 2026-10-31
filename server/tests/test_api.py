import pytest
from fastapi.testclient import TestClient

from app.config import ConfigError, Settings, validate_settings
from app.kra_client import KraError, MockKraClient
from app.main import create_app

KEY = {"X-API-Key": "test-key"}


def make_app(**overrides):
    base = dict(mock=True, proxy_api_keys=("test-key",))
    base.update(overrides)
    return create_app(Settings(**base))


@pytest.fixture
def client():
    with TestClient(make_app()) as c:
        yield c


def test_health_needs_no_key(client):
    body = client.get("/health").json()
    assert body == {"status": "ok", "environment": "sandbox", "mock": True}


def test_requires_api_key(client):
    payload = {"pin": "A000000000B", "consent": True}
    assert client.post("/v1/pin/verify", json=payload).status_code == 401
    assert client.post("/v1/pin/verify", json=payload, headers={"X-API-Key": "nope"}).status_code == 401


def test_verify_demo_pin_and_lowercase_input(client):
    r = client.post("/v1/pin/verify", json={"pin": " a000000000b ", "consent": True}, headers=KEY)
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True and body["pin"] == "A000000000B" and body["raw"] is None


def test_unknown_pin_is_not_found(client):
    r = client.post("/v1/pin/verify", json={"pin": "A999999999Z", "consent": True}, headers=KEY)
    assert r.status_code == 200 and r.json()["found"] is False


def test_consent_is_required(client):
    r = client.post("/v1/pin/verify", json={"pin": "A000000000B"}, headers=KEY)
    assert r.status_code == 400


def test_consent_can_be_disabled():
    with TestClient(make_app(require_consent=False)) as c:
        r = c.post("/v1/pin/verify", json={"pin": "A000000000B"}, headers=KEY)
        assert r.status_code == 200


def test_strict_format_rejects_bad_pin():
    with TestClient(make_app(strict_pin_format=True)) as c:
        r = c.post("/v1/pin/verify", json={"pin": "123", "consent": True}, headers=KEY)
        assert r.status_code == 422


def test_verify_by_id(client):
    r = client.post(
        "/v1/pin/verify-by-id", json={"taxpayer_id": "00000000", "consent": True}, headers=KEY
    )
    assert r.status_code == 200 and r.json()["found"] is True


def test_rate_limit():
    with TestClient(make_app(rate_limit_per_minute=2)) as c:
        payload = {"pin": "A000000000B", "consent": True}
        codes = [c.post("/v1/pin/verify", json=payload, headers=KEY).status_code for _ in range(3)]
        assert codes == [200, 200, 429]


def test_upstream_errors_are_mapped_without_leaking_details():
    class Failing(MockKraClient):
        async def check_pin(self, pin):
            raise KraError(504, "upstream_timeout", "KRA timed out")

    app = create_app(Settings(mock=True, proxy_api_keys=("test-key",)), client=Failing())
    with TestClient(app) as c:
        r = c.post("/v1/pin/verify", json={"pin": "A000000000B", "consent": True}, headers=KEY)
        assert r.status_code == 504
        assert r.json() == {"error": {"code": "upstream_timeout", "message": "KRA timed out"}}


@pytest.mark.parametrize(
    "overrides",
    [
        dict(environment="production", mock=True, proxy_api_keys=("k",)),
        dict(mock=False, proxy_api_keys=("k",)),  # missing KRA credentials
        dict(mock=True),  # no proxy keys and not explicitly unauthenticated
        dict(environment="production", pin_key="a", pin_secret="b", allow_unauthenticated=True),
        dict(environment="staging", mock=True, proxy_api_keys=("k",)),
    ],
)
def test_unsafe_configuration_refuses_to_start(overrides):
    with pytest.raises(ConfigError):
        validate_settings(Settings(**overrides))


def test_local_dev_can_run_unauthenticated():
    validate_settings(Settings(mock=True, allow_unauthenticated=True))

@pytest.mark.parametrize('service_id', [
    'authorization','pin-checker-by-pin','pin-checker-by-id','fetch-taxpayer-obligations',
    'know-kra-tax-service-office','tax-compliance-certificate-application',
    'tax-compliance-certificate-checker','vat-exemption-checker','it-exemption-checker',
    'nil-return-filing','tot-return-filing','income-tax-withholding-prn-generation',
    'vat-withholding-prn-generation','rental-withholding-prn-generation',
    'excise-license-checker-by-pin','excise-license-checker-by-certificate-number',
    'customs-declaration-status-checker','customs-tax-calculator','import-certificate-checker-by-pin',
    'import-certificate-checker-by-cert-number','invoice-checker','etims-oscu-integrator-automated-testing',
])
def test_all_catalog_routes_are_registered_in_mock_mode(client, service_id):
    response = client.post(f'/v1/kra/{service_id}', json={'consent': True, 'payload': {}}, headers={**KEY, 'Idempotency-Key': 'test-idempotency-key-0001'})
    assert response.status_code == 501
    assert 'mock' in response.text.lower() or 'mapping' in response.text.lower()


def test_catalog_idempotency_replays_same_payload_and_rejects_conflicts():
    class CatalogClient:
        def __init__(self):
            self.calls = 0
        async def invoke_catalog_service(self, service_id, payload):
            self.calls += 1
            return {"service": service_id, "accepted": True}
        async def aclose(self):
            return None

    fake = CatalogClient()
    app = create_app(Settings(mock=False, proxy_api_keys=("test-key",), pin_key="consumer", pin_secret="secret"), client=fake)
    headers = {**KEY, "Idempotency-Key": "idempotency-test-0001"}
    with TestClient(app) as c:
        first = c.post("/v1/kra/nil-return-filing", json={"consent": True, "payload": {"period": "2026"}}, headers=headers)
        replay = c.post("/v1/kra/nil-return-filing", json={"consent": True, "payload": {"period": "2026"}}, headers=headers)
        conflict = c.post("/v1/kra/nil-return-filing", json={"consent": True, "payload": {"period": "2025"}}, headers=headers)
    assert first.status_code == replay.status_code == 200
    assert conflict.status_code == 409
    assert fake.calls == 1


def test_production_requires_shared_idempotency_store():
    with pytest.raises(ConfigError, match="IDEMPOTENCY_REDIS_URL"):
        validate_settings(Settings(
            environment="production",
            pin_key="consumer",
            pin_secret="secret",
            proxy_api_keys=("production-key",),
        ))


def test_production_accepts_configured_shared_idempotency_store():
    validate_settings(Settings(
        environment="production",
        pin_key="consumer",
        pin_secret="secret",
        proxy_api_keys=("production-key",),
        idempotency_redis_url="rediss://redis.example.invalid:6379/0",
        idempotency_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    ))


def test_production_requires_idempotency_encryption_key():
    with pytest.raises(ConfigError, match="IDEMPOTENCY_ENCRYPTION_KEY"):
        validate_settings(Settings(
            environment="production",
            pin_key="consumer",
            pin_secret="secret",
            proxy_api_keys=("production-key",),
            idempotency_redis_url="rediss://redis.example.invalid:6379/0",
        ))


def test_readiness_endpoint_checks_security_store():
    with TestClient(make_app()) as c:
        response = c.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_non_finite_upstream_timeout_is_rejected():
    with pytest.raises(ConfigError, match="KRA_TIMEOUT_SECONDS"):
        validate_settings(Settings(mock=True, proxy_api_keys=("test-key",), timeout_seconds=float("nan")))


@pytest.mark.parametrize(
    "error",
    [
        KraError(504, "upstream_timeout", "KRA timed out"),
        KraError(502, "upstream_unreachable", "KRA connection failed"),
        KraError(502, "kra_upstream_error", "KRA returned an upstream error"),
        KraError(502, "unexpected_response", "KRA response was malformed"),
    ],
)
def test_ambiguous_catalog_mutation_outcome_is_never_resubmitted(error):
    class AmbiguousCatalogClient:
        def __init__(self):
            self.calls = 0

        async def invoke_catalog_service(self, service_id, payload):
            self.calls += 1
            raise error

        async def aclose(self):
            return None

    fake = AmbiguousCatalogClient()
    app = create_app(
        Settings(mock=False, proxy_api_keys=("test-key",), pin_key="consumer", pin_secret="secret"),
        client=fake,
    )
    headers = {**KEY, "Idempotency-Key": "ambiguous-mutation-0001"}
    with TestClient(app) as c:
        first = c.post(
            "/v1/kra/nil-return-filing",
            json={"consent": True, "payload": {"period": "2026"}},
            headers=headers,
        )
        replay = c.post(
            "/v1/kra/nil-return-filing",
            json={"consent": True, "payload": {"period": "2026"}},
            headers=headers,
        )
    assert first.status_code in (502, 504)
    assert replay.status_code == 409
    assert "outcome is unknown" in replay.json()["detail"]
    assert fake.calls == 1


def test_unexpected_failure_after_mutation_starts_is_marked_unknown():
    class CrashingCatalogClient:
        def __init__(self):
            self.calls = 0

        async def invoke_catalog_service(self, service_id, payload):
            self.calls += 1
            raise RuntimeError("simulated post-send failure")

        async def aclose(self):
            return None

    fake = CrashingCatalogClient()
    app = create_app(
        Settings(mock=False, proxy_api_keys=("test-key",), pin_key="consumer", pin_secret="secret"),
        client=fake,
    )
    headers = {**KEY, "Idempotency-Key": "unexpected-failure-0001"}
    with TestClient(app, raise_server_exceptions=False) as c:
        first = c.post(
            "/v1/kra/nil-return-filing",
            json={"consent": True, "payload": {"period": "2026"}},
            headers=headers,
        )
        replay = c.post(
            "/v1/kra/nil-return-filing",
            json={"consent": True, "payload": {"period": "2026"}},
            headers=headers,
        )
    assert first.status_code == 500
    assert replay.status_code == 409
    assert "outcome is unknown" in replay.json()["detail"]
    assert fake.calls == 1


def test_definitive_upstream_rejection_releases_mutation_reservation():
    class RejectingCatalogClient:
        def __init__(self):
            self.calls = 0

        async def invoke_catalog_service(self, service_id, payload):
            self.calls += 1
            raise KraError(422, "invalid_payload", "KRA rejected the request")

        async def aclose(self):
            return None

    fake = RejectingCatalogClient()
    app = create_app(
        Settings(mock=False, proxy_api_keys=("test-key",), pin_key="consumer", pin_secret="secret"),
        client=fake,
    )
    headers = {**KEY, "Idempotency-Key": "definitive-rejection-0001"}
    with TestClient(app) as c:
        first = c.post(
            "/v1/kra/nil-return-filing",
            json={"consent": True, "payload": {"period": "invalid"}},
            headers=headers,
        )
        second = c.post(
            "/v1/kra/nil-return-filing",
            json={"consent": True, "payload": {"period": "invalid"}},
            headers=headers,
        )
    assert first.status_code == second.status_code == 422
    assert fake.calls == 2
