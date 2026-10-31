#!/usr/bin/env sh
# Usage: PROXY_URL=http://localhost:8000 PROXY_API_KEY=dev-key ./curl.sh A000000000B
PROXY_URL="${PROXY_URL:-http://localhost:8000}"
curl -sS -X POST "$PROXY_URL/v1/pin/verify" \
  -H "X-API-Key: $PROXY_API_KEY" -H "Content-Type: application/json" \
  -d "{\"pin\": \"${1:-A000000000B}\", \"consent\": true}"
echo
