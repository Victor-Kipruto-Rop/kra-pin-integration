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

`KRA_SERVICE_PATHS_JSON` is a JSON object mapping service IDs to exact relative KRA paths. `KRA_SERVICE_METHODS_JSON` optionally maps service IDs to `POST` (must be `POST`). Authorization is handled by the server-side OAuth client-credentials token helper.

Example shape only — the values below are placeholders, not real KRA paths:

```json
{
  "pin-checker-by-pin": "/OFFICIAL_PATH_FROM_KRA_SPEC",
  "nil-return-filing": "/OFFICIAL_PATH_FROM_KRA_SPEC"
}
```

An absent mapping returns HTTP 501. This is intentional: an incorrect guessed path or payload could cause a failed or unsafe filing/payment operation.

For the eTIMS OSCU service, set `KRA_ETIMS_BASE_URL` to the HTTPS KRA host specified for the taxpayer's approved integration. KRA's published OSCU guide identifies `https://etims-api-sbx.kra.go.ke` for sandbox and `https://etims-api.kra.go.ke` for production. This host is separate from the general GavaConnect gateway; the endpoint path and operation payload still need to come from the current OSCU specification and approval.

## Response and safety

- Successful upstream JSON is passed through without pretending every service has the same response schema.
- Invalid upstream JSON and upstream failures are returned as sanitized proxy errors.
- Mock mode does not invent successful responses for returns, TCC applications, PRN generation or eTIMS testing. Those routes return HTTP 501 until a real verified sandbox adapter is configured.
- Token caches, rate limiters and idempotency caches are currently process-local (PHP uses local request/container storage); they are not sufficient for multi-replica production. Use shared Redis/database-backed implementations before horizontal scaling.
- No service is considered sandbox-verified until its official payload, response, error and replay cases have passing integration tests using approved KRA credentials.
