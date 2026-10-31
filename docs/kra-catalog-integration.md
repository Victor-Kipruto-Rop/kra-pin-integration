# KRA 22-service catalog integration

All seven implementations expose the same server-side GavaConnect dispatcher:

- Python: `POST /v1/kra/{service-id}`
- Go: `POST /v1/kra/{service-id}`
- Java: `POST /v1/kra/{service-id}`
- JavaScript: `POST /v1/kra/{service-id}`
- TypeScript: `POST /v1/kra/{service-id}`
- PHP: `POST /v1/kra/{service-id}`
- Ruby: `POST /v1/kra/{service-id}`

See [kra-services.json](../contracts/kra-services.json) for the canonical 22 IDs and mutability metadata, and [openapi.yaml](../contracts/openapi.yaml) for the request contract.

## Request

Headers:

- `X-API-Key`: this proxy's server-side API key.
- `Content-Type: application/json`.
- `Idempotency-Key`: required for mutating services; 16–128 characters.

Body:

```json
{
  "consent": true,
  "payload": {}
}
```

The `payload` object is forwarded to the configured GavaConnect service. The exact fields are deliberately not invented in this repository: use the current specification for the API subscribed to by the KRA developer application.

## Mutating operations

The following require `Idempotency-Key`:

- Tax Compliance Certificate Application
- NIL Return Filing
- TOT Return Filing
- Income Tax Withholding PRN Generation
- VAT Withholding PRN Generation
- Rental Withholding PRN Generation
- eTIMS OSCU Integrator Automated Testing

Do not retry these operations with a new idempotency key after an uncertain timeout. First reconcile the request outcome with KRA or the relevant official status API.

## Upstream configuration

`KRA_SERVICE_PATHS_JSON` is a JSON object mapping GavaConnect service IDs to exact relative paths. `KRA_SERVICE_METHODS_JSON` maps service IDs to `GET` or `POST`. GET payload fields are encoded as query parameters; POST payloads are sent as JSON. GET is rejected for catalog operations classified as mutating. The public proxy endpoint remains POST. Authorization is handled by the server-side GavaConnect OAuth client; the access token is never returned to API callers.

Example shape only — values are placeholders, not real KRA paths:

```json
{
  "pin-checker-by-pin": "/OFFICIAL_PATH_FROM_KRA_SPEC",
  "nil-return-filing": "/OFFICIAL_PATH_FROM_KRA_SPEC"
}
```

An absent mapping returns HTTP 501. A repeated idempotency key with a different canonical payload returns HTTP 409. Same-process replay protection is implemented, but distributed idempotency still requires a shared durable store.

## Separate direct eTIMS OSCU API

The direct OSCU Postman collection is documented separately in [etims-oscu-direct-integration.md](etims-oscu-direct-integration.md), with a machine-readable [23-operation endpoint inventory](../contracts/etims-oscu-direct.endpoints.json). These direct endpoints use the sandbox base URL `https://sbx.kra.go.ke/etims-oscu/api/v1` and a separate OSCU authentication/device context. They are **not** GavaConnect service paths and must not be added to `KRA_SERVICE_PATHS_JSON`. A separate Python direct OSCU sandbox adapter and server-side SDK clients for Python, Go, Java, JavaScript, TypeScript, PHP and Ruby are implemented. Formal schemas, live sandbox validation and KRA certification remain pending. Never forward a GavaConnect bearer token to the OSCU host.

## Response and safety

- Successful upstream JSON is passed through without pretending every service has the same response schema.
- Invalid upstream JSON and upstream failures are returned as sanitized proxy errors.
- Mock mode does not invent successful responses for returns, TCC applications, PRN generation or eTIMS testing. Unsupported routes return HTTP 501 until a verified adapter is configured.
- The Python FastAPI service now supports shared Redis-backed rate limiting and idempotency, with encrypted cached responses and tenant-scoped OSCU idempotency keys. Production requires TLS Redis and a Fernet encryption key. The independent Go/Java/JavaScript/TypeScript/PHP/Ruby GavaConnect server templates still have process-local state and need shared gateway/state coordination before horizontal scaling.
- No service is considered sandbox-verified until its official payload, response, error and replay cases have passing integration tests using approved KRA credentials.

## Implemented GavaConnect contract: Fetch Taxpayer Obligations

The supplied Postman collection documents:
- OAuth: `GET https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials` using HTTP Basic credentials.
- Operation: `POST https://sbx.kra.go.ke/dtd/checker/v1/obligation` using a bearer token.
- JSON payload: `{ "taxPayerPin": "<taxpayer PIN>" }`.

The mapping template configures the exact path and POST method. The collection contains no response examples, so response schema, error mapping, authorization scope and sandbox success remain unverified.

## Implemented GavaConnect contract: VAT Exemption Checker

The supplied KRA sandbox Postman collection documents:
- OAuth token: `GET https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials` using HTTP Basic credentials.
- Operation: `POST https://sbx.kra.go.ke/dtd/checker/v1/vatexemption` using a bearer token.
- JSON payload: `{ "VatExemptionCertificateNo": "<exemption certificate number>" }`.

The exact property name and casing are `VatExemptionCertificateNo`. No response example was supplied; response schema, error mapping, OAuth scope and successful sandbox execution remain unverified.
