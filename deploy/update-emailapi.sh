#!/usr/bin/env bash
# Update Email API code & restart service
# Usage: sudo bash /opt/emailapi/deploy/update-emailapi.sh [branch]
set -euo pipefail

APP_DIR="/opt/emailapi"
BRANCH="${1:-main}"
APP_USER="emailapi"

if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "Error: $APP_DIR is not a git repo"
  exit 1
fi

echo "==> Switching to branch $BRANCH"
sudo -u "$APP_USER" git -C "$APP_DIR" fetch --all --prune
sudo -u "$APP_USER" git -C "$APP_DIR" checkout "$BRANCH"
sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only

if [[ -f "$APP_DIR/requirements.txt" ]]; then
  echo "==> Updating Python dependencies"
  source "$APP_DIR/venv/bin/activate"
  python -m pip install --upgrade pip
  python -m pip install -r "$APP_DIR/requirements.txt"
fi

echo "==> Restarting service"
sudo systemctl restart emailapi
sudo systemctl status emailapi --no-pager
