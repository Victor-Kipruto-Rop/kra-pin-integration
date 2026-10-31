from __future__ import annotations

import hmac


def api_key_matches(provided: str, valid_keys: tuple[str, ...]) -> bool:
    """Constant-time comparison against every configured key."""
    matched = False
    for key in valid_keys:
        if hmac.compare_digest(provided.encode(), key.encode()):
            matched = True
    return matched


def mask_pin(pin: str) -> str:
    """A12*****89G-style masking for logs. Never log full PINs or ID numbers."""
    if len(pin) <= 5:
        return "*" * len(pin)
    return pin[:3] + "*" * (len(pin) - 5) + pin[-2:]
