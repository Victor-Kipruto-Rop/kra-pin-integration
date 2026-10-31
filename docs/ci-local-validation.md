# Local CI and release validation

The repository has a seven-runtime test matrix. Use the local runner when GitHub Actions is unavailable because of account billing or runner provisioning.

## One-command full test

From the repository root:

```bash
bash scripts/ci-local.sh
```

The script installs the declared test dependencies and runs, in order:

1. Canonical 22-service catalog validation and direct OSCU 23-operation manifest/OpenAPI parity.
2. Python reference API tests, linting and Python OSCU SDK tests.
3. Go unit tests.
4. Java/Maven tests.
5. JavaScript tests.
6. TypeScript compilation and tests.
7. PHP PHPUnit tests and PHP syntax checks.
8. Ruby/RSpec tests and Ruby syntax checks.
9. Docker Compose configuration validation when Docker is installed.

Use `bash scripts/ci-local.sh --skip-install` when dependencies are already installed. Use `bash scripts/ci-local.sh --validation-only` for static contract and syntax checks only; this is not a substitute for the full matrix.

Equivalent Make targets are available:

```bash
make validate
make test-python
make test-go
make test-java
make test-js
make test-ts
make test-php
make test-ruby
make test-all
```

## GitLab CI fallback

The checked-in `.gitlab-ci.yml` is the hosted CI fallback. Import or mirror this repository into GitLab, enable CI/CD for the project, and run the pipeline on the branch containing the implementation. The pipeline is configured to publish Python and Java JUnit reports and a consolidated summary artifact. No GitLab connection or pipeline execution is performed by this repository template itself.

## Docker

Validate both compose definitions before starting containers:

```bash
docker compose config --quiet
docker compose -f docker-compose.multilang.yml config --quiet
```

The secure single-service stack requires a root `.env` file with strong local values for `REDIS_PASSWORD` and `IDEMPOTENCY_ENCRYPTION_KEY`. Do not use production credentials in local development.

## Approved OSCU sandbox evidence

The default command is a dry run and does not send a network request:

```bash
make sandbox-dry-run OPERATION=oscu-initialization PAYLOAD=./sandbox-fixtures/your-approved-request.json
```

A live sandbox request requires both explicit flags, all required KRA-provided environment values, approved test data, and (for operations marked mutating) a change/ticket reference:

```bash
python3 scripts/run-oscu-sandbox-check.py \
  --operation oscu-initialization \
  --payload ./private/approved-request.json \
  --change-reference KRA-SANDBOX-123456 \
  --execute --confirm-sandbox
```

Do not commit credentials, taxpayer PINs, request payloads or raw response bodies. Evidence files are created with owner-only permissions and redact payload, response and tenant context.

## Interpreting results

- A successful local suite proves only that the local code and included test fixtures passed.
- A failed GitHub Actions job with no runner steps is an Actions infrastructure/billing failure, not a code test result.
- A green GitLab pipeline proves the jobs ran in GitLab; it does not prove KRA connectivity or certification.
- Live KRA sandbox verification requires approved KRA credentials, authorized test data and recorded redacted evidence.
- Production use requires KRA approval/certification, privacy/legal review, security review, shared state for multi-replica deployments, monitoring and release sign-off. See [Production readiness](../PRODUCTION_READINESS.md).
