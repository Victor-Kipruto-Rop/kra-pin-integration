# Feature parity and verification status

The following is an honest implementation inventory, not a claim that all runtimes are production-certified.

| Capability | Python reference | Go | Java | JavaScript | TypeScript | PHP | Ruby |
|---|---|---|---|---|---|---|---|
| Health endpoint | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| PIN and PIN-by-ID routes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| API-key authentication | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Consent enforcement | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Mock mode | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Sandbox/production URL selection | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| OAuth client-credentials flow | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| In-memory token cache | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Rate limiting | In-memory | In-memory | In-memory | In-memory | In-memory | Local file lock | In-memory |
| Upstream timeout configured | Yes | 15s client | 5s connect / 15s read | 15s | 15s | 15s cURL | 5s connect / 15s read |
| 401 token refresh/retry | Yes | Not yet | Not yet | Not yet | Not yet | Not yet | Not yet |
| Precise upstream error mapping | Yes | Partial | Partial | Partial | Partial | Partial | Partial |
| Automated tests | API + mocked client | Mock lookup | Basic context test | Mock lookup | Mock lookup | Mock lookup | Health |
| Dockerfile | Yes | Yes | Yes | Yes | Yes | Yes | Yes |

## Additional hardening applied in this branch
- Go, Java, JavaScript and TypeScript validate sandbox/production configuration; production mode rejects mock mode.
- Non-mock startup requires KRA credentials in all six additional language templates.
- Node.js, TypeScript, PHP and Ruby enforce a 64 KiB request-body cap.
- Go, Java, Node.js and TypeScript set explicit inbound/upstream timeouts.
- Docker ignore files exclude local environment files and build artifacts.

## Required before production
1. Add and test 401 token invalidation and one retry in the six additional languages; Python already implements this.
2. Standardize timeout, connection, upstream 429, upstream 5xx and malformed-body mappings.
3. Confirm actual KRA sandbox response bodies and not-found codes; the Python reference labels these as assumptions.
4. Expand each language's tests to cover authentication, consent, validation, rate limiting, token caching/refresh, timeout and response parsing.
5. Configure shared rate limiting and token caching for horizontally scaled deployments.
6. Run all language build/test workflows and security scanning on an available CI runner.
7. Conduct a security review and KRA sandbox verification.

A successful mock response is not proof of upstream connectivity. This status file deliberately distinguishes implemented route scaffolding from verified production behavior.
