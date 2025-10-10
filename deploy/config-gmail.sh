#!/usr/bin/env bash
# Configure Gmail credentials for Email API, restart the service, and run live tests.
# Usage: sudo bash /opt/emailapi/deploy/config-gmail.sh
set -euo pipefail

APP_DIR="/opt/emailapi"
ENV_FILE="$APP_DIR/.env"
SERVICE_NAME="emailapi"
API_URL_LOCAL="http://127.0.0.1:8002"

require_file() {
  if [[ ! -f "$1" ]]; then
    echo "ERROR: Missing file: $1" >&2
    exit 1
  fi
}

echo "==> Preparing environment"
require_file "$APP_DIR/venv/bin/activate"
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"
chown emailapi:emailapi "$ENV_FILE" || true

# Load existing values without exporting to env
GMAIL_USER_EXISTING=$(grep -E '^GMAIL_USER=' "$ENV_FILE" | cut -d= -f2- || true)

read -rp "Enter Gmail address${GMAIL_USER_EXISTING:+ [$GMAIL_USER_EXISTING]}: " GMAIL_USER_INPUT || true
GMAIL_USER_INPUT=${GMAIL_USER_INPUT:-$GMAIL_USER_EXISTING}
if [[ -z "${GMAIL_USER_INPUT}" ]]; then
  echo "ERROR: Gmail address is required" >&2
  exit 1
fi

read -rsp "Enter Gmail App Password (16 chars, no spaces): " GMAIL_PASSWORD_INPUT || true
echo
GMAIL_PASSWORD_INPUT="${GMAIL_PASSWORD_INPUT// /}"
if [[ -z "${GMAIL_PASSWORD_INPUT}" ]]; then
  echo "ERROR: App password is required" >&2
  exit 1
fi

read -rp "Enter a test recipient email (default: $GMAIL_USER_INPUT): " TEST_RECIP || true
TEST_RECIP=${TEST_RECIP:-$GMAIL_USER_INPUT}

echo "==> Updating $ENV_FILE (preserving other settings)"
if grep -q '^GMAIL_USER=' "$ENV_FILE"; then
  sed -i "s|^GMAIL_USER=.*|GMAIL_USER=$GMAIL_USER_INPUT|" "$ENV_FILE"
else
  echo "GMAIL_USER=$GMAIL_USER_INPUT" >> "$ENV_FILE"
fi

if grep -q '^GMAIL_APP_PASSWORD=' "$ENV_FILE"; then
  sed -i "s|^GMAIL_APP_PASSWORD=.*|GMAIL_APP_PASSWORD=$GMAIL_PASSWORD_INPUT|" "$ENV_FILE"
else
  echo "GMAIL_APP_PASSWORD=$GMAIL_PASSWORD_INPUT" >> "$ENV_FILE"
fi

chmod 600 "$ENV_FILE"
chown emailapi:emailapi "$ENV_FILE" || true

echo "==> Testing SMTP authentication with Gmail"
source "$APP_DIR/venv/bin/activate"
python - <<'PY'
import os, smtplib, sys
from pathlib import Path
env_path = Path('/opt/emailapi/.env')
env = {}
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if '=' in line and not line.strip().startswith('#'):
            k,v = line.split('=',1)
            env[k.strip()] = v.strip()
user = env.get('GMAIL_USER')
password = env.get('GMAIL_APP_PASSWORD')
if not user or not password:
    print('❌ Missing GMAIL_USER or GMAIL_APP_PASSWORD in .env')
    sys.exit(1)
try:
    server = smtplib.SMTP('smtp.gmail.com', 587, timeout=20)
    server.starttls()
    server.login(user, password)
    server.quit()
    print('✅ Gmail SMTP authentication successful for', user)
except smtplib.SMTPAuthenticationError as e:
    print('❌ Authentication failed:', e)
    sys.exit(2)
except Exception as e:
    print('❌ Connection error:', e)
    sys.exit(3)
PY

echo "==> Restarting service to apply credentials"
sudo systemctl restart "$SERVICE_NAME"
sleep 1
sudo systemctl --no-pager --full status "$SERVICE_NAME" || true

echo "==> Verifying API health"
if ! curl -fsS "$API_URL_LOCAL/health" >/dev/null; then
  echo "❌ API health check failed at $API_URL_LOCAL/health" >&2
  journalctl -u "$SERVICE_NAME" -n 50 --no-pager || true
  exit 4
fi
echo "✅ API is healthy"

echo "==> Sending a test email via the API"
API_KEY=$(grep -E '^API_KEY=' "$ENV_FILE" | cut -d= -f2- || true)
if [[ -z "$API_KEY" ]]; then
  echo "❌ API_KEY not found in $ENV_FILE" >&2
  exit 5
fi

PAYLOAD=$(cat <<JSON
{
  "to_email": "$TEST_RECIP",
  "subject": "Email API setup test",
  "message": "Hello from Email API setup script at $(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "from_name": "Email API Setup"
}
JSON
)

HTTP_CODE=$(curl -sS -o /tmp/emailapi_send_test.json -w "%{http_code}" \
  -X POST "$API_URL_LOCAL/send-email" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  --data "$PAYLOAD")

if [[ "$HTTP_CODE" == "200" ]]; then
  echo "✅ Test email requested successfully. Response:"
  cat /tmp/emailapi_send_test.json | sed 's/.*/    &/'
else
  echo "❌ Test email failed with HTTP $HTTP_CODE. Response:"
  cat /tmp/emailapi_send_test.json | sed 's/.*/    &/'
  exit 6
fi

echo "✅ Gmail configuration and end-to-end test completed"
