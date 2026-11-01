import httpx
import pytest

from app.config import Settings
from app.kra_client import KraError
from app.oscu_client import DirectOscuClient


def build(handler):
    settings = Settings(
        mock=True,
        proxy_api_keys=("local-test-key",),
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
    result = await client.invoke(
        "branch-list",
        {},
        {
            "tin": "A123456789Z",
            "bhfId": "00",
            "cmcKey": "branch-context",
        },
    )
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


async def test_access_token_is_cached_for_subsequent_operations():
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/v1/token/generate":
            return httpx.Response(200, json={"access_token": "cached-token", "expires_in": 3600})
        return httpx.Response(200, json={"ok": True})

    client = build(handler)
    context = {"tin": "A123456789Z", "bhfId": "00", "cmcKey": "branch-context"}
    await client.invoke("branch-list", {}, context)
    await client.invoke("select-code-list", {}, context)
    assert sum(request.url.path == "/v1/token/generate" for request in calls) == 1
    await client.aclose()


async def test_401_refreshes_token_once_then_retries_operation():
    tokens = iter(["expired-token", "fresh-token"])
    seen_authorizations = []
    token_calls = 0

    def handler(request):
        nonlocal token_calls
        if request.url.path == "/v1/token/generate":
            token_calls += 1
            return httpx.Response(200, json={"access_token": next(tokens), "expires_in": 3600})
        seen_authorizations.append(request.headers["authorization"])
        if request.headers["authorization"] == "Bearer expired-token":
            return httpx.Response(401, json={"sensitive": "must-not-leak"})
        return httpx.Response(200, json={"accepted": True})

    client = build(handler)
    context = {"tin": "A123456789Z", "bhfId": "00", "cmcKey": "branch-context"}
    result = await client.invoke("branch-list", {}, context)
    assert token_calls == 2
    assert seen_authorizations == ["Bearer expired-token", "Bearer fresh-token"]
    assert result["data"] == {"accepted": True}
    await client.aclose()


async def test_missing_tenant_context_fails_before_network_call():
    calls = []
    client = build(lambda request: calls.append(request))
    with pytest.raises(KraError) as error:
        await client.invoke("branch-list", {}, {"tin": "A123456789Z"})
    assert error.value.code == "oscu_context_required"
    assert calls == []
    await client.aclose()


async def test_token_rejection_is_sanitized():
    def handler(request):
        return httpx.Response(401, json={"error": "credential value should not escape"})

    client = build(handler)
    with pytest.raises(KraError) as error:
        await client.invoke(
            "branch-list",
            {},
            {
                "tin": "A123456789Z",
                "bhfId": "00",
                "cmcKey": "branch-context",
            },
        )
    assert error.value.code == "oscu_auth_failed"
    assert "credential value" not in error.value.message
    await client.aclose()


async def test_operation_timeout_reports_unknown_outcome_without_retry():
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/v1/token/generate":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        raise httpx.ReadTimeout("simulated timeout", request=request)

    client = build(handler)
    with pytest.raises(KraError) as error:
        await client.invoke(
            "save-item",
            {"itemCd": "item-1"},
            {
                "tin": "A123456789Z",
                "bhfId": "00",
                "cmcKey": "branch-context",
            },
        )
    assert error.value.code == "oscu_outcome_unknown"
    assert len([request for request in calls if request.url.path.endswith("/saveItem")]) == 1
    await client.aclose()


async def test_upstream_error_body_is_not_returned_to_caller():
    def handler(request):
        if request.url.path == "/v1/token/generate":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(400, json={"taxpayerPin": "private", "internal": "trace"})

    client = build(handler)
    with pytest.raises(KraError) as error:
        await client.invoke(
            "branch-list",
            {},
            {
                "tin": "A123456789Z",
                "bhfId": "00",
                "cmcKey": "branch-context",
            },
        )
    assert error.value.code == "oscu_request_rejected"
    assert "private" not in error.value.message and "trace" not in error.value.message
    await client.aclose()


async def test_401_does_not_replay_mutating_operation():
    seen_operations = []
    token_calls = 0

    def handler(request):
        nonlocal token_calls
        if request.url.path == "/v1/token/generate":
            token_calls += 1
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        seen_operations.append(request.url.path)
        return httpx.Response(401, json={"error": "not authorized"})

    client = build(handler)
    with pytest.raises(KraError) as error:
        await client.invoke(
            "save-item",
            {"itemCd": "item-1"},
            {
                "tin": "A123456789Z",
                "bhfId": "00",
                "cmcKey": "branch-context",
            },
        )
    assert error.value.code == "oscu_auth_failed"
    assert token_calls == 1
    assert len(seen_operations) == 1
    await client.aclose()
