# TypeScript / Node.js service

Requires Node.js 20+. Run `npm install`, `npm test`, then `npm start`. Strict TypeScript compiles to dist/ and uses native fetch at runtime. Configure environment variables from `.env.example`. Demo PIN A000000000B and ID 00000000. Independent server-side KRA integration; do not embed secrets in browser code. Confirm upstream response mappings in sandbox.

## Full KRA catalog (22 services)

This template exposes POST /v1/kra/{service-id} for every service in the shared catalog. See the root README and contracts/kra-services.json for the complete ID list. Send X-API-Key and JSON { "consent": true, "payload": { ... } }. Mutating services require an Idempotency-Key header (16–128 characters).

Configure KRA_SERVICE_PATHS_JSON and optionally KRA_SERVICE_METHODS_JSON from the current approved KRA API specifications. The adapter intentionally returns HTTP 501 for missing mappings instead of inventing upstream URLs or payloads. Mock mode also returns 501 for these real operations; it does not fake successful filings, TCC applications or PRNs.

For eTIMS OSCU automated testing, set KRA_ETIMS_BASE_URL to the exact HTTPS KRA host assigned in the official OSCU documentation/approval. The eTIMS service is not assumed to share the GavaConnect API host. Service-specific request/response schemas and live sandbox verification remain release gates.

### Upstream method and authorization safety

The public proxy endpoint is always POST. Each verified KRA mapping may use GET (payload fields become query parameters) or POST (payload is sent as JSON); GET is rejected for mutating operations. The `authorization` catalog operation obtains the KRA bearer token internally and returns only authorization status metadata. The raw token is never returned to API clients.


## Direct eTIMS OSCU sandbox SDK

Import `DirectOscuClient` from `src/oscu-client.ts` in server-side Node.js code only. It uses the fixed KRA sandbox host, Basic token acquisition and bearer-authenticated operations. Mutations require `{ confirmMutation: true }`; submitted operations are never automatically retried. A mutation timeout is marked as an unknown outcome and must be reconciled with KRA before resubmission. Formal schemas and mutation classifications remain pending KRA confirmation.
