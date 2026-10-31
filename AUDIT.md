# Repository audit

Baseline main: c8d809e87466c682106e8f9ac1c7d4548b71492e. Existing Python FastAPI/httpx service provides GET /health, POST /v1/pin/verify and POST /v1/pin/verify-by-id, API-key authentication, consent, process-local rate limiting, mock mode, KRA OAuth token caching, Docker and pytest tests. Existing JS/PHP examples are clients, not full server implementations.

Known limitations: KRA success response fields and error code 30002 are explicitly assumptions in the Python client and require sandbox confirmation. In-memory rate limiting/token caching are per-process. A PIN match is not identity proof or tax compliance. KRA production access requires separate approval/credentials. Scope remains PIN Checker and PIN Checker By ID; no scraping.
