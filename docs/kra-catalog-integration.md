# KRA 22-service catalog integration

All seven implementations expose the same server-side dispatcher:

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

The `payload` object is forwarded to the configured KRA service. The exact fields are deliberately not invented in this repository: use the current specification for the API subscribed to by the KRA developer application.

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

`KRA_SERVICE_PATHS_JSON` is a JSON object mapping service IDs to exact relative KRA paths. `KRA_SERVICE_METHODS_JSON` maps service IDs to `GET` or `POST`. GET payload fields are encoded as query parameters; POST payloads are sent as JSON. GET is rejected for catalog operations classified as mutating. The public proxy endpoint remains POST. Authorization is handled by the server-side OAuth client-credentials token helper; the access token is never returned to API callers.

Example shape only — the values below are placeholders, not real KRA paths:

```json
{
  "pin-checker-by-pin": "/OFFICIAL_PATH_FROM_KRA_SPEC",
  "nil-return-filing": "/OFFICIAL_PATH_FROM_KRA_SPEC"
}
```

An absent mapping returns HTTP 501. A repeated idempotency key with a different canonical payload returns HTTP 409. Same-process replay protection is implemented, but distributed idempotency still requires a shared durable store. This is intentional: an incorrect guessed path or payload could cause a failed or unsafe filing/payment operation.

The catalog entry `etims-oscu-integrator-automated-testing` is dispatched through the GavaConnect base URL like the other developer-catalog services. Its exact GavaConnect path, method, scope and payload must come from the authenticated developer-portal specification. This proxy does **not** implement the separate direct OSCU device protocol. Direct OSCU/VSCU integration uses its own KRA API, device activation/communication-key flow, sandbox and certification process; it must be implemented as a separate adapter, not by forwarding a GavaConnect bearer token to the OSCU host. See KRA's [OSCU specification](https://www.kra.go.ke/images/publications/OSCU_Specification_Document_v2.0.pdf), [OSCU/VSCU sign-up guide](https://kra.go.ke/images/publications/OSCU_VSCU_Step-by-Step_Guide-on-how-to-sign-up.pdf), and [system-to-system integration guidance](https://www.kra.go.ke/services/service/16).

## Response and safety

- Successful upstream JSON is passed through without pretending every service has the same response schema.
- Invalid upstream JSON and upstream failures are returned as sanitized proxy errors.
- Mock mode does not invent successful responses for returns, TCC applications, PRN generation or eTIMS testing. Those routes return HTTP 501 until a real verified sandbox adapter is configured.
- Token caches, rate limiters and idempotency caches are currently process-local (PHP uses local request/container storage); they are not sufficient for multi-replica production. Use shared Redis/database-backed implementations before horizontal scaling.
- No service is considered sandbox-verified until its official payload, response, error and replay cases have passing integration tests using approved KRA credentials.


## Implemented contract: Fetch Taxpayer Obligations

The supplied Postman collection documents this sandbox operation:

- OAuth: `GET https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials` using HTTP Basic credentials (consumer key as username, consumer secret as password).
- Operation: `POST https://sbx.kra.go.ke/dtd/checker/v1/obligation` using `Authorization: Bearer <access_token>`.
- JSON payload: `{ "taxPayerPin": "<taxpayer PIN>" }`.

The shared token client already obtains the token server-side and caches it; callers never submit or receive the KRA bearer token. The mapping template now configures the exact relative path and POST method. Example proxy invocation:

```bash
curl -X POST http://localhost:8000/v1/kra/fetch-taxpayer-obligations \\
  -H "X-API-Key: $PROXY_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"consent":true,"payload":{"taxPayerPin":"A000000000B"}}'
```

Set `KRA_MOCK=false`, `KRA_PIN_CONSUMER_KEY`, `KRA_PIN_CONSUMER_SECRET`, and the mapping JSON from `contracts/kra-service-mappings.template.json`. The request field spelling is case-sensitive. The Postman collection contains no response examples, so response schema, error mapping, authorization scope and live sandbox success remain unverified. Do not infer these from the collection.


## Implemented contract: VAT Exemption Checker

The supplied KRA sandbox Postman collection documents:

- OAuth token: `GET https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials` using HTTP Basic credentials.
- Operation: `POST https://sbx.kra.go.ke/dtd/checker/v1/vatexemption` using `Authorization: Bearer <access_token>`.
- JSON payload: `{ "VatExemptionCertificateNo": "<exemption certificate number>" }`.

The exact property name and casing are `VatExemptionCertificateNo`. The mapping template configures this relative path and POST method. Example proxy invocation:

```bash
curl -X POST http://localhost:8000/v1/kra/vat-exemption-checker \\
  -H "X-API-Key: $PROXY_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"consent":true,"payload":{"VatExemptionCertificateNo":"YOUR_SANDBOX_CERTIFICATE_NUMBER"}}'
```

The collection contains no response examples, so response schema, error mapping, OAuth scope and successful sandbox execution remain unverified. Do not infer them from this request-only collection.
