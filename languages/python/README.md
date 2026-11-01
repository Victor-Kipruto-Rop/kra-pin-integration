# Python direct eTIMS OSCU SDK

This SDK is a server-side client for the 23 operations in the supplied KRA OSCU sandbox Postman collection. It uses a fixed sandbox host and obtains OAuth tokens using HTTP Basic credentials. It does not support production hosts.

Install with `pip install -r requirements.txt`. Import `DirectOscuClient` from `kra_pin_oscu`.

Mutating operations require the caller to pass `confirm_mutation=True` after obtaining business approval. This is a local safety guard, not an upstream idempotency guarantee. The client never retries a mutation automatically. A timeout on a mutation raises `OscuError` with `outcome_unknown=True`; reconcile with KRA before resubmitting.

Payloads are accepted as JSON objects because KRA has not supplied formal field-level schemas for all operations. The manifest deliberately preserves unresolved sample issues. No taxpayer data, credentials or raw payloads are logged by this client.

The SDK's manifest is a packaged copy of `contracts/etims-oscu-direct.endpoints.json`; CI validates parity. Do not modify one copy independently.

This is an integration SDK, not KRA certification. Obtain KRA-confirmed schemas, mutation classifications and written sandbox approval before live use.
