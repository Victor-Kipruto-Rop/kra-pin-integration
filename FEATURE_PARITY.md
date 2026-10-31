# Feature parity

| Feature | Python | Go | Java | JavaScript | TypeScript | PHP | Ruby |
|---|---|---|---|---|---|---|---|
| Health/PIN/PIN-by-ID | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| OAuth/token cache | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Mock/sandbox/production | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| API key/consent/rate limit | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Timeout/error handling | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Tests/Docker | Yes | Added | Added | Added | Added | Added | Added |

New services are independent. KRA response parsing remains subject to sandbox confirmation. Rate limiting and token caches are process-local; use shared controls for multi-replica deployments. Mock tests are not KRA certification.
