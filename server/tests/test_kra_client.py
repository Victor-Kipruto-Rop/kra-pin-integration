"""Client tests run against httpx.MockTransport: no network, no credentials.

The success-response shape below ({"PINDATA": {...}}) is an ASSUMPTION based on
public integrations; confirm it with scripts/probe_sandbox.py and update here.
"""
import base64

import httpx
import pytest

from app.config import Settings
from app.kra_client import KraClient, KraError


def make(handler, **overrides):
    settings = Settings(pin_key="k", pin_secret="s", **overrides)
    return KraClient(settings, transport=httpx.MockTransport(handler))


def basic(key, secret):
    return "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode()


def router(checker, calls, token="tok"):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/v1/token/generate":
            assert request.url.params["grant_type"] == "client_credentials"
            return httpx.Response(200, json={"access_token": token, "expires_in": "3600"})
        return checker(request)

    return handler


FOUND = {"PINDATA": {"KRAPIN": "A000000010Z", "Name": "JOHN D*****"}}


async def test_found_and_token_is_cached():
    calls = []
    client = make(router(lambda r: httpx.Response(200, json=FOUND), calls))
    first = await client.check_pin("A000000010Z")
    await client.check_pin("A000000010Z")
    assert first.found and first.pin == "A000000010Z" and first.name == "JOHN D*****"
    assert calls.count("/v1/token/generate") == 1
    await client.aclose()


async def test_request_shapes_and_basic_auth():
    seen = {}

    def checker(request):
        seen["auth"] = request.headers["authorization"]
        seen["body"] = request.read()
        return httpx.Response(200, json=FOUND)

    client = make(router(checker, []))
    await client.check_pin("A000000010Z")
    assert seen["auth"] == "Bearer tok"
    assert seen["body"] == b'{"KRAPIN":"A000000010Z"}'
    await client.aclose()


async def test_by_id_not_found_maps_error_30002():
    seen = {}

    def checker(request):
        assert request.url.path == "/checker/v1/pin"
        seen["body"] = request.read()
        return httpx.Response(400, json={"errorCode": "30002", "errorMessage": "Invalid ID"})

    client = make(router(checker, []))
    result = await client.check_pin_by_id("12345678")
    assert result.found is False
    assert b'"TaxpayerType":"KE"' in seen["body"] and b'"TaxpayerID":"12345678"' in seen["body"]
    await client.aclose()


async def test_by_id_can_use_separate_credentials():
    auths = []

    def handler(request):
        if request.url.path == "/v1/token/generate":
            auths.append(request.headers["authorization"])
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(200, json=FOUND)

    settings = Settings(pin_key="k", pin_secret="s", pin_by_id_key="k2", pin_by_id_secret="s2")
    client = KraClient(settings, transport=httpx.MockTransport(handler))
    await client.check_pin("A000000010Z")
    await client.check_pin_by_id("12345678")
    assert auths == [basic("k", "s"), basic("k2", "s2")]
    await client.aclose()


async def test_bad_credentials_become_upstream_auth_failed():
    client = make(lambda r: httpx.Response(401, json={"errorCode": "401"}))
    with pytest.raises(KraError) as exc:
        await client.check_pin("A000000010Z")
    assert exc.value.status_code == 502 and exc.value.code == "upstream_auth_failed"
    await client.aclose()


async def test_token_refreshed_once_after_401():
    calls, state = [], {"n": 0}

    def checker(request):
        state["n"] += 1
        return httpx.Response(401) if state["n"] == 1 else httpx.Response(200, json=FOUND)

    client = make(router(checker, calls))
    assert (await client.check_pin("A000000010Z")).found
    assert calls.count("/v1/token/generate") == 2
    await client.aclose()


async def test_timeout_maps_to_504():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    client = make(handler)
    with pytest.raises(KraError) as exc:
        await client.check_pin("A000000010Z")
    assert exc.value.status_code == 504
    await client.aclose()


async def test_unexpected_shape_is_reported_not_guessed():
    client = make(router(lambda r: httpx.Response(200, json={"hello": "world"}), []))
    with pytest.raises(KraError) as exc:
        await client.check_pin("A000000010Z")
    assert exc.value.code == "unexpected_response" and exc.value.payload == {"hello": "world"}
    await client.aclose()
