"""Minimal, non-executing .env loader for local developer tooling.

Only KEY=VALUE assignments are accepted. Values are never expanded or evaluated.
Existing process environment values always take precedence.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import MutableMapping

_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_dotenv(path: Path, environ: MutableMapping[str, str] | None = None) -> list[str]:
    """Load missing variables from *path* and return the names loaded.

    Missing files are ignored. Malformed non-comment lines fail closed with a
    line number only; values are never included in exceptions or output.
    """
    target = os.environ if environ is None else environ
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []

    loaded: list[str] = []
    for line_number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"Invalid .env syntax at line {line_number}")
        key, value = line.split("=", 1)
        key = key.strip()
        if not _KEY.fullmatch(key):
            raise ValueError(f"Invalid .env key at line {line_number}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        elif value.startswith(("'", '"')) or value.endswith(("'", '"')):
            raise ValueError(f"Unclosed .env quote at line {line_number}")
        if key not in target:
            target[key] = value
            loaded.append(key)
    return loaded
