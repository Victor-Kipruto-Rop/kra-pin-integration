# Direct eTIMS OSCU integration

This is the direct KRA eTIMS OSCU API, separate from GavaConnect. The supplied collection documents sandbox base URL `https://sbx.kra.go.ke/etims-oscu/api/v1`, a shared OAuth client-credentials token endpoint, and 23 POST operations. This file records the integration boundary; it does not claim a runtime adapter or sandbox verification.

Use HTTP Basic credentials only server-side to obtain a bearer token from `GET https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials`. Operations use bearer authentication. Most operations include `tin`, `bhfId`, `cmcKey`, and `apigee_app_id` headers; `initialize` documents only `apigee_app_id`.

Do not configure the GavaConnect catalog service ID `etims-oscu-integrator-automated-testing` with these direct OSCU paths. A separate adapter must use its own base URL, credentials, device context, validation, token lifecycle and retry policy.

The supplied samples contain invalid JSON comments and a malformed sales field named `isr ccCd`. Confirm that field with KRA; do not silently correct it. Response examples, response schemas, error codes, OAuth scopes and replay semantics are not supplied. No sandbox execution or certification has been performed.
