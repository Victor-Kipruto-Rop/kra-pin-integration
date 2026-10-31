# KRA PIN Integration — Multi-language templates

> **Release status: NOT PRODUCTION READY — validation required.** See [Production Readiness](PRODUCTION_READINESS.md) for release gates and evidence requirements.


Unofficial, server-side integration templates for verifying KRA PINs through the official GavaConnect developer gateway ([developer.go.ke](https://developer.go.ke)). This project is community software and is not affiliated with or endorsed by the Kenya Revenue Authority. It never scrapes iTax. Check current KRA terms and API documentation before going live.

## Supported server implementations

| Language | Directory | Technology |
|---|---|---|
| Python (reference) | `server/` | FastAPI, httpx |
| Go | `languages/go/` | Go 1.22+, net/http |
| Java | `languages/java/` | Java 21, Spring Boot |
| JavaScript | `languages/javascript/` | Node.js 20+, native HTTP/fetch |
| TypeScript | `languages/typescript/` | Node.js 20+, strict TypeScript |
| PHP | `languages/php/` | PHP 8.2+, cURL |
| Ruby | `languages/ruby/` | Ruby 3.3+, Rack |

Every language is an independent server application and calls KRA directly. The other services do not proxy through Python.

## Shared API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health and environment |
| POST | `/v1/pin/verify` | Verify PIN |
| POST | `/v1/pin/verify-by-id` | Lookup PIN by taxpayer ID |

Protected routes require `X-API-Key` and `consent: true` by default. Success response shape:

```json
{"found":true,"pin":"A000000000B","taxpayer_name":"DEMO T*****","environment":"sandbox","mock":true,"raw":null}
```

Example request:

```bash
curl -X POST http://localhost:8000/v1/pin/verify \
  -H "X-API-Key: dev-key" -H "Content-Type: application/json" \
  -d '{"pin":"A000000000B","consent":true}'
```

## Run locally

Start with one implementation at a time. Set `KRA_MOCK=true` and a non-empty `PROXY_API_KEYS`. In mock mode, `A000000000B` is the demo PIN and `00000000` is the demo taxpayer ID.

- Python: follow [docs/getting-started.md](docs/getting-started.md).
- Go: `cd languages/go && go test ./... && go run .`
- Java: `cd languages/java && mvn test && mvn spring-boot:run`
- JavaScript: `cd languages/javascript && npm test && npm start`
- TypeScript: `cd languages/typescript && npm install && npm test && npm start`
- PHP: `cd languages/php && composer install && composer test`; serve with `php -S 127.0.0.1:8000 -t public`.
- Ruby: `cd languages/ruby && bundle install && bundle exec rspec && bundle exec rackup`.

Copy each language's `.env.example` to `.env` or export variables in your shell/deployment secret manager. Never commit real credentials.

## KRA setup and verification

1. Register at [developer.go.ke](https://developer.go.ke), create an application and subscribe to PIN Checker and, if required, PIN Checker By ID.
2. Configure sandbox consumer credentials securely and set `KRA_MOCK=false`.
3. Confirm success/not-found response shapes with current KRA sandbox data.
4. Request production access from KRA and use separately issued production credentials.

The Python reference currently documents response mappings such as `PINDATA`, `KRAPIN`, `Name` and error code `30002` as assumptions to confirm. New language implementations use the same cautious mapping. Do not claim sandbox or production verification until it has actually succeeded.

## Security and limitations

- Consumer keys/secrets belong only on the server. Never embed them in browser or mobile applications.
- Use TLS, high-entropy proxy API keys, secret management and rotation.
- Do not log full PINs, national IDs, credentials, tokens or raw KRA payloads.
- Collect and validate taxpayer consent in the calling application.
- In-memory token caches and rate limiters are process-local. Use Redis or gateway enforcement for multiple replicas.
- A PIN match is not proof of identity or tax compliance.
- Mock tests are not KRA certification. Production use is subject to KRA approval and current terms.
- The project scope is PIN Checker and PIN Checker By ID, not eTIMS/TCC or other KRA APIs.

## Documentation

- [Architecture](docs/architecture.md)
- [OpenAPI contract](contracts/openapi.yaml)
- [Language guides](docs/language-guides/README.md)
- [Security](docs/security.md)
- [Production readiness assessment](PRODUCTION_READINESS.md)
- [Compliance](docs/compliance.md)
- [Repository audit](AUDIT.md)
- [Implementation plan](IMPLEMENTATION_PLAN.md)
- [Feature parity](FEATURE_PARITY.md)

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). MIT license.
