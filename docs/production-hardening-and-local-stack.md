# Production hardening and local stack

## Shared security state

The API now uses a common store interface for mutation idempotency and rate limiting:

- Local tests and a developer setup without Redis use a single-process memory store. It is not safe for multiple workers or production.
- When `IDEMPOTENCY_REDIS_URL` is configured, Redis coordinates rate limits and idempotency reservations across workers/replicas.
- Production startup requires `IDEMPOTENCY_REDIS_URL`, a TLS `rediss://` URL, and a valid `IDEMPOTENCY_ENCRYPTION_KEY`.
- Completed idempotency responses are encrypted with Fernet before being stored in Redis. The key must be kept in a secret manager and backed up securely; losing it makes completed cached responses unreadable. Undecryptable/corrupt records fail closed as unknown outcomes.
- Default idempotency retention is seven days. Configure `IDEMPOTENCY_TTL_SECONDS` to at least 3600 seconds. After expiry, a repeated key can no longer be recognized; choose a retention period aligned with KRA's replay and business-reconciliation requirements.
- A pending reservation blocks concurrent duplicates. If the process crashes after KRA may have accepted a mutation, the pending reservation remains until its TTL. Operators must reconcile the outcome with KRA before manually clearing any record.
- A timeout on a mutation is recorded as unknown where the upstream client can identify that outcome. Do not resubmit until KRA state is reconciled.

Redis is security-sensitive infrastructure: use private networking, TLS, authentication, encrypted persistence/backups, access controls and monitoring. Never expose Redis to the public internet. Cached responses can contain taxpayer information; encryption keys and Redis snapshots must be treated as sensitive.

## Local Docker Compose stack

1. Copy `.env.example` to `.env`.
2. Generate a URL-safe Redis password:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Put the result in `REDIS_PASSWORD` in `.env`.
3. Generate a Fernet key:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Put it in `IDEMPOTENCY_ENCRYPTION_KEY` in `.env`.
4. Keep `KRA_ENVIRONMENT=sandbox`, `KRA_MOCK=true`, and `ETIMS_OSCU_ENABLED=false` for an offline local trial.
5. Run `docker compose up --build`.
6. Check `http://127.0.0.1:8000/health` and `http://127.0.0.1:8000/ready`.
7. Stop with `docker compose down`. Use `docker compose down -v` only when intentionally deleting the local Redis volume and its idempotency records.

The Compose Redis service has no published host port and the API binds only to loopback. This is a developer stack, not a production deployment blueprint.

## Production release gates

Before deploying:
- Use a managed/private Redis-compatible service with TLS and authentication.
- Set a Fernet key from a secret manager; never commit it or put it in an image.
- Set production KRA credentials and proxy API keys through a secret manager.
- Disable mock mode and verify production base URLs and KRA approval separately.
- Run Redis backup restoration drills and document retention.
- Configure HTTPS ingress, request-size limits, WAF/network policy, centralized logs and alerting.
- Run dependency, container and penetration tests.
- Obtain KRA-approved production endpoint details and written certification/approval.

This repository does not provide KRA production OSCU credentials, certify KRA contracts, or enable direct OSCU production. Direct OSCU remains sandbox-only.
