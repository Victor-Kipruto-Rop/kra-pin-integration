from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .config import Settings, load_settings, validate_settings
from .kra_client import KraClient, KraError, MockKraClient, PinResult
from .ratelimit import RateLimiter
from .schemas import PinByIdRequest, PinVerifyRequest, VerifyResponse, normalize_pin
from .security import api_key_matches, mask_pin

log = logging.getLogger("kra_pin")


def create_app(settings: Settings | None = None, client=None) -> FastAPI:
    settings = settings or load_settings()
    validate_settings(settings)
    limiter = RateLimiter(settings.rate_limit_per_minute)
    idempotency_cache: dict[str, tuple[str, dict]] = {}
    idempotency_lock = asyncio.Lock()
    service_mutates = {"authorization": False, "pin-checker-by-pin": False, "pin-checker-by-id": False, "fetch-taxpayer-obligations": False, "know-kra-tax-service-office": False, "tax-compliance-certificate-application": True, "tax-compliance-certificate-checker": False, "vat-exemption-checker": False, "it-exemption-checker": False, "nil-return-filing": True, "tot-return-filing": True, "income-tax-withholding-prn-generation": True, "vat-withholding-prn-generation": True, "rental-withholding-prn-generation": True, "excise-license-checker-by-pin": False, "excise-license-checker-by-certificate-number": False, "customs-declaration-status-checker": False, "customs-tax-calculator": False, "import-certificate-checker-by-pin": False, "import-certificate-checker-by-cert-number": False, "invoice-checker": False, "etims-oscu-integrator-automated-testing": True}
    kra = client or (MockKraClient() if settings.mock else KraClient(settings))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await kra.aclose()

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
            allow_headers=["X-API-Key", "Content-Type"],
        )

    async def guard(request: Request, x_api_key: str | None = Header(default=None)) -> str:
        if settings.proxy_api_keys:
            if not x_api_key or not api_key_matches(x_api_key, settings.proxy_api_keys):
                raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
            identity = hashlib.sha256(x_api_key.encode()).hexdigest()[:16]
        else:
            identity = request.client.host if request.client else "anonymous"
        if not limiter.allow(identity):
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded", headers={"Retry-After": "60"}
            )
        return identity

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
    async def verify_pin_by_id(
        body: PinByIdRequest, identity: str = Depends(guard)
    ) -> VerifyResponse:
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
        if service_mutates[service_id] and (
            not idempotency_key or not 16 <= len(idempotency_key) <= 128
        ):
            raise HTTPException(
                status_code=400,
                detail="Idempotency-Key (16-128 chars) is required for this operation",
            )
        cache_key = hashlib.sha256(
            f"{identity}:{service_id}:{idempotency_key}".encode()
        ).hexdigest() if idempotency_key else None
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        if settings.mock:
            raise HTTPException(
                status_code=501,
                detail="No fabricated filing/payment mock exists; configure a verified KRA sandbox mapping",
            )
        if cache_key:
            # Serializes same-process duplicate submissions. Production must use a shared
            # durable store (Redis/database) to coordinate multiple workers/replicas.
            async with idempotency_lock:
                prior = idempotency_cache.get(cache_key)
                if prior:
                    if prior[0] != fingerprint:
                        raise HTTPException(status_code=409, detail="Idempotency-Key was already used with a different payload")
                    return prior[1]
                result = await kra.invoke_catalog_service(service_id, payload)
                idempotency_cache[cache_key] = (fingerprint, result)
                return result
        return await kra.invoke_catalog_service(service_id, payload)

    return app
