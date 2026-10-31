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
