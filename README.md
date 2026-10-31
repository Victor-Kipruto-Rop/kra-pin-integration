# KRA PIN Integration Template

A ready-to-fork, server-side template for verifying **KRA PINs** from websites, mobile apps and other
platforms using KRA's official **GavaConnect** API gateway ([developer.go.ke](https://developer.go.ke)).

> **Unofficial.** This project is community software and is not affiliated with or endorsed by the
> Kenya Revenue Authority. It talks only to KRA's official API gateway and never scrapes iTax. Check
> KRA's current terms and API documentation before going live, and read [docs/compliance.md](docs/compliance.md).

## What you get

- A small **FastAPI proxy** (`server/`) that holds your KRA credentials, handles OAuth tokens, and exposes
  a simple JSON API your own apps can call.
- **PIN by PIN** and **PIN by ID number** checks.
- **Mock mode**, so you can try everything without KRA credentials.
- Safe defaults: API-key auth, rate limiting, consent flag, PII-safe logging, refuses unsafe production config.
- Tests (no network needed), Dockerfile, CI workflow, OpenAPI spec, and client examples in cURL, JavaScript,
  Python, PHP and Dart (cURL, JavaScript and Python are tested against the mock server; PHP and Dart are untested sketches).

```
 Browser / mobile app ──► YOUR backend ──► this proxy ──► KRA GavaConnect (sbx.kra.go.ke / api.kra.go.ke)
        (never holds keys)    (holds proxy key)   (holds KRA keys)
```

Why a proxy: KRA consumer keys must never ship in front-end or mobile code. Keeping them server-side
also gives you one place for caching tokens, rate limits, consent checks and audit logging.

## Quick start (no KRA credentials needed)

```bash
git clone https://github.com/<your-username>/kra-pin-integration-template.git
cd kra-pin-integration-template/server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

export KRA_MOCK=true PROXY_API_KEYS=dev-key
uvicorn app.asgi:app --reload
```

```bash
curl -X POST http://localhost:8000/v1/pin/verify \
  -H "X-API-Key: dev-key" -H "Content-Type: application/json" \
  -d '{"pin": "A000000000B", "consent": true}'
```

In mock mode `A000000000B` (PIN) and `00000000` (ID number) are the only "found" values. Interactive docs
are at <http://localhost:8000/docs>. Run the tests with `pytest`.

Docker: copy `.env.example` to `.env`, edit it, then `docker compose up --build`.

## Going live with real KRA data

1. Register on [developer.go.ke](https://developer.go.ke), create an app and subscribe it to the PIN Checker
   API(s). Start in the sandbox. Step-by-step: [docs/getting-started.md](docs/getting-started.md).
2. Put the consumer key/secret in `.env` (never in Git) and set `KRA_MOCK=false`.
3. Run `python -m scripts.probe_sandbox pin <sandbox-pin>` to confirm response field names (see
   [Known gaps](#known-gaps)).
4. Request production access from KRA, switch `KRA_ENVIRONMENT=production`, and use production keys.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness and environment (no auth) |
| POST | `/v1/pin/verify` | Check a PIN: `{"pin": "...", "consent": true}` |
| POST | `/v1/pin/verify-by-id` | Find a PIN by ID: `{"taxpayer_id": "...", "taxpayer_type": "KE", "consent": true}` |

Auth: `X-API-Key` header. Success body: `{"found": true, "pin": "...", "taxpayer_name": "...", "environment": "sandbox", "mock": false, "raw": null}`.
Errors: `{"error": {"code": "upstream_timeout", "message": "..."}}` for upstream failures; standard
`{"detail": "..."}` for validation, auth and rate-limit errors. Full spec: [docs/openapi.json](docs/openapi.json).

`found: true` means KRA has a matching record. It is **not** proof of identity and **not** proof of tax
compliance (that is a separate Tax Compliance Certificate check).

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `KRA_ENVIRONMENT` | `sandbox` | `sandbox` or `production` |
| `KRA_PIN_CONSUMER_KEY` / `_SECRET` | | App subscribed to PIN Checker |
| `KRA_PIN_BY_ID_CONSUMER_KEY` / `_SECRET` | falls back to the PIN keys | Only if KRA issued separate keys |
| `KRA_MOCK` | `false` | Offline demo mode; refused in production |
| `PROXY_API_KEYS` | | Comma-separated keys callers must send as `X-API-Key` |
| `ALLOW_UNAUTHENTICATED` | `false` | Local development only; refused in production |
| `REQUIRE_CONSENT` | `true` | Request must include `"consent": true` |
| `STRICT_PIN_FORMAT` | `true` in production | Sandbox sample data may not match the real PIN shape |
| `INCLUDE_RAW_RESPONSE` | `false` | Return KRA's full payload (more personal data) |
| `RATE_LIMIT_PER_MINUTE` | `30` | Per API key, in memory (per process) |
| `CORS_ORIGINS` | empty | Only needed if browsers call the proxy directly (usually don't) |
| `KRA_TIMEOUT_SECONDS` | `15` | Upstream timeout |

## Security checklist

- Keep `.env` out of Git (already in `.gitignore`); use your platform's secret store in production.
- Call the proxy from servers only. Do not embed `PROXY_API_KEYS` in web or mobile apps.
- Put TLS in front of the proxy (reverse proxy, platform load balancer).
- Logs mask PINs and never record ID numbers. Keep it that way if you extend the code.
- Add a shared rate limiter if you run more than one instance.

## Known gaps

- KRA's success and not-found response bodies are parsed defensively, because the public docs show
  request formats and error codes more completely than response bodies. Field names are isolated in
  `server/app/kra_client.py`; confirm them with the probe script and update the tests.
- Only PIN checks are implemented. Other GavaConnect APIs (TCC, eTIMS, nil returns, and so on) are out of scope.
- KRA's terms, endpoints and access rules can change. Treat [developer.go.ke](https://developer.go.ke) as the source of truth.

## Layout

```
server/            FastAPI proxy, tests, Dockerfile, sandbox probe script
docs/              getting-started, integration guides, compliance notes, OpenAPI spec
examples/          cURL, JavaScript, Python, PHP, Dart callers
.github/           CI and Dependabot
```

## Contributing and licence

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Released under the MIT licence
([LICENSE](LICENSE)).
