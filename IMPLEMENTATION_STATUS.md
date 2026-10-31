# Implementation status

## Delivered on `feature/multilanguage-sdk-expansion`
- Independent Go, Java/Spring Boot, JavaScript, TypeScript, PHP and Ruby service templates alongside the Python reference.
- Shared OpenAPI contract and canonical 22-service catalog with stable service IDs and mutability metadata.
- Generic POST /v1/kra/{service-id} dispatcher in Python, Go, Java, JavaScript, TypeScript, PHP and Ruby.
- Configurable upstream path/method mappings (GET query forwarding and POST JSON forwarding), OAuth token handling, one-time 401 refresh/retry, consent enforcement and idempotency-key requirements for mutating operations.
- Same-process idempotency replay with canonical payload fingerprints and HTTP 409 on key reuse with a different payload.
- Authorization endpoint keeps the KRA bearer token server-side and returns status metadata only.
- Complete 21-service upstream mapping template, per-service contract-readiness register and fail-closed production configuration preflight.
- eTIMS OSCU automated-testing catalog entry registered and dispatched through the GavaConnect adapter; direct OSCU device-protocol integration remains a separate certified workstream.
- Per-language tests asserting the 22-service catalog is present.
- Multi-language CI workflow with manual dispatch and read-only repository permissions.
- Dependabot coverage for Python, Go, Java, JavaScript, TypeScript, PHP, Ruby and GitHub Actions.
- Docker ignore rules to exclude local environment files and build artifacts from build contexts.
- Request-body limits for Node.js, TypeScript, PHP and Ruby; HTTP server/read timeouts for Go, Java, Node.js and TypeScript.
- Production-readiness assessment, release evidence checklist and updated README status notice.

## Verification state
**NOT PRODUCTION READY.** This branch has not completed all runtime builds and tests in a functioning CI runner. The previously inspected Actions jobs ended before workflow steps executed, and no live KRA credentials were supplied. No real KRA sandbox or production API call has been verified by this work.

## Remaining release blockers
1. Run and pass the complete CI matrix for all seven implementations, including the Python reference.
2. Complete the shared contract-test suite across all seven runtimes, including GET/POST query/body behavior, idempotency replay/conflicts, rate limits, token expiry and upstream failures.
3. Obtain the authenticated KRA specifications for the 21 non-authorization operations, then populate the endpoint mappings, methods, OAuth scopes, request/response schemas and error mappings; confirm eTIMS OSCU separately.
4. Add per-service request/response schemas and normalize upstream 400/401/403/404/429/5xx and malformed-response handling to a single documented contract.
5. Confirm all 22 KRA hosts, payloads, success response fields, not-found semantics, token behavior and mutation/replay behavior with current official documentation and approved sandbox credentials.
6. Replace per-process/per-host rate limiting, token caching and idempotency with shared durable infrastructure (for example Redis) before multi-instance deployment.
7. Complete dependency, secret, container and static-analysis scans; remediate findings and obtain independent security review.
8. Complete privacy/legal review, retention controls, operational monitoring, alerting, incident response and recovery testing.
9. Obtain KRA production approval and deployment-specific sign-off.

## Release policy
Do not merge as production-ready or deploy real taxpayer data until all release gates in [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) are evidenced for the exact release commit. Mock-mode tests are not production verification.


## Direct OSCU and shared-state update

- Seven language-specific direct OSCU sandbox SDK clients now exist and use the same 23-operation manifest.
- Added a language-neutral direct OSCU OpenAPI document and CI manifest parity validation.
- Python FastAPI uses Redis-backed distributed rate limiting and idempotency when configured; cached KRA responses are Fernet-encrypted, tenant-scoped OSCU keys prevent cross-tenant replay, and the readiness endpoint checks security-store availability.
- Added a Redis-backed local Docker Compose stack and production preflight requirements.
- These changes have not passed a functioning CI runner yet. Live KRA sandbox testing, formal schemas and certification remain pending.
