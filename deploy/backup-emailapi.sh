#!/usr/bin/env bash
# Backup Email API deployment: app config, DB, Nginx confs, systemd unit, and TLS certs
# Usage: sudo bash /opt/emailapi/deploy/backup-emailapi.sh [--dest /root]

set -euo pipefail

DEST_DIR="/root"
APP_DIR="/opt/emailapi"
NGX_DIR="/etc/nginx"
CONF_D="$NGX_DIR/conf.d"
SYSTEMD_UNIT="/etc/systemd/system/emailapi.service"

while [[ ${1:-} ]]; do
  case "$1" in
    --dest) DEST_DIR="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: sudo bash $0 [--dest /path]"; exit 0 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo)." >&2
  exit 1
fi

mkdir -p "$DEST_DIR"
TS=$(date -u +%Y%m%d-%H%M%S)
ARCHIVE="$DEST_DIR/emailapi-backup-$TS.tgz"

echo "==> Building backup list"
PATHS=()

# Core app dir (we'll exclude venv/.git caches at tar time)
if [[ -d "$APP_DIR" ]]; then
  PATHS+=("opt/emailapi")
fi

# .env and DB path (in case DB is outside)
ENV_FILE="$APP_DIR/.env"
DB_PATH="$APP_DIR/api_keys.db"
if [[ -f "$ENV_FILE" ]]; then
  ENV_DB=$(grep -E '^API_KEYS_DB=' "$ENV_FILE" | cut -d= -f2- || true)
  if [[ -n "$ENV_DB" ]]; then
    DB_PATH="$ENV_DB"
  fi
fi
if [[ -f "$ENV_FILE" ]]; then PATHS+=("opt/emailapi/.env"); fi
if [[ -f "$DB_PATH" ]]; then PATHS+=("${DB_PATH#/}"); fi

# Nginx confs for this app
[[ -f "$CONF_D/emailapi.conf" ]] && PATHS+=("etc/nginx/conf.d/emailapi.conf")
[[ -f "$CONF_D/emailapi-https.conf" ]] && PATHS+=("etc/nginx/conf.d/emailapi-https.conf")

# Systemd unit
[[ -f "$SYSTEMD_UNIT" ]] && PATHS+=("${SYSTEMD_UNIT#/}")

# TLS certificates referenced in https conf (if present)
CERT_FILES=()
if [[ -f "$CONF_D/emailapi-https.conf" ]]; then
  CERT_FILES+=( $(awk '/ssl_certificate(_key)?/ {print $2}' "$CONF_D/emailapi-https.conf" | tr -d ';' || true) )
fi
for f in "${CERT_FILES[@]:-}"; do
  [[ -f "$f" ]] && PATHS+=("${f#/}")
done

if [[ ${#PATHS[@]} -eq 0 ]]; then
  echo "Nothing to backup (no expected files found)." >&2
  exit 2
fi

echo "==> Creating $ARCHIVE"
tar -C / -czf "$ARCHIVE" \
  --exclude='opt/emailapi/venv' \
  --exclude='opt/emailapi/.git' \
  --exclude='opt/emailapi/__pycache__' \
  --exclude='opt/emailapi/**/*.pyc' \
  "${PATHS[@]}"

echo "==> Contents (top level)"
tar -tf "$ARCHIVE" | sed -n '1,50p'

cat <<EOT

✅ Backup complete: $ARCHIVE

Restore (careful: overwrites existing files):
  sudo tar -C / -xzf $ARCHIVE
  sudo systemctl daemon-reload
  sudo systemctl restart emailapi
  sudo nginx -t && sudo systemctl reload nginx

Notes:
- Virtualenv is excluded to keep backups small; recreate with: source /opt/emailapi/venv/bin/activate || python3 -m venv /opt/emailapi/venv && source /opt/emailapi/venv/bin/activate && pip install -r /opt/emailapi/requirements.txt
- Certificates are included only if referenced in emailapi-https.conf
- DB path is resolved from API_KEYS_DB in .env when present
EOT