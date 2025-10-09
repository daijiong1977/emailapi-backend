#!/usr/bin/env bash
# Uninstall Email API and clean up
# Usage: sudo bash /opt/emailapi/deploy/uninstall-emailapi.sh
set -euo pipefail

APP_DIR="/opt/emailapi"
APP_USER="emailapi"

read -rp "This will stop services and remove $APP_DIR. Continue? (y/N) " ans
if [[ "${ans:-N}" != "y" && "${ans:-N}" != "Y" ]]; then
  echo "Aborted"
  exit 0
fi

echo "==> Stopping and disabling service"
sudo systemctl disable --now emailapi || true
sudo rm -f /etc/systemd/system/emailapi.service
sudo systemctl daemon-reload

echo "==> Removing Nginx config"
sudo rm -f /etc/nginx/conf.d/emailapi.conf
sudo systemctl reload nginx || true

echo "==> Removing application directory"
sudo rm -rf "$APP_DIR"

if id -u "$APP_USER" >/dev/null 2>&1; then
  echo "==> Removing user $APP_USER (home may remain if other files exist)"
  sudo userdel "$APP_USER" || true
fi

echo "✅ Uninstall complete"
