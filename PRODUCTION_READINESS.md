# Production readiness assessment

> **Current release classification: NOT PRODUCTION READY — validation required.**

This project provides seven independent language templates with a shared dispatcher for all 22 KRA developer-catalog services. It is not a KRA-certified product and this repository does not establish that KRA has approved any specific deployment.

## Release gates

A release may be marked production-ready only when every gate below has recorded evidence for the exact commit being released.

| Gate | Required evidence | Current state |
|---|---|---|
| Runtime builds | Clean build for Python, Go, Java, JavaScript, TypeScript, PHP and Ruby | Not verified |
| Automated tests | All unit, integration, contract and negative tests pass | Not verified |
| Contract parity | All runtimes pass the same OpenAPI contract suite | Not verified |
| KRA sandbox | Approved credentials; success, not-found, invalid-input, expired-token and upstream-error cases captured with sensitive data redacted | Not verified |
| KRA production approval | KRA production access granted for the application and APIs in use | Not verified |
| Secrets | Production secrets stored in secret manager, rotated, least-privilege, never committed | Deployment-specific |
| Privacy | Lawful basis, consent wording, retention, data-subject process and Data Protection Act review approved | Not verified |
| Security | SAST, dependency, container and secret scans pass; independent security review completed | Not verified |
| Operations | TLS, monitoring, alerting, incident response, backups and tested recovery | Deployment-specific |
| Scale | Shared rate limiting/token strategy; load and concurrency tests pass | Not verified |
| Release control | Protected branch, reviewed PR, passing CI and approved production environment | Not verified |

## What this repository currently does not prove

- A mock lookup is not a real KRA API call. Mock mode deliberately returns 501 for unimplemented catalog services rather than fabricating successful filing, PRN or certificate responses.
- A green local test is not KRA certification or production approval.
- The exact upstream path, HTTP method, scope, request fields, response fields, not-found codes and authentication behavior for each of the 22 services must be confirmed against current official KRA specifications and sandbox.
- The Python FastAPI API now supports Redis-backed distributed rate limiting and durable idempotency reservations. Completed responses are Fernet-encrypted in Redis; production requires a TLS `rediss://` URL and a valid `IDEMPOTENCY_ENCRYPTION_KEY`. The in-memory fallback is local development/test only. The separate language GavaConnect server templates still use process-local caches/limiters and require shared gateway/state coordination before horizontal scaling.
- The PHP CLI Dockerfile uses PHP's built-in development server; production requires PHP-FPM behind a hardened web server or ingress.
- PHP's local file locks do not coordinate across multiple hosts or containers.
- Catalog idempotency is durable and cross-worker in the Python FastAPI service when Redis is configured. The separate Go/Java/JavaScript/TypeScript/PHP/Ruby GavaConnect server templates still have process-local or file-local idempotency behavior and are not ready for multi-replica mutating workloads.
- A PIN lookup result is not identity proof, tax compliance proof or a Tax Compliance Certificate.

## Required sign-off record

For each release, attach the commit SHA and evidence for:
1. CI workflow run URLs and all seven runtime test results.
2. Cross-runtime catalog/contract test evidence for all 22 services.
3. KRA sandbox test report with credentials, PINs, taxpayer IDs and personal data redacted.
4. KRA production approval reference (do not publish confidential approval documents).
5. Security scan reports and remediation sign-off.
6. Privacy/legal review sign-off.
7. Deployment architecture, monitoring and recovery test.
8. Named release approver and release date.

## Production configuration preflight
Run `python scripts/validate-production-config.py` in the deployment environment after setting production secrets and all 21 verified service mappings. The script checks configuration completeness and unsafe method/path combinations; it does not prove KRA subscription, sandbox behavior or production approval.

## Safe deployment posture

Run one language implementation per deployment. Use the included PHP container only for local development; build a PHP-FPM production image and web-server/ingress configuration before deploying PHP. Populate every KRA service path/method mapping from the current approved specifications, configure the eTIMS OSCU host separately, and use a shared durable idempotency store for all mutating operations. Set `KRA_ENVIRONMENT=production`, `KRA_MOCK=false`, use separately approved production credentials, terminate TLS at a trusted ingress, and store `PROXY_API_KEYS` in a secret manager. Do not expose consumer credentials to clients. Do not deploy this template unchanged as a multi-replica service until shared rate limiting and token coordination are configured.

**Do not change this assessment to “Production Ready” until all gates are evidenced for the release commit.**
