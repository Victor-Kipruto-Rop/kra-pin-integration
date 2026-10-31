# Getting started with real KRA credentials

This guide reflects KRA's developer portal as documented in October 2026. Portal screens and rules can
change, so follow the portal where it differs.

## 1. Register and create an app

1. Create an account on [developer.go.ke](https://developer.go.ke) (KRA's GavaConnect developer portal).
2. Create an application and subscribe it to the **PIN Checker** API. If you also want lookups by ID number,
   subscribe to **PIN Checker By ID**.
3. Copy the app's **Consumer Key** and **Consumer Secret**. Credentials are provisioned per app and API
   subscription, so you may end up with one pair or two. This template supports both setups.

KRA's FAQ states that access is currently free for approved developers and businesses and that pricing may
change with advance notice on the portal.

## 2. Configure

```bash
cp .env.example .env
# set KRA_MOCK=false, KRA_PIN_CONSUMER_KEY, KRA_PIN_CONSUMER_SECRET, PROXY_API_KEYS
```

Generate a proxy key with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

If KRA gave you separate credentials for PIN Checker By ID, also set `KRA_PIN_BY_ID_CONSUMER_KEY` and
`KRA_PIN_BY_ID_CONSUMER_SECRET`.

## 3. Confirm the sandbox response shapes

Use the portal's sample data, then run:

```bash
cd server
python -m scripts.probe_sandbox pin <sandbox-pin>
python -m scripts.probe_sandbox id <sandbox-id>
```

The script prints keys and value types only, never values. If the output differs from what
`server/app/kra_client.py` expects (`PINDATA`, `Name`, `KRAPIN`, error code `30002`), update the constants
at the top of that file and the matching tests, then please share the output with the project so others benefit.

Sandbox sample PINs may not follow the production PIN format, which is why `STRICT_PIN_FORMAT` defaults to
off outside production.

## 4. Move to production

1. Complete whatever KRA requires for production access (the portal may ask you to run its test cases first).
2. Set `KRA_ENVIRONMENT=production` and use the **production** consumer key/secret.
3. Keep `STRICT_PIN_FORMAT=true`, set real `PROXY_API_KEYS`, and run behind TLS.
4. Review [compliance.md](compliance.md) before processing real customers' data.

## Environments

| Environment | Base URL |
|---|---|
| Sandbox | `https://sbx.kra.go.ke` |
| Production | `https://api.kra.go.ke` |

## Upstream calls this template makes

```
GET  /v1/token/generate?grant_type=client_credentials     Authorization: Basic base64(key:secret)
POST /checker/v1/pinbypin   {"KRAPIN": "<PIN>"}           Authorization: Bearer <token>
POST /checker/v1/pin        {"TaxpayerType": "KE", "TaxpayerID": "<ID>"}
```

Tokens are cached and refreshed shortly before expiry (and once on a 401).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `502 upstream_auth_failed` | Wrong key/secret, wrong environment, or app not subscribed to that API |
| `502 unexpected_response` | KRA's response shape differs from what the parser expects; run the probe script |
| `504 upstream_timeout` | KRA slow or unreachable; raise `KRA_TIMEOUT_SECONDS` or retry |
| `503 upstream_rate_limited` | KRA is throttling; slow down and retry later |
| Startup `ConfigError` | An unsafe or incomplete setting; the message names the variable |
