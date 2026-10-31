from __future__ import annotations

import re

from pydantic import BaseModel, Field

_STRICT_PIN = re.compile(r"^[AP]\d{9}[A-Z]$")  # A = individual, P = non-individual
_LOOSE_PIN = re.compile(r"^[A-Z0-9]{9,11}$")


def normalize_pin(pin: str, strict: bool) -> str:
    value = pin.strip().upper()
    if not (_STRICT_PIN if strict else _LOOSE_PIN).fullmatch(value):
        raise ValueError(
            "Invalid PIN format. Expected a letter (A or P), 9 digits and a letter, e.g. A123456789Z"
            if strict
            else "Invalid PIN format"
        )
    return value


class PinVerifyRequest(BaseModel):
    pin: str = Field(max_length=20, examples=["A000000000B"])
    consent: bool = Field(
        default=False,
        description="True when the taxpayer has agreed to this verification (Data Protection Act, 2019).",
    )


class PinByIdRequest(BaseModel):
    taxpayer_id: str = Field(min_length=5, max_length=20, pattern=r"^[A-Za-z0-9]+$")
    taxpayer_type: str = Field(default="KE", pattern=r"^[A-Za-z]{2}$")
    consent: bool = False


class VerifyResponse(BaseModel):
    found: bool
    pin: str | None = None
    taxpayer_name: str | None = Field(default=None, description="As returned by KRA (usually masked).")
    environment: str
    mock: bool = False
    raw: dict | None = Field(default=None, description="Only when INCLUDE_RAW_RESPONSE=true.")
