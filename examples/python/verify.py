"""Standard-library only. Run on a SERVER, not inside a distributed app.

    PROXY_URL=http://localhost:8000 PROXY_API_KEY=dev-key python verify.py A000000000B
"""
import json
import os
import sys
import urllib.error
import urllib.request

base = os.environ.get("PROXY_URL", "http://localhost:8000")
pin = sys.argv[1] if len(sys.argv) > 1 else "A000000000B"

req = urllib.request.Request(
    f"{base}/v1/pin/verify",
    data=json.dumps({"pin": pin, "consent": True}).encode(),
    headers={"X-API-Key": os.environ.get("PROXY_API_KEY", ""), "Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.load(resp)
except urllib.error.HTTPError as exc:
    sys.exit(f"{exc.code}: {exc.read().decode()}")
print("KRA PIN found" if body["found"] else "KRA PIN not found", body.get("taxpayer_name") or "")
