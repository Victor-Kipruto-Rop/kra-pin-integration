# PHP service

Requires PHP 8.2+ and cURL. Run `composer install`, export variables from `.env.example`, then run the development server with `php -S 127.0.0.1:8000 -t public`. Tests: `composer test`. Demo PIN A000000000B; ID 00000000. Server-side only. Add a shared gateway rate limiter for production replicas and verify KRA response fields in sandbox.


**Production deployment:** The PHP built-in server and included CLI Dockerfile are development-only. Deploy PHP-FPM behind a hardened web server or ingress, with TLS, process supervision and centralized rate limiting.

## Full KRA catalog (22 services)

This template exposes POST /v1/kra/{service-id} for every service in the shared catalog. See the root README and contracts/kra-services.json for the complete ID list. Send X-API-Key and JSON { "consent": true, "payload": { ... } }. Mutating services require an Idempotency-Key header (16–128 characters).

Configure KRA_SERVICE_PATHS_JSON and optionally KRA_SERVICE_METHODS_JSON from the current approved KRA API specifications. The adapter intentionally returns HTTP 501 for missing mappings instead of inventing upstream URLs or payloads. Mock mode also returns 501 for these real operations; it does not fake successful filings, TCC applications or PRNs.

For eTIMS OSCU automated testing, set KRA_ETIMS_BASE_URL to the exact HTTPS KRA host assigned in the official OSCU documentation/approval. The eTIMS service is not assumed to share the GavaConnect API host. Service-specific request/response schemas and live sandbox verification remain release gates.

### Upstream method and authorization safety

The public proxy endpoint is always POST. Each verified KRA mapping may use GET (payload fields become query parameters) or POST (payload is sent as JSON); GET is rejected for mutating operations. The `authorization` catalog operation obtains the KRA bearer token internally and returns only authorization status metadata. The raw token is never returned to API clients.


## Direct eTIMS OSCU sandbox SDK

Use `KraPin\\DirectOscuClient` from `src/DirectOscuClient.php` in server-side PHP only. The client uses the fixed sandbox host, Basic token acquisition and bearer-authenticated POST calls. Mutations require explicit confirmation; the client never retries a submitted request. A transport failure on a mutation raises `OscuUnknownOutcomeException`; reconcile the operation with KRA before resubmitting. Request and response schemas remain provisional pending KRA confirmation.
