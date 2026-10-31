"""Async client for KRA's GavaConnect PIN Checker APIs (developer.go.ke).

Flow (as documented on developer.go.ke at the time of writing):
  1. GET  /v1/token/generate?grant_type=client_credentials   (HTTP Basic: key:secret)
  2. POST /checker/v1/pinbypin   {"KRAPIN": "<PIN>"}
     POST /checker/v1/pin        {"TaxpayerType": "KE", "TaxpayerID": "<ID>"}

KRA's success/not-found response bodies are parsed defensively. Confirm the exact
field names against your sandbox with scripts/probe_sandbox.py and adjust the
constants below if needed.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import Settings

NOT_FOUND_CODES = {"30002"}  # "Invalid ID" per the PIN Checker By ID docs
_PIN_KEYS = ("KRAPIN", "PIN", "TaxpayerPIN")
_NAME_KEYS = ("Name", "TaxpayerName", "taxpayerName")
_ERROR_CODE_KEYS = ("errorCode", "ErrorCode", "error_code")


class KraError(Exception):
    """An upstream or client-side failure, already mapped to an HTTP status."""

    def __init__(self, status_code: int, code: str, message: str, payload: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.payload = payload  # kept for debugging tools; never sent to API callers


@dataclass
class PinResult:
    found: bool
    pin: str | None = None
    name: str | None = None  # as returned by KRA (KRA masks taxpayer names)
    raw: dict[str, Any] = field(default_factory=dict)


def _first(data: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _extract_record(data: dict) -> dict:
    for key in ("PINDATA", "data", "Data"):
        value = data.get(key)
        if isinstance(value, dict) and value:
            return value
    if any(k in data for k in _PIN_KEYS + _NAME_KEYS):
        return data
    return {}


def parse_pin_response(status: int, data: dict) -> PinResult:
    code = _first(data, _ERROR_CODE_KEYS)
    record = _extract_record(data)
    if record and code is None and status < 400:
        return PinResult(True, _first(record, _PIN_KEYS), _first(record, _NAME_KEYS), data)
    if status == 404 or (code is not None and code in NOT_FOUND_CODES):
        return PinResult(False, None, None, data)
    raise KraError(
        502, "unexpected_response", f"KRA returned an unexpected response (HTTP {status})", data
    )


class KraClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._s = settings
        self._http = httpx.AsyncClient(
            base_url=settings.base_url, timeout=settings.timeout_seconds, transport=transport
        )
        self._tokens: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _token(self, key: str, secret: str) -> str:
        async with self._lock:
            cached = self._tokens.get(key)
            if cached and cached[1] > time.monotonic() + 60:
                return cached[0]
            try:
                resp = await self._http.get(
                    "/v1/token/generate",
                    params={"grant_type": "client_credentials"},
                    auth=(key, secret),
                )
            except httpx.TimeoutException as exc:
                raise KraError(504, "upstream_timeout", "KRA token endpoint timed out") from exc
            except httpx.HTTPError as exc:
                raise KraError(502, "upstream_unreachable", "Could not reach KRA") from exc
            if resp.status_code in (400, 401, 403):
                raise KraError(502, "upstream_auth_failed", "KRA rejected the configured credentials")
            if resp.status_code >= 400:
                raise KraError(502, "upstream_error", f"KRA token endpoint returned {resp.status_code}")
            try:
                body = resp.json()
                token = body["access_token"]
                ttl = int(body.get("expires_in", 3600))
            except (ValueError, KeyError, TypeError) as exc:
                raise KraError(502, "unexpected_response", "Malformed KRA token response") from exc
            self._tokens[key] = (token, time.monotonic() + ttl)
            return token

    async def _post(
        self, path: str, payload: dict, creds: tuple[str, str], retry: bool = True
    ) -> tuple[int, dict]:
        token = await self._token(*creds)
        try:
            resp = await self._http.post(
                path, json=payload, headers={"Authorization": f"Bearer {token}"}
            )
        except httpx.TimeoutException as exc:
            raise KraError(504, "upstream_timeout", "KRA timed out") from exc
        except httpx.HTTPError as exc:
            raise KraError(502, "upstream_unreachable", "Could not reach KRA") from exc
        if resp.status_code == 401:
            if retry:  # token may have been revoked or expired early
                self._tokens.pop(creds[0], None)
                return await self._post(path, payload, creds, retry=False)
            raise KraError(502, "upstream_auth_failed", "KRA rejected the access token")
        if resp.status_code == 429:
            raise KraError(503, "upstream_rate_limited", "KRA rate limit reached; retry later")
        if resp.status_code >= 500:
            raise KraError(502, "upstream_error", f"KRA returned HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise KraError(502, "unexpected_response", "KRA returned a non-JSON body") from exc
        if not isinstance(data, dict):
            raise KraError(502, "unexpected_response", "KRA returned an unexpected JSON shape")
        return resp.status_code, data


    async def invoke_catalog_service(self, service_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Invoke a configured catalog operation without guessing KRA endpoint contracts."""
        paths = json.loads(os.environ.get("KRA_SERVICE_PATHS_JSON", "{}"))
        methods = json.loads(os.environ.get("KRA_SERVICE_METHODS_JSON", "{}"))
        if service_id == "authorization":
            return {"access_token": await self._token(self._s.pin_key, self._s.pin_secret), "token_type": "Bearer"}
        path = paths.get(service_id)
        if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
            raise KraError(501, "service_not_configured", "No verified KRA endpoint mapping configured")
        method = str(methods.get(service_id, "POST")).upper()
        if method != "POST":
            raise KraError(501, "method_not_supported", "Catalog operations currently require POST; configure the official KRA method before use")
        upstream_base = self._s.base_url
        if service_id == "etims-oscu-integrator-automated-testing":
            upstream_base = os.environ.get("KRA_ETIMS_BASE_URL", "")
        parsed = urlparse(upstream_base)
        if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".kra.go.ke"):
            raise KraError(501, "service_base_not_configured", "Set a verified HTTPS KRA base URL for this service")
        credentials = (self._s.pin_key, self._s.pin_secret)
        async def send(token: str) -> httpx.Response:
            url = f"{upstream_base.rstrip('/')}{path}"
            return await self._http.request(method, url, json=payload,
                headers={"Authorization": f"Bearer {token}"})
        token = await self._token(*credentials)
        try:
            response = await send(token)
            if response.status_code == 401:
                self._tokens.pop(credentials[0], None)
                token = await self._token(*credentials)
                response = await send(token)
        except httpx.TimeoutException as exc:
            raise KraError(504, "upstream_timeout", "KRA service timed out") from exc
        except httpx.HTTPError as exc:
            raise KraError(502, "upstream_unreachable", "Could not reach KRA") from exc
        if response.status_code == 429:
            raise KraError(503, "upstream_rate_limited", "KRA rate limit reached; retry later")
        if response.status_code >= 400:
            raise KraError(502, "kra_upstream_error", "KRA service request failed")
        try:
            data = response.json()
        except ValueError as exc:
            raise KraError(502, "unexpected_response", "KRA returned non-JSON content") from exc
        if not isinstance(data, dict):
            raise KraError(502, "unexpected_response", "KRA returned an unexpected JSON shape")
        return data

    async def check_pin(self, pin: str) -> PinResult:
        status, data = await self._post(
            "/checker/v1/pinbypin", {"KRAPIN": pin}, (self._s.pin_key, self._s.pin_secret)
        )
        return parse_pin_response(status, data)

    async def check_pin_by_id(self, taxpayer_id: str, taxpayer_type: str = "KE") -> PinResult:
        status, data = await self._post(
            "/checker/v1/pin",
            {"TaxpayerType": taxpayer_type, "TaxpayerID": taxpayer_id},
            self._s.by_id_credentials,
        )
        return parse_pin_response(status, data)


class MockKraClient:
    """Offline stand-in so the template can be tried without KRA credentials."""

    DEMO_PIN = "A000000000B"
    DEMO_ID = "00000000"

    async def check_pin(self, pin: str) -> PinResult:
        if pin == self.DEMO_PIN:
            return PinResult(True, self.DEMO_PIN, "DEMO T*****", {"mock": True})
        return PinResult(False, None, None, {"mock": True})

    async def check_pin_by_id(self, taxpayer_id: str, taxpayer_type: str = "KE") -> PinResult:
        if taxpayer_id == self.DEMO_ID:
            return PinResult(True, self.DEMO_PIN, "DEMO T*****", {"mock": True})
        return PinResult(False, None, None, {"mock": True})

    async def aclose(self) -> None:
        return None
