# Direct eTIMS OSCU integration

This is the direct KRA eTIMS OSCU API, separate from GavaConnect. The supplied collection documents sandbox base URL `https://sbx.kra.go.ke/etims-oscu/api/v1`, a shared OAuth client-credentials token endpoint, and 23 POST operations. A separate Python reference adapter is implemented behind a disabled-by-default feature flag; live sandbox verification and certification remain pending.

Use HTTP Basic credentials only server-side to obtain a bearer token from `GET https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials`. Operations use bearer authentication. Most operations include `tin`, `bhfId`, `cmcKey`, and `apigee_app_id` headers; `initialize` documents only `apigee_app_id`.

Do not configure the GavaConnect catalog service ID `etims-oscu-integrator-automated-testing` with these direct OSCU paths. A separate adapter must use its own base URL, credentials, device context, validation, token lifecycle and retry policy.

The supplied samples contain invalid JSON comments and a malformed sales field named `isr ccCd`. Confirm that field with KRA; do not silently correct it. Response examples, response schemas, error codes, OAuth scopes and replay semantics are not supplied. No sandbox execution or certification has been performed.

## Runtime adapter

The Python reference server exposes `POST /v1/etims/oscu/{operation_id}` when `ETIMS_OSCU_ENABLED=true`. Configure the direct OSCU sandbox app credentials and application ID on the server. The caller supplies tenant context through `X-ETIMS-TIN`, `X-ETIMS-BHF-ID`, and `X-ETIMS-CMC-KEY`; the server injects `apigee_app_id`.

The adapter has its own token cache and uses only the documented sandbox host. Production is blocked because the supplied collection contains no production host or approval evidence. Eleven write operations require an idempotency key; successful responses and unknown outcomes are cached in process memory only. Use Redis or a database for multi-worker deployments.

The adapter accepts object payloads because formal request schemas and response examples were not supplied. A timeout on a write is treated as an unknown outcome; reconcile with KRA before attempting another submission. No live sandbox request or KRA certification is claimed.


## Seven-language SDKs and OpenAPI

Server-side direct OSCU clients are now provided in Python, Go, Java, JavaScript, TypeScript, PHP and Ruby. Each client uses the fixed sandbox token/operation hosts and the packaged 23-operation manifest. Mutating operations require an explicit local confirmation flag; clients do not automatically retry submitted mutations. This confirmation is a safety interlock, not a KRA idempotency guarantee. A language-neutral OpenAPI description is available at [contracts/etims-oscu-openapi.yaml](../contracts/etims-oscu-openapi.yaml). CI checks the seven packaged manifest copies against the canonical inventory.

No formal field-level request or response schemas have been supplied for all operations. The SDKs therefore accept JSON objects without pretending to validate KRA's undocumented field contracts. Mutation classifications remain provisional until KRA confirms them. None of these SDKs has been certified by KRA or validated with live credentials in this implementation work.
