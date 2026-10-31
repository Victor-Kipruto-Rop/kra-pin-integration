# Direct eTIMS OSCU sandbox validation runbook

## Purpose and limits

This runner executes **one explicitly selected** operation from the direct OSCU endpoint manifest. It uses the dedicated sandbox OAuth client and direct OSCU host. It does not run the whole collection, guess payload fields, certify the integration, or enable production. The supplied Postman collection does not provide formal response schemas; prepare each payload only from an approved KRA example or KRA-confirmed contract.

## Safety model

- No network call occurs unless both `--execute` and `--confirm-sandbox` are supplied.
- The runner uses the fixed sandbox host in `DirectOscuClient`; there is no arbitrary URL argument.
- Credentials and tenant context are read from environment variables, never command-line arguments.
- Evidence stores request/response SHA-256 hashes and response structure only. It never stores raw request or response bodies, credentials, bearer tokens, tenant identifiers, or authorization headers.
- Evidence files are created exclusively with owner-only permissions where supported. Existing paths are not overwritten.
- Mutating operations require a caller-provided idempotency key. The key itself is not saved; only its hash is.
- The adapter never retries an operation after a timeout. An unknown outcome must be reconciled with KRA before resubmission.
- Do not put real taxpayer payloads or secrets in the repository. Keep fixture files outside version control.

## Prepare a local payload

Create a local JSON object using an approved KRA sample. Example below is deliberately a placeholder and is not a claim about the official schema:

```json
{}
```

## Configure local environment

Set these values in the shell or a local, untracked environment file loaded by your secret manager:

- `ETIMS_OSCU_CONSUMER_KEY`
- `ETIMS_OSCU_CONSUMER_SECRET`
- `ETIMS_OSCU_APP_ID`
- `ETIMS_OSCU_TIN`
- `ETIMS_OSCU_BHF_ID`
- `ETIMS_OSCU_CMC_KEY`

Optional: `ETIMS_OSCU_TIMEOUT_SECONDS` (default 20). Never commit these values or include them in support tickets.

## Dry-run first

From the repository root:

```bash
python scripts/run-oscu-sandbox-check.py --operation branch-list --payload ./private-fixtures/branch-list.json
```

This validates the operation and JSON payload locally and makes no network request.

## Execute one approved sandbox call

Only after KRA has issued credentials, confirmed the payload contract, and authorized the test:

```bash
python scripts/run-oscu-sandbox-check.py \
  --operation branch-list \
  --payload ./private-fixtures/branch-list.json \
  --execute \
  --confirm-sandbox
```

For an operation marked mutating, add a unique `--idempotency-key` of 16-128 characters. Do not blindly rerun a write operation after a timeout.

Evidence is written under `artifacts/oscu-evidence/` by default. Review and retain it according to your organization’s data-retention policy. The artifact proves only that the selected call returned successfully from the sandbox endpoint; it is not KRA certification.

## Evidence format

Each evidence record includes timestamp, operation ID/path, environment, payload hash, response hash, response shape, presence-only tenant-context indicators, and explicit redaction flags. It excludes raw values. Hashes are integrity references, not proof of taxpayer identity or business correctness.

## Certification checklist

Before calling this integration certified, collect:
1. KRA-issued sandbox app credentials and approved app ID.
2. Written confirmation of request fields, required headers, response schemas and error semantics for each tested operation.
3. Written confirmation of which operations mutate KRA state and how KRA supports idempotency/replay.
4. Successful tests using KRA-approved non-production taxpayer/device data.
5. Redacted evidence artifacts, test date, operation list and KRA support/certification reference.
6. A separate approved production base URL and production credentials. This code intentionally rejects production for direct OSCU.
