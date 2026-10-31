# Implementation status

## Delivered on `feature/multilanguage-sdk-expansion`
- Independent Go, Java/Spring Boot, JavaScript, TypeScript, PHP and Ruby service templates alongside the Python reference.
- Shared OpenAPI contract, examples, per-language Dockerfiles, environment examples and basic tests.
- Multi-language CI workflow with manual dispatch and read-only repository permissions.
- Dependabot coverage for Python, Go, Java, JavaScript, TypeScript, PHP, Ruby and GitHub Actions.
- Docker ignore rules to exclude local environment files and build artifacts from build contexts.
- Request-body limits for Node.js, TypeScript, PHP and Ruby; HTTP server/read timeouts for Go, Java, Node.js and TypeScript.
- Production-readiness assessment, release evidence checklist and updated README status notice.

## Verification state
**NOT PRODUCTION READY.** This branch has not completed all runtime builds and tests in a functioning CI runner. The previously inspected Actions jobs ended before workflow steps executed, and no live KRA credentials were supplied. No real KRA sandbox or production API call has been verified by this work.

## Remaining release blockers
1. Run and pass the complete CI matrix for all seven implementations, including the Python reference.
2. Add a shared contract-test suite that runs identical auth, consent, input, not-found and upstream-error cases against every language.
3. Implement and test consistent one-time token refresh/retry after KRA 401 responses.
4. Normalize upstream 400/401/403/404/429/5xx and malformed-response handling to a single documented contract.
5. Confirm KRA hosts, payloads, success response fields, not-found semantics and token behavior with current official documentation and approved sandbox credentials.
6. Replace per-process/per-host rate limiting and token caching with shared infrastructure before horizontal scaling.
7. Complete dependency, secret, container and static-analysis scans; remediate findings and obtain independent security review.
8. Complete privacy/legal review, retention controls, operational monitoring, alerting, incident response and recovery testing.
9. Obtain KRA production approval and deployment-specific sign-off.

## Release policy
Do not merge as production-ready or deploy real taxpayer data until all release gates in [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) are evidenced for the exact release commit. Mock-mode tests are not production verification.
