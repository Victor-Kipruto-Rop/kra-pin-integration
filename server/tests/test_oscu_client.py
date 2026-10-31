import httpx
import pytest

from app.config import Settings
from app.kra_client import KraError
from app.oscu_client import DirectOscuClient


def build(handler):
    settings = Settings(
        mock=True, proxy_api_keys=("local-test-key",),
        etims_oscu_enabled=True,
        etims_oscu_consumer_key="local-key",
        etims_oscu_consumer_secret="local-secret",
        etims_oscu_app_id="local-app",
    )
    return DirectOscuClient(settings, transport=httpx.MockTransport(handler))


async def test_token_and_operation_use_separate_direct_host():
    seen = []
    def handler(request):
        seen.append(request)
        if request.url.path == "/v1/token/generate":
            return httpx.Response(200, json={"access_token": "direct-token", "expires_in": 3600})
        return httpx.Response(200, json={"accepted": True})
    client = build(handler)
    result = await client.invoke("branch-list", {}, {
        "tin": "A123456789Z", "bhfId": "00", "cmcKey": "branch-context",
    })
    assert seen[0].url.path == "/v1/token/generate"
    assert seen[1].url.path == "/etims-oscu/api/v1/branchList"
    assert seen[1].headers["authorization"] == "Bearer direct-token"
    assert seen[1].headers["apigee_app_id"] == "local-app"
    assert result["data"] == {"accepted": True}
    await client.aclose()


async def test_initialize_does_not_require_branch_headers():
    def handler(request):
        if request.url.path == "/v1/token/generate":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        assert request.url.path.endswith("/initialize")
        return httpx.Response(200, json={"ok": True})
    client = build(handler)
    await client.invoke("oscu-initialization", {"tin": "x"}, {})
    await client.aclose()


async def test_unknown_operation_is_rejected_without_network_call():
    calls = []
    client = build(lambda request: calls.append(request))
    with pytest.raises(KraError) as error:
        await client.invoke("not-listed", {}, {})
    assert error.value.code == "oscu_operation_not_found"
    assert calls == []
    await client.aclose()
