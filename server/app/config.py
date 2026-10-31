"""Runtime configuration, read from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass

SANDBOX_URL = "https://sbx.kra.go.ke"
PRODUCTION_URL = "https://api.kra.go.ke"
ENVIRONMENTS = ("sandbox", "production")


class ConfigError(RuntimeError):
    """Raised at startup when the configuration is unsafe or incomplete."""


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    environment: str = "sandbox"
    pin_key: str = ""
    pin_secret: str = ""
    pin_by_id_key: str = ""
    pin_by_id_secret: str = ""
    mock: bool = False
    timeout_seconds: float = 15.0
    strict_pin_format: bool = False
    include_raw: bool = False
    require_consent: bool = True
    rate_limit_per_minute: int = 30
    proxy_api_keys: tuple[str, ...] = ()
    allow_unauthenticated: bool = False
    cors_origins: tuple[str, ...] = ()
    etims_oscu_enabled: bool = False
    etims_oscu_consumer_key: str = ""
    etims_oscu_consumer_secret: str = ""
    etims_oscu_app_id: str = ""
    idempotency_redis_url: str = ""
    idempotency_encryption_key: str = ""
    idempotency_ttl_seconds: int = 604800

    @property
    def base_url(self) -> str:
        return PRODUCTION_URL if self.environment == "production" else SANDBOX_URL

    @property
    def by_id_credentials(self) -> tuple[str, str]:
        """PIN-by-ID credentials, falling back to the PIN-checker app's keys."""
        if self.pin_by_id_key and self.pin_by_id_secret:
            return self.pin_by_id_key, self.pin_by_id_secret
        return self.pin_key, self.pin_secret


def load_settings() -> Settings:
    environment = os.environ.get("KRA_ENVIRONMENT", "sandbox").strip().lower()
    return Settings(
        environment=environment,
        pin_key=os.environ.get("KRA_PIN_CONSUMER_KEY", ""),
        pin_secret=os.environ.get("KRA_PIN_CONSUMER_SECRET", ""),
        pin_by_id_key=os.environ.get("KRA_PIN_BY_ID_CONSUMER_KEY", ""),
        pin_by_id_secret=os.environ.get("KRA_PIN_BY_ID_CONSUMER_SECRET", ""),
        mock=_env_bool("KRA_MOCK", False),
        timeout_seconds=float(os.environ.get("KRA_TIMEOUT_SECONDS", "15")),
        # Sandbox sample data may not follow the production PIN shape, so strict
        # format checking defaults to on only in production.
        strict_pin_format=_env_bool("STRICT_PIN_FORMAT", environment == "production"),
        include_raw=_env_bool("INCLUDE_RAW_RESPONSE", False),
        require_consent=_env_bool("REQUIRE_CONSENT", True),
        rate_limit_per_minute=int(os.environ.get("RATE_LIMIT_PER_MINUTE", "30")),
        proxy_api_keys=_env_list("PROXY_API_KEYS"),
        allow_unauthenticated=_env_bool("ALLOW_UNAUTHENTICATED", False),
        cors_origins=_env_list("CORS_ORIGINS"),
        etims_oscu_enabled=_env_bool("ETIMS_OSCU_ENABLED", False),
        etims_oscu_consumer_key=os.environ.get("ETIMS_OSCU_CONSUMER_KEY", ""),
        etims_oscu_consumer_secret=os.environ.get("ETIMS_OSCU_CONSUMER_SECRET", ""),
        etims_oscu_app_id=os.environ.get("ETIMS_OSCU_APP_ID", ""),
        idempotency_redis_url=os.environ.get("IDEMPOTENCY_REDIS_URL", ""),
        idempotency_encryption_key=os.environ.get("IDEMPOTENCY_ENCRYPTION_KEY", ""),
        idempotency_ttl_seconds=int(os.environ.get("IDEMPOTENCY_TTL_SECONDS", "604800")),
    )


def validate_settings(s: Settings) -> None:
    problems: list[str] = []
    if s.environment not in ENVIRONMENTS:
        problems.append(f"KRA_ENVIRONMENT must be one of {ENVIRONMENTS}")
    if s.mock and s.environment == "production":
        problems.append("KRA_MOCK cannot be enabled in production")
    if not s.mock and not (s.pin_key and s.pin_secret):
        problems.append(
            "KRA_PIN_CONSUMER_KEY and KRA_PIN_CONSUMER_SECRET are required "
            "(or set KRA_MOCK=true for a local trial without credentials)"
        )
    if not s.proxy_api_keys and not s.allow_unauthenticated:
        problems.append(
            "PROXY_API_KEYS is empty; set at least one key "
            "(ALLOW_UNAUTHENTICATED=true is for local development only)"
        )
    if s.allow_unauthenticated and s.environment == "production":
        problems.append("ALLOW_UNAUTHENTICATED cannot be enabled in production")
    if s.etims_oscu_enabled:
        if s.environment != "sandbox":
            problems.append("Direct eTIMS OSCU is sandbox-only until KRA provides production endpoint details and approval")
        if not (s.etims_oscu_consumer_key and s.etims_oscu_consumer_secret and s.etims_oscu_app_id):
            problems.append("ETIMS_OSCU_CONSUMER_KEY, ETIMS_OSCU_CONSUMER_SECRET and ETIMS_OSCU_APP_ID are required when ETIMS_OSCU_ENABLED=true")
    if problems:
        raise ConfigError("; ".join(problems))
