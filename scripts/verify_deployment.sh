#!/usr/bin/env sh
set -eu
BASE_URL="${1:?Usage: ./scripts/verify_deployment.sh https://monitor.example.com}"
case "$BASE_URL" in
  https://*) ;;
  *) echo 'Public deployment requires an https:// URL' >&2; exit 2 ;;
esac
printf 'Checking %s\n' "$BASE_URL"
curl --fail --silent --show-error --max-time 10 "$BASE_URL/health" | grep -q '"status":"ok"'
printf 'PASS /health\n'
response="$(curl --silent --show-error --max-time 10 -o /dev/null -w '%{http_code}' "$BASE_URL/api/v1/monitors")"
[ "$response" = '401' ] || { echo "FAIL: unauthenticated API status $response (expected 401)" >&2; exit 1; }
printf 'PASS unauthenticated API returns HTTP 401\n'
curl --fail --silent --show-error --max-time 10 "$BASE_URL/" >/dev/null
printf 'PASS dashboard responds\n'
printf 'NOTE: this is a basic smoke test, not a penetration test or comprehensive security assessment.\n'
