#!/usr/bin/env bash
# One-shot test sender for Email API
# - Creates a per-user API key via admin API if -k not supplied
# - Sends an email through the API and prints the response
#
# Usage:
#   sudo bash /opt/emailapi/deploy/test-send.sh -t dd@6ray.com -s "test" -m "API" \
#       [-a https://emailapi.6ray.com] [-u cli-test] [-k key_id.secret] [-A ADMIN_TOKEN]

set -euo pipefail

APP_DIR="/opt/emailapi"
ENV_FILE="$APP_DIR/.env"
API="http://127.0.0.1:8002"   # default local API
TO=""
SUBJECT=""
MESSAGE=""
USERNAME="cli-test-$(date +%s)"
API_KEY=""
ADMIN_OVERRIDE=""

usage() {
  grep '^#' "$0" | sed 's/^# \{0,1\}//'
}

while getopts ":a:t:s:m:u:k:A:h" opt; do
  case $opt in
    a) API="$OPTARG" ;;
    t) TO="$OPTARG" ;;
    s) SUBJECT="$OPTARG" ;;
    m) MESSAGE="$OPTARG" ;;
    u) USERNAME="$OPTARG" ;;
    k) API_KEY="$OPTARG" ;;
    A) ADMIN_OVERRIDE="$OPTARG" ;;
    h) usage; exit 0 ;;
    *) echo "Unknown option -$OPTARG"; usage; exit 1 ;;
  esac
done

if [[ -z "$TO" || -z "$SUBJECT" || -z "$MESSAGE" ]]; then
  echo "ERROR: Missing required -t, -s, or -m" >&2
  usage
  exit 2
fi

if [[ -z "$API_KEY" ]]; then
  # Create a per-user key using admin API
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: $ENV_FILE not found" >&2
    exit 3
  fi
  # Resolve admin token: CLI override > env var > .env file
  if [[ -n "$ADMIN_OVERRIDE" ]]; then
    ADMIN_TOKEN="$ADMIN_OVERRIDE"
  elif [[ -n "${ADMIN_TOKEN:-}" ]]; then
    ADMIN_TOKEN="$ADMIN_TOKEN"
  else
    ADMIN_TOKEN=$(grep -E '^ADMIN_TOKEN=' "$ENV_FILE" | cut -d= -f2- || true)
  fi
  if [[ -z "$ADMIN_TOKEN" ]]; then
    echo "ERROR: ADMIN_TOKEN not found in $ENV_FILE; cannot create key automatically" >&2
    exit 3
  fi
  echo "==> Creating per-user API key for '$USERNAME' via $API"
  CREATE_PAYLOAD=$(printf '{"username":"%s"}' "$USERNAME")
  RESP=$(curl -fsS -X POST "$API/admin/keys/create" \
    -H "Content-Type: application/json" \
    -H "X-Admin-Token: $ADMIN_TOKEN" \
    --data "$CREATE_PAYLOAD")
  API_KEY=$(printf '%s' "$RESP" | sed -n 's/.*"api_key"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
  if [[ -z "$API_KEY" ]]; then
    echo "ERROR: Failed to create API key. Response:" >&2
    echo "  $RESP" >&2
    exit 4
  fi
  echo "✅ API key created: $API_KEY"
fi

echo "==> Sending email to $TO via $API"
PAYLOAD=$(cat <<JSON
{
  "to_email": "$TO",
  "subject": "$SUBJECT",
  "message": "$MESSAGE",
  "from_name": "Email API"
}
JSON
)

HTTP_CODE=$(curl -sS -o /tmp/emailapi_test_send.json -w "%{http_code}" \
  -X POST "$API/send-email" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  --data "$PAYLOAD")

echo "HTTP $HTTP_CODE"
cat /tmp/emailapi_test_send.json | sed 's/.*/  &/'

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "❌ Send failed (HTTP $HTTP_CODE). Check service logs: journalctl -u emailapi -n 50 --no-pager" >&2
  exit 5
fi

echo "✅ Send request accepted. Check recipient inbox."