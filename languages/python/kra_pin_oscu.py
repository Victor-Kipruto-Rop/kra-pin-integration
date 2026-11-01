"""Direct eTIMS OSCU sandbox client. Never use this module in browser code."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

TOKEN_URL = "https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials"
API_BASE = "https://sbx.kra.go.ke/etims-oscu/api/v1"


class OscuError(RuntimeError):
    def __init__(self, code: str, message: str, *, outcome_unknown: bool = False):
        super().__init__(message)
        self.code = code
        self.outcome_unknown = outcome_unknown


class DirectOscuClient:
    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        app_id: str,
        *,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not all((consumer_key, consumer_secret, app_id)):
            raise ValueError("OSCU consumer credentials and app ID are required")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        self._key, self._secret, self._app_id = consumer_key, consumer_secret, app_id
        self._http = httpx.Client(timeout=timeout, transport=transport)
        manifest = json.loads((Path(__file__).with_name("etims_oscu_endpoints.json")).read_text())
        self._operations = {item["id"]: item for item in manifest["operations"]}
        self._token: str | None = None

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "DirectOscuClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _access_token(self) -> str:
        try:
            response = self._http.get(TOKEN_URL, auth=(self._key, self._secret))
            response.raise_for_status()
            body = response.json()
            token = body.get("access_token") if isinstance(body, dict) else None
            if not isinstance(token, str) or not token:
                raise ValueError("missing token")
            self._token = token
            return token
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            raise OscuError("oscu_auth_failed", "Could not obtain a valid KRA OSCU access token") from exc

    def invoke(
        self,
        operation_id: str,
        payload: dict[str, Any],
        tenant_context: dict[str, str],
        *,
        confirm_mutation: bool = False,
    ) -> Any:
        operation = self._operations.get(operation_id)
        if operation is None:
            raise ValueError("Unknown OSCU operation ID")
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        if operation["mutates"] and not confirm_mutation:
            raise ValueError("This operation may mutate KRA state; pass confirm_mutation=True after approval")
        headers = {"apigee_app_id": self._app_id, "Accept": "application/json", "Content-Type": "application/json"}
        for name in operation["headers"]:
            if name == "apigee_app_id":
                continue
            value = tenant_context.get(name)
            if not value:
                raise ValueError(f"Missing required OSCU context: {name}")
            headers[name] = value
        headers["Authorization"] = f"Bearer {self._token or self._access_token()}"
        try:
            response = self._http.post(f"{API_BASE}{operation['path']}", json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise OscuError(
                "oscu_outcome_unknown" if operation["mutates"] else "oscu_timeout",
                "KRA OSCU request timed out; reconcile the operation before resubmitting" if operation["mutates"] else "KRA OSCU request timed out",
                outcome_unknown=bool(operation["mutates"]),
            ) from exc
        except httpx.HTTPError as exc:
            if operation["mutates"]:
                raise OscuError(
                    "oscu_outcome_unknown",
                    "KRA OSCU request outcome is unknown; reconcile before resubmitting",
                    outcome_unknown=True,
                ) from exc
            raise OscuError("oscu_upstream_unreachable", "Could not reach KRA OSCU") from exc
        if response.status_code == 401:
            self._token = None
        if response.status_code >= 500 and operation["mutates"]:
            raise OscuError(
                "oscu_outcome_unknown",
                "KRA OSCU returned a server error; reconcile before resubmitting",
                outcome_unknown=True,
            )
        if response.status_code >= 400:
            raise OscuError("oscu_request_rejected", f"KRA OSCU rejected the request (HTTP {response.status_code})")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            if operation["mutates"]:
                raise OscuError(
                    "oscu_outcome_unknown",
                    "KRA OSCU returned an invalid response; reconcile before resubmitting",
                    outcome_unknown=True,
                ) from exc
            raise OscuError("oscu_invalid_response", "KRA OSCU returned a non-JSON response") from exc
