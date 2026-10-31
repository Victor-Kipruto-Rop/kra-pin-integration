# Ruby / Rack service

Requires Ruby 3.3+. Run `bundle install`, export variables from `.env.example`, then `bundle exec rackup -o 127.0.0.1 -p 8000`. Tests: `bundle exec rspec`. Demo PIN A000000000B; ID 00000000. Independent server-side KRA integration. Verify response field mappings in sandbox before production.

## Full KRA catalog (22 services)

This template exposes POST /v1/kra/{service-id} for every service in the shared catalog. See the root README and contracts/kra-services.json for the complete ID list. Send X-API-Key and JSON { "consent": true, "payload": { ... } }. Mutating services require an Idempotency-Key header (16–128 characters).

Configure KRA_SERVICE_PATHS_JSON and optionally KRA_SERVICE_METHODS_JSON from the current approved KRA API specifications. The adapter intentionally returns HTTP 501 for missing mappings instead of inventing upstream URLs or payloads. Mock mode also returns 501 for these real operations; it does not fake successful filings, TCC applications or PRNs.

For eTIMS OSCU automated testing, set KRA_ETIMS_BASE_URL to the exact HTTPS KRA host assigned in the official OSCU documentation/approval. The eTIMS service is not assumed to share the GavaConnect API host. Service-specific request/response schemas and live sandbox verification remain release gates.

### Upstream method and authorization safety

The public proxy endpoint is always POST. Each verified KRA mapping may use GET (payload fields become query parameters) or POST (payload is sent as JSON); GET is rejected for mutating operations. The `authorization` catalog operation obtains the KRA bearer token internally and returns only authorization status metadata. The raw token is never returned to API clients.


## Direct eTIMS OSCU sandbox SDK

Use `KraPin::DirectOscuClient` from `oscu_client.rb` in server-side Ruby only. It uses the fixed sandbox host, HTTP Basic token acquisition and bearer-authenticated POST operations. Mutating operations require `confirm_mutation: true`; submitted operations are never automatically retried. A mutation transport failure raises `KraPin::OscuError` with `outcome_unknown=true`; reconcile with KRA before resubmitting. Formal request/response schemas remain pending KRA confirmation.
