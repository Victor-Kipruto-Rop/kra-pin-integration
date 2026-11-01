"""Print the SHAPE (keys and value types, no values) of a KRA response.

Use it to confirm field names against your own sandbox credentials, then open a
PR/issue with the output. It never prints taxpayer data.

    python -m scripts.probe_sandbox pin A000000010Z
    python -m scripts.probe_sandbox id 12345678
"""

import asyncio
import json
import sys

from app.config import load_settings
from app.kra_client import KraClient, KraError


def shape(value):
    if isinstance(value, dict):
        return {k: shape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [shape(v) for v in value[:1]]
    return type(value).__name__


async def main(kind: str, value: str) -> None:
    client = KraClient(load_settings())
    try:
        result = await (client.check_pin(value) if kind == "pin" else client.check_pin_by_id(value))
        print(json.dumps({"found": result.found, "shape": shape(result.raw)}, indent=2))
    except KraError as exc:
        print(json.dumps({"error": exc.code, "shape": shape(exc.payload or {})}, indent=2))
    finally:
        await client.aclose()


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in {"pin", "id"}:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
