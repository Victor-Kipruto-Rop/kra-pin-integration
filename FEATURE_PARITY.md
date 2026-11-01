# Feature parity and verification status

The following is an honest implementation inventory, not a claim that all runtimes are production-certified.

| Capability | Python reference | Go | Java | JavaScript | TypeScript | PHP | Ruby |
|---|---|---|---|---|---|---|---|
| Health endpoint | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| 22-service catalog dispatcher | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| PIN Checker and PIN Checker BY ID service IDs | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| API-key authentication | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Consent enforcement | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Mock mode | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Sandbox/production URL selection | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| OAuth client-credentials flow | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| In-memory token cache | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Rate limiting | In-memory | In-memory | In-memory | In-memory | In-memory | Local file lock | In-memory |
| Upstream timeout configured | Yes | 15s client | 5s connect / 15s read | 15s | 15s | 15s cURL | 5s connect / 15s read |
| Catalog dispatcher 401 handling | Read-only retry only; no mutation replay | Same | Same | Same | Same | Same | Same |
| GET query / POST JSON upstream forwarding | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Canonical payload fingerprint for idempotency | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Idempotency payload conflict response (409) | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| OAuth bearer token kept server-side | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Precise upstream error mapping | Yes | Partial | Partial | Partial | Partial | Partial | Partial |
| Catalog coverage tests | 22 route registrations | 22 IDs + unmapped 501 | 22 IDs | 22 IDs | 22 IDs | Shared JSON catalog | 22 IDs |
| Dockerfile | Yes | Yes | Yes | Yes | Yes | Yes | Yes |

## Catalog dispatcher behavior
- Public proxy calls use POST consistently; configured KRA upstream methods support GET (query parameters) or POST (JSON body). Mutating operations are blocked if configured as GET.
- Authorization obtains the upstream bearer token internally and returns status metadata only; it does not return the raw token.
- All seven implementations expose POST /v1/kra/{service-id} for the canonical 22-service catalog.
- All require consent; mutating services require Idempotency-Key.
- Upstream paths/methods are explicitly configured; missing mappings return 501 instead of guessed KRA calls.
- The eTIMS automated-testing catalog service uses its official GavaConnect mapping; direct OSCU device protocol is explicitly out of scope for this generic catalog dispatcher.
- Mock mode does not fabricate successful filing, PRN, TCC application or eTIMS responses.

## Additional hardening applied in this branch
- Go, Java, JavaScript and TypeScript validate sandbox/production configuration; production mode rejects mock mode.
- Non-mock startup requires KRA credentials in all six additional language templates.
- Node.js, TypeScript, PHP and Ruby enforce a 64 KiB request-body cap.
- Go, Java, Node.js and TypeScript set explicit inbound/upstream timeouts.
- Docker ignore files exclude local environment files and build artifacts.

## Required before production
1. Populate and sandbox-verify all service paths, methods, payloads and response schemas from current official KRA specifications.
2. Standardize timeout, connection, upstream 400/401/403/404/429/5xx and malformed-body mappings; verify idempotency replay and timeout reconciliation semantics.
3. Confirm actual KRA sandbox response bodies and not-found codes for all 22 services.
4. Expand each language's tests to cover authentication, consent, validation, rate limiting, token caching/refresh, timeout and response parsing.
5. Configure shared durable rate limiting, token caching and idempotency for horizontally scaled deployments.
6. Run all language build/test workflows and security scanning on an available CI runner.
7. Conduct a security review and KRA sandbox verification.

A successful mock response is not proof of upstream connectivity. This status file deliberately distinguishes implemented route scaffolding from verified production behavior.


## Direct eTIMS OSCU SDK parity

The direct OSCU protocol is a separate integration surface from the 22-service GavaConnect dispatcher. The feature branch now includes server-side clients in Python, Go, Java, JavaScript, TypeScript, PHP and Ruby. Each loads a packaged copy of the canonical 23-operation manifest; the contract validator checks parity for all copies and the OpenAPI document. Each client uses the fixed KRA sandbox host, HTTP Basic token acquisition, bearer authentication, required tenant context, explicit confirmation for provisionally mutating operations and no automatic mutation retries. These SDKs remain unverified against live KRA credentials and do not imply certification.

The Python FastAPI adapter additionally uses Redis-backed distributed rate limiting and idempotency when configured. Completed response bodies are encrypted using the configured Fernet key. Other independent GavaConnect server implementations still require shared state/gateway enforcement before multi-replica production.


## Catalog mutation retry and idempotency safeguards

- Python, Go, Java, JavaScript, TypeScript, PHP and Ruby catalog dispatchers now avoid automatic 401 replay for mutating services.
- Mutating requests with idempotency keys reserve a pending state before upstream submission. Duplicate in-flight requests are blocked; completed requests replay their cached response; ambiguous transport failures, 5xx responses and malformed responses are held as unknown outcomes and require reconciliation.
- Definitive non-5xx upstream rejections release the reservation where the implementation can identify the upstream status. Some language adapters conservatively retain an unknown state for errors whose pre-send versus post-send phase cannot be reliably distinguished.
- This is process-local state in most language templates; PHP uses a local filesystem lock/state file. These mechanisms prevent common same-process duplicate submissions but are **not** a substitute for a shared durable idempotency store across replicas or hosts.
- Python FastAPI remains the reference implementation for Redis-backed cross-worker state and encrypted completed-response caching. All language implementations still require test execution and independent review before production.
