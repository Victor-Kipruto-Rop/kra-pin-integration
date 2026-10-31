# KRA GavaConnect Integration — Seven-language templates

> **Release status: NOT PRODUCTION READY — validation required.** See [Production Readiness](PRODUCTION_READINESS.md) for release gates and evidence requirements.

Unofficial, server-side integration templates for the 22 KRA developer-catalog services through approved GavaConnect integrations ([developer.go.ke](https://developer.go.ke)). This project is community software and is not affiliated with or endorsed by the Kenya Revenue Authority. It never scrapes iTax. Check current KRA terms and API documentation before going live.

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
| POST | `/v1/kra/{service-id}` | Invoke any of the 22 catalog services |
| POST | `/v1/pin/verify` | Legacy convenience route in Python, Java, JavaScript, TypeScript, PHP and Ruby |
| POST | `/v1/pin/verify-by-id` | Legacy convenience route in Python, Java, JavaScript, TypeScript, PHP and Ruby |

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

Start with one implementation at a time. Set `KRA_MOCK=true` and a non-empty `PROXY_API_KEYS`. Legacy PIN convenience routes in Python, Java, JavaScript, TypeScript, PHP and Ruby have demo values `A000000000B` and `00000000`. The Go template exposes the catalog dispatcher; generic catalog calls return 501 in mock mode rather than fabricating results.

- Python: follow [docs/getting-started.md](docs/getting-started.md).
- Go: `cd languages/go && go test ./... && go run .`
- Java: `cd languages/java && mvn test && mvn spring-boot:run`
- JavaScript: `cd languages/javascript && npm test && npm start`
- TypeScript: `cd languages/typescript && npm install && npm test && npm start`
- PHP: `cd languages/php && composer install && composer test`; serve with `php -S 127.0.0.1:8000 -t public`.
- Ruby: `cd languages/ruby && bundle install && bundle exec rspec && bundle exec rackup`.

Copy each language's `.env.example` to `.env` or export variables in your shell/deployment secret manager. Never commit real credentials.

## Complete 22-service GavaConnect catalog

Stable proxy IDs and operation classes are defined in `contracts/kra-services.json`.

| # | KRA service | Proxy service ID | Operation |
|---:|---|---|---|
| 1 | Authorization | authorization | Authentication |
| 2 | PIN Checker by PIN | pin-checker-by-pin | Read |
| 3 | PIN Checker BY ID | pin-checker-by-id | Read |
| 4 | Fetch Taxpayer Obligations | fetch-taxpayer-obligations | Read |
| 5 | Know KRA Tax Service Office | know-kra-tax-service-office | Read |
| 6 | Tax Compliance Certificate Application | tax-compliance-certificate-application | Mutating |
| 7 | Tax Compliance Certificate Checker | tax-compliance-certificate-checker | Read |
| 8 | VAT Exemption Checker | vat-exemption-checker | Read |
| 9 | IT Exemption checker | it-exemption-checker | Read |
| 10 | NIL Return Filling | nil-return-filing | Mutating |
| 11 | TOT Return Filing | tot-return-filing | Mutating |
| 12 | Income Tax Withholding PRN Generation | income-tax-withholding-prn-generation | Mutating |
| 13 | VAT Withholding PRN Generation | vat-withholding-prn-generation | Mutating |
| 14 | Rental Withholding PRN Generation | rental-withholding-prn-generation | Mutating |
| 15 | Excise License Checker By Pin | excise-license-checker-by-pin | Read |
| 16 | Excise License Checker By Certificate Number | excise-license-checker-by-certificate-number | Read |
| 17 | Customs Declaration Status Checker | customs-declaration-status-checker | Read |
| 18 | Customs Tax Calculator | customs-tax-calculator | Read/calculation |
| 19 | Import Certificate Checker by PIN | import-certificate-checker-by-pin | Read |
| 20 | Import Certificate Checker by Cert Number | import-certificate-checker-by-cert-number | Read |
| 21 | Invoice Checker | invoice-checker | Read |
| 22 | eTIMS OSCU Integrator Automated Testing | etims-oscu-integrator-automated-testing | GavaConnect catalog operation |

### Unified invocation contract

Every language exposes `POST /v1/kra/{service-id}`, protected by `X-API-Key`:

```json
{
  "consent": true,
  "payload": {"service-specific": "fields come from the official KRA specification"}
}
```

Mutating operations (TCC application, NIL/TOT filing, the three withholding PRN generators and eTIMS OSCU automated testing) require an `Idempotency-Key` header of 16–128 characters. Mock mode does not fabricate successful filing, application or PRN responses; unsupported mappings return HTTP 501.

### Explicit upstream mappings

Set `KRA_SERVICE_PATHS_JSON` to a JSON object mapping service IDs to exact paths from the current official KRA GavaConnect API documentation. Optionally set `KRA_SERVICE_METHODS_JSON` (default POST; GET and POST, according to the official service specification). An empty mapping is safe by default and returns 501 rather than guessing endpoint paths. Authorization uses the existing server-side OAuth client-credentials flow.

Example structure only — these are placeholders, not real KRA paths:

```json
{
  "pin-checker-by-pin": "/REPLACE_WITH_OFFICIAL_PATH",
  "nil-return-filing": "/REPLACE_WITH_OFFICIAL_PATH",
  "invoice-checker": "/REPLACE_WITH_OFFICIAL_PATH"
}
```

## Separate direct eTIMS OSCU API

The supplied Postman collection also documents **23 direct OSCU sandbox POST operations** at `https://sbx.kra.go.ke/etims-oscu/api/v1`. This is not the GavaConnect catalog endpoint above and is not wired into the seven-language dispatcher. See [direct OSCU integration notes](docs/etims-oscu-direct-integration.md) and the [machine-readable endpoint inventory](contracts/etims-oscu-direct.endpoints.json).

The inventory captures the token endpoint, methods, paths and header context. A separate Python direct-OSCU sandbox adapter is now implemented; formal request/response schemas, live sandbox tests and applicable certification are still outstanding. The supplied collection contains malformed sample JSON and one malformed sales property; see the integration notes. Never reuse GavaConnect bearer tokens or proxy API keys for the direct OSCU host.


### Direct OSCU adapter (Python reference)

The Python server now exposes `POST /v1/etims/oscu/{operation_id}` when `ETIMS_OSCU_ENABLED=true`. Configure the separate sandbox application credentials and app ID in server environment variables; supply tenant context using `X-ETIMS-TIN`, `X-ETIMS-BHF-ID`, and `X-ETIMS-CMC-KEY`. Write operations require an `Idempotency-Key`. This adapter is sandbox-only, separate from GavaConnect, and has not yet been verified against live KRA sandbox credentials. See [direct OSCU integration notes](docs/etims-oscu-direct-integration.md).

## KRA setup and verification

1. Register at [developer.go.ke](https://developer.go.ke), create the developer application and subscribe to each KRA API your product needs.
2. Obtain the current specification for every subscribed service, including method, path, request/response schemas, scopes and error codes.
3. Configure sandbox credentials securely and test each read-only and mutating operation separately.
4. For direct OSCU device-protocol integration, follow the separate KRA OSCU sandbox and certification process.
5. Request production access from KRA and use separately issued production credentials.

The PIN-specific legacy routes still contain example response mappings; confirm them against sandbox. Do not claim sandbox or production verification until it has actually succeeded.

## Security and limitations

- Consumer keys/secrets belong only on the server. Never embed them in browser or mobile applications.
- Use TLS, high-entropy proxy API keys, secret management and rotation.
- Do not log full PINs, national IDs, credentials, tokens or raw KRA payloads.
- Collect and validate taxpayer consent in the calling application.
- In-memory token caches and rate limiters are process-local. Use Redis or gateway enforcement for multiple replicas.
- A PIN match is not proof of identity or tax compliance.
- Mock tests are not KRA certification. Production use is subject to KRA approval and current terms.

## Documentation

- [Architecture](docs/architecture.md)
- [OpenAPI contract](contracts/openapi.yaml)
- [KRA 22-service integration guide](docs/kra-catalog-integration.md)
- [Direct eTIMS OSCU integration](docs/etims-oscu-direct-integration.md)
- [Direct OSCU endpoint inventory](contracts/etims-oscu-direct.endpoints.json)
- [Language guides](docs/language-guides/README.md)
- [Security](docs/security.md)
- [Production readiness assessment](PRODUCTION_READINESS.md)
- [Compliance](docs/compliance.md)
- [Repository audit](AUDIT.md)
- [Implementation plan](IMPLEMENTATION_PLAN.md)
- [Feature parity](FEATURE_PARITY.md)

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). MIT license.


## Shared idempotency and local Docker stack

Mutating KRA and direct OSCU operations now use a shared idempotency store abstraction. Local development and tests use an in-memory store unless Redis is configured. Production requires private TLS Redis (`IDEMPOTENCY_REDIS_URL=rediss://...`) and a valid Fernet `IDEMPOTENCY_ENCRYPTION_KEY`; cached KRA responses are encrypted before persistence. Redis also coordinates rate limiting across application replicas. See [production hardening and local stack](docs/production-hardening-and-local-stack.md) for configuration, retention, recovery and Docker Compose instructions. The local Compose stack binds the API to loopback and does not publish Redis.
