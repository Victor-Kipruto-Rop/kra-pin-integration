# Repository audit

Baseline main: c8d809e87466c682106e8f9ac1c7d4548b71492e. Python FastAPI/httpx service provides PIN routes, GavaConnect catalog dispatch and a separate direct OSCU sandbox adapter. The current feature branch adds Redis-backed distributed rate limiting/idempotency, encrypted cached responses, a readiness endpoint, seven direct OSCU SDK clients and a canonical 23-operation manifest/OpenAPI contract. Existing JS/PHP examples are clients, not full server implementations.

Baseline limitations: KRA success response fields and error code 30002 were assumptions in the original Python PIN client and require sandbox confirmation. A PIN match is not identity proof or tax compliance. KRA production access requires separate approval/credentials. The current feature branch extends the baseline with the 22-service GavaConnect catalog, a separate direct OSCU sandbox adapter and seven direct OSCU SDK clients; it does not scrape iTax.


## Current feature-branch additions

The branch adds a canonical 23-operation direct OSCU inventory, OpenAPI description and seven SDK manifest copies with static parity checks. The Python API supports shared Redis rate limiting and idempotency with encrypted response caching when configured. These additions have not yet passed full CI or live KRA sandbox verification; see [production readiness](PRODUCTION_READINESS.md).
