"""Entry point: `uvicorn app.asgi:app`. Fails fast on unsafe configuration."""

import logging

from .main import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = create_app()
