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


## Local CI execution path

- Added `scripts/ci-local.sh` to run catalog validation, OSCU manifest parity, Python reference/API tests, and the Go, Java, JavaScript, TypeScript, PHP and Ruby suites locally.
- Added root `Makefile` targets for validation, each language test suite, full matrix testing and safe OSCU dry-run invocation.
- Added [local CI and release validation instructions](docs/ci-local-validation.md), including GitLab CI fallback and the distinction between code tests and KRA sandbox evidence.
- The local runner has been committed but has not been executed in this environment; the container could not resolve github.com to clone the repository. Do not report its tests as passing until run on a machine or CI runner with the required runtimes installed.

## Remaining external and release blockers

- GitHub Actions runs still fail before any job steps execute (empty step lists); billing/runner provisioning must be resolved or the GitLab pipeline must be run after importing/mirroring the repository.
- Official KRA documentation distinguishes the eTIMS OSCU/VSCU system-to-system integration and certification process from the separate GavaConnect API catalog. The 23-operation sandbox collection in this repository must be checked with KRA to confirm that its host, token route and endpoint inventory are the intended product-specific automated-testing API; it must not be presented as the standard OSCU device API without that confirmation.
- KRA-issued credentials, approved taxpayer test data, complete official per-service contracts, live sandbox evidence, certification, privacy/legal review and independent security review remain external requirements.

## Idempotency transition hardening

- Completion and unknown-outcome transitions now require an existing pending reservation with the exact matching payload fingerprint.
- The in-memory store enforces the same ownership rule as Redis.
- Redis transitions use atomic Lua compare-and-set operations, preventing a stale worker or mismatched request from overwriting a completed, unknown, or differently-owned record.
- Regression tests cover attempted overwrites after completion for both storage implementations.
- These changes are committed but have not yet been executed in a functioning test runner; do not treat the regression tests as passing until CI or the local matrix runs.


## Mutation retry and ambiguous-outcome safeguards

- Catalog and direct OSCU mutation routes disable automatic request replay after HTTP 401; read-only operations retain the configurable token-refresh retry behavior.
- Mutating catalog operations mark timeout, transport failure, upstream 5xx, malformed responses and unexpected exceptions as unknown outcomes. The idempotency key remains blocked until reconciliation.
- Direct OSCU mutations apply the same fail-closed policy for timeout, transport failure, upstream 5xx and malformed responses.
- Added API regression coverage for ambiguous catalog and OSCU mutation outcomes, unexpected exceptions, definitive rejection handling, and disabled mutation auth replay.
- These tests are committed but have **not** been executed in a functioning test runner. Do not interpret committed tests as passing evidence.
- KRA's exact semantics for 401, 429, 5xx and operation-level rejection still require written confirmation. The adapter intentionally avoids automatic mutation replay where that guarantee is absent.

- The standalone direct OSCU client used by the guarded sandbox runner also enforces this rule internally: mutating manifest operations do not replay after 401 even when a caller uses the default client options; read-only operations may refresh and retry.
- Added a transport-mocked regression test proving a mutating OSCU operation receives only one POST after 401.


## Cross-language OSCU ambiguous-outcome parity

- Go, Java, JavaScript, TypeScript, PHP, Ruby and the standalone Python SDK now treat mutation transport failures, HTTP 5xx responses and malformed/unreadable success responses as unknown outcomes requiring reconciliation.
- Definitive non-5xx HTTP rejections remain explicit request rejections; automatic retry is not performed by these SDK clients.
- Added regression tests for the Python, Go, JavaScript, TypeScript, PHP and Ruby clients. Java's production code path has been hardened, but a transport-mocked regression test is still outstanding.
- Full seven-runtime tests remain unexecuted; no language-level change in this section is considered verified until the local matrix or GitLab CI completes successfully.

- Python GavaConnect and direct OSCU token-acquisition failures now use distinct error codes from operation-request failures. This avoids incorrectly marking an idempotency key unknown when authentication failed before the mutating request was submitted.
