#!/usr/bin/env bash
# Configure Gmail credentials for Email API and test SMTP connection
# Usage: sudo -u emailapi bash /opt/emailapi/deploy/config-gmail.sh
set -euo pipefail

APP_DIR="/opt/emailapi"
ENV_FILE="$APP_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Creating $ENV_FILE"
  cat > "$ENV_FILE" <<EOF
# Gmail Configuration
GMAIL_USER=
GMAIL_APP_PASSWORD=
EOF
  chmod 600 "$ENV_FILE"
fi

# Read existing values if present
source "$ENV_FILE" || true

read -rp "Enter Gmail address: " GMAIL_USER_INPUT
read -rsp "Enter Gmail App Password (16 chars, no spaces): " GMAIL_PASSWORD_INPUT
echo

# Normalize by removing spaces from app password
GMAIL_PASSWORD_INPUT="${GMAIL_PASSWORD_INPUT// /}"

# Write back to .env
cat > "$ENV_FILE" <<EOF
# Gmail Configuration
GMAIL_USER=$GMAIL_USER_INPUT
GMAIL_APP_PASSWORD=$GMAIL_PASSWORD_INPUT
EOF
chmod 600 "$ENV_FILE"
chown emailapi:emailapi "$ENV_FILE"

echo "==> Testing SMTP connection to Gmail..."
# Activate venv and run a tiny Python snippet to test login
source "$APP_DIR/venv/bin/activate"
python - <<'PY'
import os, smtplib, sys
user = os.getenv('GMAIL_USER')
password = os.getenv('GMAIL_APP_PASSWORD')
if not user or not password:
    print('❌ Missing GMAIL_USER or GMAIL_APP_PASSWORD')
    sys.exit(1)
try:
    server = smtplib.SMTP('smtp.gmail.com', 587, timeout=15)
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

echo "==> Restarting Email API service to load new credentials"
sudo systemctl restart emailapi
sudo systemctl status emailapi --no-pager

echo "✅ Gmail configuration complete"
