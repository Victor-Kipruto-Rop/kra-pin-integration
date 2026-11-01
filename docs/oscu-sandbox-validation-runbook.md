# Direct eTIMS OSCU sandbox validation runbook

## Purpose and limits

This runner executes **one explicitly selected** operation from the direct OSCU endpoint manifest. It uses the dedicated sandbox OAuth client and direct OSCU host. It does not run the whole collection, guess payload fields, certify the integration, or enable production. The supplied Postman collection does not provide formal response schemas; prepare each payload only from an approved KRA example or KRA-confirmed contract.

## Safety model

- No network call occurs unless both `--execute` and `--confirm-sandbox` are supplied.
- The runner uses the fixed sandbox host in `DirectOscuClient`; there is no arbitrary URL argument.
- Credentials and tenant context are read from environment variables, never command-line arguments.
- Evidence stores request/response SHA-256 hashes and anonymous response structure only. It never stores raw request or response bodies, object field names (which may themselves contain taxpayer identifiers), credentials, bearer tokens, tenant identifiers, or authorization headers.
- Evidence files are created exclusively with owner-only permissions where supported. Existing paths are not overwritten.
- Mutating operations require a local approval/ticket reference. It is not sent to KRA and is not an idempotency guarantee; only its hash is saved. The adapter's in-memory replay protection does not make this standalone runner durable across processes.
- The adapter never retries an operation after a timeout. An unknown outcome must be reconciled with KRA before resubmission.
- Do not put real taxpayer payloads or secrets in the repository. Keep fixture files outside version control locally; the GitHub workflow accepts only KRA-approved non-production fixtures stored under `sandbox-fixtures/`.

## Prepare a local payload

Create a local JSON object using an approved KRA sample. Example below is deliberately a placeholder and is not a claim about the official schema:

```json
{}
```

## Configure local environment

Copy the repository-root `.env.example` to `.env`, then fill in the six direct OSCU values below. The runner now loads this file automatically. It uses only simple `KEY=VALUE` assignments (optional `export `, single/double quotes, blank lines and full-line comments); it does not execute shell syntax, expand variables, or override variables already present in the process environment.

- `ETIMS_OSCU_CONSUMER_KEY`
- `ETIMS_OSCU_CONSUMER_SECRET`
- `ETIMS_OSCU_APP_ID`
- `ETIMS_OSCU_TIN`
- `ETIMS_OSCU_BHF_ID`
- `ETIMS_OSCU_CMC_KEY`

Optional: `ETIMS_OSCU_TIMEOUT_SECONDS` (default 20). Never commit `.env`, real taxpayer payloads, or credentials.

## Dry-run first

From the repository root:

```bash
python scripts/run-oscu-sandbox-check.py --operation branch-list --payload ./private-fixtures/branch-list.json
```

This validates the operation and JSON payload locally and makes no network request. No KRA credentials are needed for this step.

## Execute one approved sandbox call locally

Only after KRA has issued credentials, confirmed the payload contract, and authorized the test:

```bash
python scripts/run-oscu-sandbox-check.py \
  --operation branch-list \
  --payload ./private-fixtures/branch-list.json \
  --execute \
  --confirm-sandbox
```

For an operation marked mutating, provide `--change-reference` with the approval or test-ticket reference (6-128 characters). This is an audit reference only, not an upstream idempotency header. Do not blindly rerun a write operation after a timeout.

Evidence is written under `artifacts/oscu-evidence/` by default. Review and retain it according to your organization's data-retention policy. The artifact proves only that the selected call returned successfully from the sandbox endpoint; it is not KRA certification.

## Execute through GitHub Actions

The normal CI workflows never require or receive KRA credentials. They run contract validation, mocked/unit tests and the language SDK checks offline.

For a separately approved live sandbox test:

1. In GitHub, open **Settings → Environments** and create an environment named `kra-sandbox`.
2. Configure required reviewers/deployment protection for that environment. Do not rely on the workflow's manual trigger alone as an approval control.
3. Add these six environment secrets to `kra-sandbox` (not repository-wide secrets): `ETIMS_OSCU_CONSUMER_KEY`, `ETIMS_OSCU_CONSUMER_SECRET`, `ETIMS_OSCU_APP_ID`, `ETIMS_OSCU_TIN`, `ETIMS_OSCU_BHF_ID`, and `ETIMS_OSCU_CMC_KEY`.
4. Add only KRA-approved, non-production JSON fixtures under `sandbox-fixtures/`. Do not commit real taxpayer data or secrets. The project intentionally supplies no invented request schemas.
5. Open **Actions → KRA OSCU sandbox validation → Run workflow**. Supply the operation ID, fixture path, and approval reference for mutating operations. Explicitly check `confirm_sandbox`.
6. Review the protected environment approval, workflow result and redacted evidence artifact. The evidence contains hashes, counts and anonymous shape metadata, not raw request or response values or object field names.

The workflow runs one selected operation only. It is not a full 23-operation certification suite. If the environment has no required reviewers configured, GitHub may allow execution without human approval; configure protection before adding credentials.

## Evidence format

Each evidence record includes timestamp, operation ID/path, environment, payload and response SHA-256 fingerprints, anonymous response shape/counts, presence-only tenant-context indicators, and explicit redaction flags. It excludes raw values and object field names. SHA-256 fingerprints are deterministic and may be guessable for low-entropy inputs; treat evidence as sensitive operational metadata and share it only with authorized reviewers. Hashes are integrity references, not proof of taxpayer identity or business correctness.

## Certification checklist

Before calling this integration certified, collect:
1. KRA-issued sandbox app credentials and approved app ID.
2. Written confirmation of request fields, required headers, response schemas and error semantics for each tested operation.
3. Written confirmation of which operations mutate KRA state and whether KRA supports an idempotency/replay mechanism.
4. Successful tests using KRA-approved non-production taxpayer/device data.
5. Redacted evidence artifacts, test date, operation list and KRA support/certification reference.
6. A separate approved production base URL and production credentials. This code intentionally rejects production for direct OSCU.
