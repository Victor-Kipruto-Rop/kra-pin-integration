from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app

KEY = {"X-API-Key": "test-key"}

class FakeOscu:
    def operation(self, operation_id):
        return {"id": operation_id, "mutates": operation_id == "save-item", "headers": ["tin", "bhfId", "cmcKey", "apigee_app_id"]}
    async def invoke(self, operation_id, payload, tenant_headers):
        return {"operation": operation_id, "data": payload}
    async def aclose(self):
        pass

def make_client():
    settings = Settings(mock=True, proxy_api_keys=("test-key",))
    app = create_app(settings, oscu_client=FakeOscu())
    return TestClient(app)

def test_direct_oscu_route_requires_consent():
    with make_client() as client:
        response = client.post("/v1/etims/oscu/branch-list", json={"payload": {}}, headers=KEY)
    assert response.status_code == 400

def test_direct_oscu_route_passes_tenant_context():
    headers = {**KEY, "X-ETIMS-TIN": "A123456789Z", "X-ETIMS-BHF-ID": "00", "X-ETIMS-CMC-KEY": "ctx"}
    with make_client() as client:
        response = client.post("/v1/etims/oscu/branch-list", json={"consent": True, "payload": {"tin": "A123456789Z"}}, headers=headers)
    assert response.status_code == 200
    assert response.json()["operation"] == "branch-list"

def test_direct_oscu_write_requires_idempotency_key():
    headers = {**KEY, "X-ETIMS-TIN": "A123456789Z", "X-ETIMS-BHF-ID": "00", "X-ETIMS-CMC-KEY": "ctx"}
    with make_client() as client:
        response = client.post("/v1/etims/oscu/save-item", json={"consent": True, "payload": {}}, headers=headers)
    assert response.status_code == 400

def test_direct_oscu_write_idempotency_replay_and_conflict():
    headers = {**KEY, "X-ETIMS-TIN": "A123456789Z", "X-ETIMS-BHF-ID": "00", "X-ETIMS-CMC-KEY": "ctx", "Idempotency-Key": "oscu-write-key-000001"}
    with make_client() as client:
        first = client.post("/v1/etims/oscu/save-item", json={"consent": True, "payload": {"itemCd": "x"}}, headers=headers)
        replay = client.post("/v1/etims/oscu/save-item", json={"consent": True, "payload": {"itemCd": "x"}}, headers=headers)
        conflict = client.post("/v1/etims/oscu/save-item", json={"consent": True, "payload": {"itemCd": "y"}}, headers=headers)
    assert first.status_code == replay.status_code == 200
    assert conflict.status_code == 409


def test_direct_oscu_adapter_is_disabled_by_default():
    settings = Settings(mock=True, proxy_api_keys=("test-key",))
    app = create_app(settings, oscu_client=None)
    with TestClient(app) as client:
        response = client.post(
            "/v1/etims/oscu/branch-list",
            json={"consent": True, "payload": {}},
            headers=KEY,
        )
    assert response.status_code == 503


def test_direct_oscu_route_requires_api_key():
    with make_client() as client:
        response = client.post(
            "/v1/etims/oscu/branch-list",
            json={"consent": True, "payload": {}},
        )
    assert response.status_code == 401


def test_direct_oscu_unknown_outcome_blocks_same_process_replay():
    from app.kra_client import KraError

    class TimeoutOscu(FakeOscu):
        def __init__(self):
            self.calls = 0
        async def invoke(self, operation_id, payload, tenant_headers):
            self.calls += 1
            raise KraError(504, "oscu_outcome_unknown", "simulated timeout")

    fake = TimeoutOscu()
    settings = Settings(mock=True, proxy_api_keys=("test-key",))
    app = create_app(settings, oscu_client=fake)
    headers = {
        **KEY,
        "X-ETIMS-TIN": "A123456789Z",
        "X-ETIMS-BHF-ID": "00",
        "X-ETIMS-CMC-KEY": "ctx",
        "Idempotency-Key": "unknown-outcome-key-001",
    }
    with TestClient(app) as client:
        first = client.post(
            "/v1/etims/oscu/save-item",
            json={"consent": True, "payload": {"itemCd": "x"}},
            headers=headers,
        )
        replay = client.post(
            "/v1/etims/oscu/save-item",
            json={"consent": True, "payload": {"itemCd": "x"}},
            headers=headers,
        )
    assert first.status_code == 504
    assert replay.status_code == 409
    assert fake.calls == 1

