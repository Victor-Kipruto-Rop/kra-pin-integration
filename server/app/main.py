from __future__ import annotations

import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .config import Settings, load_settings, validate_settings
from .idempotency import MemoryIdempotencyStore, RedisIdempotencyStore
from .kra_client import KraClient, KraError, MockKraClient, PinResult
from .oscu_client import DirectOscuClient
from .schemas import PinByIdRequest, PinVerifyRequest, VerifyResponse, normalize_pin
from .security import api_key_matches, mask_pin

log = logging.getLogger("kra_pin")


def create_app(
    settings: Settings | None = None, client=None, oscu_client=None, idempotency_store=None
) -> FastAPI:
    settings = settings or load_settings()
    validate_settings(settings)
    store = idempotency_store or (
        RedisIdempotencyStore(
            settings.idempotency_redis_url,
            settings.idempotency_encryption_key,
            settings.idempotency_ttl_seconds,
        )
        if settings.idempotency_redis_url
        else MemoryIdempotencyStore()
    )
    service_mutates = {
        "authorization": False,
        "pin-checker-by-pin": False,
        "pin-checker-by-id": False,
        "fetch-taxpayer-obligations": False,
        "know-kra-tax-service-office": False,
        "tax-compliance-certificate-application": True,
        "tax-compliance-certificate-checker": False,
        "vat-exemption-checker": False,
        "it-exemption-checker": False,
        "nil-return-filing": True,
        "tot-return-filing": True,
        "income-tax-withholding-prn-generation": True,
        "vat-withholding-prn-generation": True,
        "rental-withholding-prn-generation": True,
        "excise-license-checker-by-pin": False,
        "excise-license-checker-by-certificate-number": False,
        "customs-declaration-status-checker": False,
        "customs-tax-calculator": False,
        "import-certificate-checker-by-pin": False,
        "import-certificate-checker-by-cert-number": False,
        "invoice-checker": False,
        "etims-oscu-integrator-automated-testing": True,
    }
    kra = client or (MockKraClient() if settings.mock else KraClient(settings))
    oscu = oscu_client or (DirectOscuClient(settings) if settings.etims_oscu_enabled else None)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await store.ping()
        yield
        await kra.aclose()
        if oscu is not None:
            await oscu.aclose()
        await store.aclose()

    app = FastAPI(
        title="KRA PIN Integration Template",
        version=__version__,
        description="Unofficial server-side proxy for KRA GavaConnect PIN checks.",
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET", "POST"],
            allow_headers=[
                "X-API-Key",
                "Content-Type",
                "Idempotency-Key",
                "X-ETIMS-TIN",
                "X-ETIMS-BHF-ID",
                "X-ETIMS-CMC-KEY",
            ],
        )

    async def guard(request: Request, x_api_key: str | None = Header(default=None)) -> str:
        if settings.proxy_api_keys:
            if not x_api_key or not api_key_matches(x_api_key, settings.proxy_api_keys):
                raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
            identity = hashlib.sha256(x_api_key.encode()).hexdigest()
        else:
            identity = request.client.host if request.client else "anonymous"
        try:
            allowed = await store.allow_rate_limit(identity, settings.rate_limit_per_minute)
        except Exception as exc:
            log.error("rate_limit_store_unavailable")
            raise HTTPException(status_code=503, detail="Security storage is unavailable") from exc
        if not allowed:
            raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": "60"})
        return identity

    async def execute_idempotently(
        cache_key: str,
        fingerprint: str,
        operation,
        unknown_codes: set[str] | None = None,
    ) -> dict:
        try:
            state, cached_response = await store.reserve(cache_key, fingerprint)
        except Exception as exc:
            log.error("idempotency_store_unavailable operation=reserve")
            raise HTTPException(
                status_code=503, detail="Idempotency storage is unavailable; request was not submitted"
            ) from exc
        if state == "conflict":
            raise HTTPException(
                status_code=409, detail="Idempotency-Key was already used with a different payload"
            )
        if state == "complete":
            return cached_response
        if state == "unknown":
            raise HTTPException(
                status_code=409,
                detail="Previous request outcome is unknown; reconcile with KRA before retrying",
            )
        if state == "pending":
            raise HTTPException(
                status_code=409, detail="A request with this Idempotency-Key is already in progress"
            )
        try:
            response = await operation()
        except KraError as exc:
            try:
                if exc.code in (unknown_codes or set()):
                    await store.mark_unknown(cache_key, fingerprint)
                else:
                    await store.release(cache_key, fingerprint)
            except Exception:
                log.error("idempotency_store_unavailable operation=record_failure")
            raise
        except Exception:
            # Once the operation coroutine has started, an unexpected failure may
            # have happened after the upstream accepted a mutation. Fail closed:
            # keep this key blocked until an operator reconciles the upstream state.
            try:
                await store.mark_unknown(cache_key, fingerprint)
            except Exception:
                log.error("idempotency_store_unavailable operation=record_unknown")
            raise
        try:
            await store.complete(cache_key, fingerprint, response)
        except Exception as exc:
            # The upstream may have committed the mutation. Leave the durable
            # pending reservation in place so a retry cannot submit it again.
            log.error("idempotency_store_unavailable operation=complete")
            raise HTTPException(
                status_code=503,
                detail=(
                    "KRA response received but idempotency result could not be persisted; "
                    "reconcile before retrying"
                ),
            ) from exc
        return response

    def payload_fingerprint(payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        secret = (
            settings.idempotency_encryption_key.encode("ascii")
            if settings.idempotency_encryption_key
            else b"kra-pin-local-development-only"
        )
        return hmac.new(secret, canonical, hashlib.sha256).hexdigest()

    def require_consent(consent: bool) -> None:
        if settings.require_consent and not consent:
            raise HTTPException(
                status_code=400, detail="consent must be true: the taxpayer must agree to this check"
            )

    def to_response(result: PinResult) -> VerifyResponse:
        return VerifyResponse(
            found=result.found,
            pin=result.pin,
            taxpayer_name=result.name,
            environment=settings.environment,
            mock=settings.mock,
            raw=result.raw if settings.include_raw else None,
        )

    @app.exception_handler(KraError)
    async def kra_error_handler(_: Request, exc: KraError) -> JSONResponse:
        log.warning("kra_error code=%s status=%s", exc.code, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}}
        )

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "environment": settings.environment, "mock": settings.mock}

    @app.get("/ready", tags=["meta"])
    async def ready() -> dict:
        try:
            await store.ping()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Security storage is unavailable") from exc
        return {"status": "ready"}

    @app.post("/v1/pin/verify", response_model=VerifyResponse, tags=["pin"])
    async def verify_pin(body: PinVerifyRequest, identity: str = Depends(guard)) -> VerifyResponse:
        require_consent(body.consent)
        try:
            pin = normalize_pin(body.pin, settings.strict_pin_format)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        result = await kra.check_pin(pin)
        log.info("pin_verify found=%s pin=%s caller=%s", result.found, mask_pin(pin), identity)
        return to_response(result)

    @app.post("/v1/pin/verify-by-id", response_model=VerifyResponse, tags=["pin"])
    async def verify_pin_by_id(body: PinByIdRequest, identity: str = Depends(guard)) -> VerifyResponse:
        require_consent(body.consent)
        result = await kra.check_pin_by_id(body.taxpayer_id, body.taxpayer_type.upper())
        log.info("pin_by_id found=%s caller=%s", result.found, identity)  # never log the ID
        return to_response(result)

    @app.post("/v1/kra/{service_id}", tags=["kra-services"])
    async def invoke_kra_service(
        service_id: str,
        body: dict,
        identity: str = Depends(guard),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict:
        if service_id not in service_mutates:
            raise HTTPException(status_code=404, detail="Unknown KRA service")
        if body.get("consent") is not True:
            raise HTTPException(status_code=400, detail="consent must be true")
        payload = body.get("payload")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="payload must be a JSON object")
        if service_mutates[service_id] and (not idempotency_key or not 16 <= len(idempotency_key) <= 128):
            raise HTTPException(
                status_code=400,
                detail="Idempotency-Key (16-128 chars) is required for this operation",
            )
        cache_key = (
            hashlib.sha256(f"{identity}:{service_id}:{idempotency_key}".encode()).hexdigest()
            if idempotency_key
            else None
        )
        fingerprint = payload_fingerprint(payload)
        if settings.mock:
            raise HTTPException(
                status_code=501,
                detail="No fabricated filing/payment mock exists; configure a verified KRA sandbox mapping",
            )
        if cache_key:
            return await execute_idempotently(
                cache_key,
                fingerprint,
                lambda: kra.invoke_catalog_service(
                    service_id, payload, retry_auth=not service_mutates[service_id]
                ),
                {
                    "upstream_timeout",
                    "upstream_unreachable",
                    "upstream_error",
                    "kra_upstream_error",
                    "unexpected_response",
                },
            )
        return await kra.invoke_catalog_service(service_id, payload)

    @app.post("/v1/etims/oscu/{operation_id}", tags=["etims-oscu"])
    async def invoke_direct_oscu(
        operation_id: str,
        body: dict,
        identity: str = Depends(guard),
        x_etims_tin: str | None = Header(default=None, alias="X-ETIMS-TIN"),
        x_etims_bhf_id: str | None = Header(default=None, alias="X-ETIMS-BHF-ID"),
        x_etims_cmc_key: str | None = Header(default=None, alias="X-ETIMS-CMC-KEY"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict:
        if oscu is None:
            raise HTTPException(status_code=503, detail="Direct eTIMS OSCU adapter is disabled")
        if body.get("consent") is not True:
            raise HTTPException(status_code=400, detail="consent must be true")
        payload = body.get("payload")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="payload must be a JSON object")
        operation = oscu.operation(operation_id)
        if operation is None:
            raise HTTPException(status_code=404, detail="Unknown direct OSCU operation")
        if operation.get("mutates") and (not idempotency_key or not 16 <= len(idempotency_key) <= 128):
            raise HTTPException(status_code=400, detail="Idempotency-Key (16-128 chars) is required")
        tenant_headers = {
            "tin": x_etims_tin or "",
            "bhfId": x_etims_bhf_id or "",
            "cmcKey": x_etims_cmc_key or "",
        }
        cache_material = json.dumps(
            {
                "identity": identity,
                "operation": operation_id,
                "idempotency_key": idempotency_key,
                "tenant": tenant_headers,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        cache_key = hashlib.sha256(cache_material.encode()).hexdigest() if idempotency_key else None
        fingerprint = payload_fingerprint(payload)
        if cache_key:
            return await execute_idempotently(
                cache_key,
                fingerprint,
                lambda: oscu.invoke(
                    operation_id, payload, tenant_headers, retry_auth=not operation.get("mutates", False)
                ),
                {
                    "oscu_outcome_unknown",
                    "oscu_upstream_unreachable",
                    "oscu_upstream_error",
                    "oscu_unexpected_response",
                },
            )
        return await oscu.invoke(operation_id, payload, tenant_headers)

    return app
