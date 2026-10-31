# Multi-language implementation plan

Python remains the reference service under server/. Independent services under languages/ communicate directly with KRA, never through Python. All expose GET /health, POST /v1/pin/verify and POST /v1/pin/verify-by-id; protected routes use X-API-Key and require consent=true by default. Success fields: found, pin, taxpayer_name, environment, mock, raw. Errors use {error:{code,message}} for upstream failures.

Implementation order: shared contract and docs; Go and Java; JavaScript and TypeScript; PHP and Ruby; cross-language fixtures, Docker, CI and security review. Sandbox/production verification must be reported separately from mock tests.
