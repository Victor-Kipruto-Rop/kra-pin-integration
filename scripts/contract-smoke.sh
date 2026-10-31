#!/usr/bin/env sh
set -eu
BASE_URL=${BASE_URL:-http://localhost:8000}
API_KEY=${PROXY_API_KEY:-dev-key}
curl --fail --silent "$BASE_URL/health" >/dev/null
curl --fail --silent -X POST "$BASE_URL/v1/pin/verify" -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' -d '{"pin":"A000000000B","consent":true}' >/dev/null
echo "Contract smoke checks passed: $BASE_URL"
