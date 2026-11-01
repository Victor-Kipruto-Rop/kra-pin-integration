"""Isolated server-side client for KRA's direct eTIMS OSCU sandbox API.

This client is deliberately separate from the GavaConnect catalog client. The
provided collection documents sandbox only; production is disabled until KRA
provides an approved production host and credentials.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx

from .config import Settings
from .kra_client import KraError

TOKEN_HOST = "https://sbx.kra.go.ke"
OSCU_BASE_URL = "https://sbx.kra.go.ke/etims-oscu/api/v1"


class DirectOscuClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        if settings.environment != "sandbox":
            raise ValueError("Direct OSCU is sandbox-only until KRA supplies production details")
        self._settings = settings
        self._http = httpx.AsyncClient(
            base_url=TOKEN_HOST, timeout=settings.timeout_seconds, transport=transport
        )
        self._tokens: tuple[str, float] | None = None
        self._token_lock = asyncio.Lock()
        manifest_path = Path(__file__).with_name("etims_oscu_endpoints.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self._operations = {item["id"]: item for item in manifest["operations"]}

    async def aclose(self) -> None:
        await self._http.aclose()

    def operation(self, operation_id: str) -> dict[str, Any] | None:
        return self._operations.get(operation_id)

    async def _access_token(self, force_refresh: bool = False) -> str:
        async with self._token_lock:
            if not force_refresh and self._tokens and self._tokens[1] > time.monotonic() + 60:
                return self._tokens[0]
            try:
                response = await self._http.get(
                    "/v1/token/generate",
                    params={"grant_type": "client_credentials"},
                    auth=(self._settings.etims_oscu_consumer_key, self._settings.etims_oscu_consumer_secret),
                )
            except httpx.TimeoutException as exc:
                raise KraError(504, "oscu_token_timeout", "KRA OSCU token endpoint timed out") from exc
            except httpx.HTTPError as exc:
                raise KraError(
                    502, "oscu_token_unreachable", "Could not reach KRA OSCU token endpoint"
                ) from exc
            if response.status_code in (400, 401, 403):
                raise KraError(502, "oscu_auth_failed", "KRA rejected the configured OSCU credentials")
            if response.status_code >= 400:
                raise KraError(
                    502, "oscu_token_error", f"KRA OSCU token endpoint returned HTTP {response.status_code}"
                )
            try:
                body = response.json()
                token = body["access_token"]
                ttl = int(body.get("expires_in", 3600))
                if not isinstance(token, str) or not token or ttl <= 0:
                    raise ValueError("invalid token response")
            except (ValueError, KeyError, TypeError) as exc:
                raise KraError(
                    502, "oscu_token_unexpected_response", "Malformed KRA OSCU token response"
                ) from exc
            self._tokens = (token, time.monotonic() + ttl)
            return token

    async def invoke(
        self,
        operation_id: str,
        payload: dict[str, Any],
        tenant_headers: dict[str, str],
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        operation = self.operation(operation_id)
        if operation is None:
            raise KraError(404, "oscu_operation_not_found", "Unknown direct OSCU operation")
        headers = {"apigee_app_id": self._settings.etims_oscu_app_id}
        for name in operation["headers"]:
            if name == "apigee_app_id":
                continue
            value = tenant_headers.get(name)
            if not value:
                raise KraError(422, "oscu_context_required", f"Missing required OSCU context header: {name}")
            headers[name] = value

        token = await self._access_token()
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/json"
        headers["Content-Type"] = "application/json"
        try:
            response = await self._http.post(
                f"{OSCU_BASE_URL.removeprefix(TOKEN_HOST)}{operation['path']}",
                json=payload,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            # A timeout on a write can leave the remote outcome unknown. Never retry it here.
            raise KraError(
                504,
                "oscu_outcome_unknown",
                "KRA OSCU request timed out; check the transaction state before resubmitting",
            ) from exc
        except httpx.HTTPError as exc:
            raise KraError(502, "oscu_upstream_unreachable", "Could not reach KRA OSCU API") from exc

        if response.status_code == 401:
            self._tokens = None
            if retry_auth and not operation.get("mutates", False):
                # Replaying a mutation after 401 is unsafe unless KRA explicitly
                # guarantees the rejected request could not have been processed.
                await self._access_token(force_refresh=True)
                return await self.invoke(operation_id, payload, tenant_headers, retry_auth=False)
        if response.status_code == 401:
            raise KraError(502, "oscu_auth_failed", "KRA OSCU rejected the access token")
        if response.status_code == 429:
            raise KraError(503, "oscu_rate_limited", "KRA OSCU rate limit reached; retry later")
        if response.status_code >= 500:
            raise KraError(502, "oscu_upstream_error", f"KRA OSCU returned HTTP {response.status_code}")
        if not response.content:
            data = None
        else:
            try:
                data = response.json()
            except ValueError as exc:
                raise KraError(
                    502, "oscu_unexpected_response", "KRA OSCU returned a non-JSON response"
                ) from exc
        if response.status_code >= 400:
            # Do not relay untrusted upstream error content or taxpayer data.
            raise KraError(
                422, "oscu_request_rejected", f"KRA OSCU rejected the request (HTTP {response.status_code})"
            )
        return {"operation": operation_id, "environment": "sandbox", "data": data}
