# Integration guides

Pick the pattern that fits your stack. In every case, **browsers and mobile apps never hold KRA keys or the
proxy API key**. They call your own backend, which calls the proxy (or embeds the client).

## Patterns

| Pattern | When to use |
|---|---|
| **A. Run the proxy as a service** | Any language or platform. Your backend calls it over HTTP. |
| **B. Embed the Python client** | Python apps. Copy `server/app/kra_client.py` and `config.py`; call `KraClient`. |
| **C. Port to your language** | Use [openapi.json](openapi.json) for the proxy contract, and "Upstream calls" in [getting-started.md](getting-started.md) for the KRA flow. |

## Typical flows

- **Website sign-up or checkout form:** browser posts the PIN to your server route, which checks that the
  user ticked a consent box, then calls `POST /v1/pin/verify`, then stores only the outcome you need.
- **Mobile app (Flutter, React Native, Android, iOS):** the app sends the PIN to your API; your API calls the proxy.
- **Supplier or merchant onboarding, lending, marketplaces:** run the check on submission, store `found`
  and a timestamp, and send mismatches to manual review rather than auto-rejecting.

Treat `found` as one signal. It does not prove the person submitting the PIN owns it, and it says nothing
about tax compliance.

## Calling the proxy

All examples send the proxy key from the server side. Runnable files are in [`../examples`](../examples).

**cURL**

```bash
curl -X POST "$PROXY_URL/v1/pin/verify" \
  -H "X-API-Key: $PROXY_API_KEY" -H "Content-Type: application/json" \
  -d '{"pin": "A000000000B", "consent": true}'
```

**Node.js 18+ (server-side)**

```js
const res = await fetch(`${process.env.PROXY_URL}/v1/pin/verify`, {
  method: "POST",
  headers: { "X-API-Key": process.env.PROXY_API_KEY, "Content-Type": "application/json" },
  body: JSON.stringify({ pin, consent: true }),
});
const result = await res.json(); // { found, pin, taxpayer_name, ... }
```

**Python**

```python
import httpx
r = httpx.post(f"{PROXY_URL}/v1/pin/verify", headers={"X-API-Key": KEY},
               json={"pin": pin, "consent": True}, timeout=20)
r.raise_for_status()
```

**PHP**

```php
$ch = curl_init("$proxyUrl/v1/pin/verify");
curl_setopt_array($ch, [
  CURLOPT_POST => true, CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20,
  CURLOPT_HTTPHEADER => ["X-API-Key: $apiKey", "Content-Type: application/json"],
  CURLOPT_POSTFIELDS => json_encode(["pin" => $pin, "consent" => true]),
]);
$result = json_decode(curl_exec($ch), true);
```

## Handling results

| HTTP | Meaning | What to do |
|---|---|---|
| 200, `found: true` | KRA has a record | Continue; store the outcome, not more than you need |
| 200, `found: false` | No match | Ask the user to re-check; offer manual review |
| 400 / 422 | Missing consent or bad format | Fix the request |
| 401 / 429 | Bad proxy key / rate limit | Check key; back off |
| 502 / 503 / 504 | KRA problem or timeout | Retry with backoff; do not treat as "invalid PIN" |

## Deployment notes

- Run 1+ container instances behind TLS. The in-memory rate limiter is per instance, so use your gateway's
  limiter or Redis when scaling out.
- Set `CORS_ORIGINS` only if a browser must call the proxy directly, and then protect it with your own
  session auth rather than a shared key.