def test_oscu_idempotency_is_scoped_to_tenant_context():
    class CountingOscu(FakeOscu):
        def __init__(self):
            self.calls = 0
        async def invoke(self, operation_id, payload, tenant_headers):
            self.calls += 1
            return {"operation": operation_id, "tenant": tenant_headers["tin"], "call": self.calls}
    fake = CountingOscu()
    app = create_app(Settings(mock=True, proxy_api_keys=("test-key",)), oscu_client=fake)
    common = {"X-API-Key": "test-key", "X-ETIMS-BHF-ID": "00", "X-ETIMS-CMC-KEY": "ctx", "Idempotency-Key": "tenant-isolation-key-0001"}
    body = {"consent": True, "payload": {"itemCd": "same"}}
    with TestClient(app) as client:
        first = client.post("/v1/etims/oscu/save-item", json=body, headers={**common, "X-ETIMS-TIN": "A111111111A"})
        replay = client.post("/v1/etims/oscu/save-item", json=body, headers={**common, "X-ETIMS-TIN": "A111111111A"})
        other_tenant = client.post("/v1/etims/oscu/save-item", json=body, headers={**common, "X-ETIMS-TIN": "A222222222B"})
    assert first.status_code == replay.status_code == other_tenant.status_code == 200
    assert first.json()["call"] == replay.json()["call"] == 1
    assert other_tenant.json()["call"] == 2
    assert fake.calls == 2

def test_idempotency_store_failure_prevents_upstream_submission():
    class BrokenStore:
        async def ping(self): return None
        async def aclose(self): return None
        async def allow_rate_limit(self, identity, limit, window_seconds=60): return True
        async def reserve(self, key, fingerprint): raise ConnectionError("redis unavailable")
        async def complete(self, key, fingerprint, response): raise AssertionError("must not complete")
        async def mark_unknown(self, key, fingerprint): return None
        async def release(self, key, fingerprint): return None

    fake = FakeOscu()
    app = create_app(Settings(mock=True, proxy_api_keys=("test-key",)), oscu_client=fake, idempotency_store=BrokenStore())
    headers = {**KEY, "X-ETIMS-TIN": "A123456789Z", "X-ETIMS-BHF-ID": "00", "X-ETIMS-CMC-KEY": "ctx", "Idempotency-Key": "redis-unavailable-key-001"}
    with TestClient(app) as client:
        response = client.post("/v1/etims/oscu/save-item", json={"consent": True, "payload": {}}, headers=headers)
    assert response.status_code == 503


def test_failed_idempotency_persistence_blocks_replay_after_upstream_success():
    class CompletionFailStore:
        def __init__(self):
            self.state = "new"
        async def ping(self): return None
        async def aclose(self): return None
        async def allow_rate_limit(self, identity, limit, window_seconds=60): return True
        async def reserve(self, key, fingerprint):
            if self.state == "new":
                self.state = "pending"
                return "new", None
            return "pending", None
        async def complete(self, key, fingerprint, response): raise ConnectionError("redis write failed")
        async def mark_unknown(self, key, fingerprint): self.state = "unknown"
        async def release(self, key, fingerprint): self.state = "new"

    fake = FakeOscu()
    store = CompletionFailStore()
    app = create_app(Settings(mock=True, proxy_api_keys=("test-key",)), oscu_client=fake, idempotency_store=store)
    headers = {**KEY, "X-ETIMS-TIN": "A123456789Z", "X-ETIMS-BHF-ID": "00", "X-ETIMS-CMC-KEY": "ctx", "Idempotency-Key": "redis-complete-failure-001"}
    with TestClient(app) as client:
        first = client.post("/v1/etims/oscu/save-item", json={"consent": True, "payload": {}}, headers=headers)
        replay = client.post("/v1/etims/oscu/save-item", json={"consent": True, "payload": {}}, headers=headers)
    assert first.status_code == 503
    assert replay.status_code == 409
