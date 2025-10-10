#!/usr/bin/env bash
# Email API automated installer for RHEL (EC2)
# Usage: sudo bash install-emailapi.sh -d emailapi.6ray.com -r <git_repo_url> [-b <branch>]
set -euo pipefail

DOMAIN=""
REPO=""
BRANCH="main"
APP_DIR="/opt/emailapi"
APP_USER="emailapi"

while getopts ":d:r:b:" opt; do
  case $opt in
    d) DOMAIN="$OPTARG" ;;
    r) REPO="$OPTARG" ;;
    b) BRANCH="$OPTARG" ;;
    *) echo "Usage: $0 -d <domain> -r <repo_url> [-b <branch>]"; exit 1 ;;
  esac
done

if [[ -z "$DOMAIN" || -z "$REPO" ]]; then
  echo "Usage: $0 -d <domain> -r <repo_url> [-b <branch>]"
  exit 1
fi

echo "==> Installing system packages"
DNF_PKGS=(python3 python3-pip git nginx firewalld policycoreutils-python-utils)
sudo dnf install -y "${DNF_PKGS[@]}"

echo "==> Ensuring firewall for HTTP/HTTPS"
sudo systemctl enable --now firewalld || true
sudo firewall-cmd --permanent --add-service=http || true
sudo firewall-cmd --permanent --add-service=https || true
sudo firewall-cmd --reload || true

echo "==> Enabling SELinux network connect for Nginx"
sudo setsebool -P httpd_can_network_connect on || true

echo "==> Creating app user: $APP_USER"
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  sudo useradd --system --create-home --shell /sbin/nologin "$APP_USER"
fi

echo "==> Preparing application directory: $APP_DIR"
sudo mkdir -p "$APP_DIR"
sudo chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "==> Cloning repository $REPO (branch: $BRANCH)"
  sudo -u "$APP_USER" git clone -b "$BRANCH" "$REPO" "$APP_DIR"
else
  echo "==> Updating repository"
  sudo -u "$APP_USER" git -C "$APP_DIR" fetch --all --prune
  sudo -u "$APP_USER" git -C "$APP_DIR" checkout "$BRANCH"
  sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
fi

# Check if repo cloned successfully
if [[ ! -f "$APP_DIR/requirements.txt" ]]; then
  echo "ERROR: requirements.txt not found. Repo clone may have failed."
  exit 1
fi

echo "==> Creating Python virtualenv"
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
source "$APP_DIR/venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$APP_DIR/requirements.txt"

if [[ ! -f "$APP_DIR/.env" ]]; then
  echo "==> Creating .env template (please edit after install)"
  cat | sudo tee "$APP_DIR/.env" >/dev/null <<EOF
# Gmail Configuration
GMAIL_USER=your_gmail@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password
# API access
API_KEY=replace_with_long_random_string
# Per-user API keys DB and admin token
API_KEYS_DB=/opt/emailapi/api_keys.db
ADMIN_TOKEN=replace_with_admin_token
# Recipient domain policy (comma-separated). Leave ALLOW_DOMAINS empty to allow all by default.
ALLOW_DOMAINS=
BLOCK_DOMAINS=
# Admin panel settings
PANEL_PASSWORD=771008
ENV_FILE_PATH=/opt/emailapi/.env
EOF
  sudo chown "$APP_USER":"$APP_USER" "$APP_DIR/.env"
  sudo chmod 600 "$APP_DIR/.env"
fi

echo "==> Installing systemd service"
if [[ ! -f "$APP_DIR/deploy/emailapi.service" ]]; then
  echo "ERROR: emailapi.service not found in $APP_DIR/deploy/"
  exit 1
fi
sudo cp "$APP_DIR/deploy/emailapi.service" /etc/systemd/system/emailapi.service
sudo systemctl daemon-reload
sudo systemctl enable --now emailapi

echo "==> Installing Nginx site config for $DOMAIN"
if [[ ! -f "$APP_DIR/deploy/emailapi.nginx.conf" ]]; then
  echo "ERROR: emailapi.nginx.conf not found in $APP_DIR/deploy/"
  exit 1
fi
sudo cp "$APP_DIR/deploy/emailapi.nginx.conf" "/etc/nginx/conf.d/emailapi.conf"
sudo sed -i "s/server_name .*/server_name $DOMAIN;/" "/etc/nginx/conf.d/emailapi.conf"

# Ensure rate limit zone exists before first nginx config test
if ! sudo grep -q "limit_req_zone .*zone=emailapi" /etc/nginx/nginx.conf; then
  echo "==> Injecting rate limit zone into /etc/nginx/nginx.conf"
  if ! sudo grep -q "http\s*{" /etc/nginx/nginx.conf; then
    echo "ERROR: No 'http {' block found in /etc/nginx/nginx.conf. Cannot inject rate limit zone."
    exit 1
  fi
  BACKUP="/etc/nginx/nginx.conf.bak.$(date +%s)"
  sudo cp /etc/nginx/nginx.conf "$BACKUP"
  # Insert immediately after opening http { block
  sudo awk '/http\s*\{/ && !x{print;print "    limit_req_zone \$binary_remote_addr zone=emailapi:10m rate=5r/s;";x=1;next}1' /etc/nginx/nginx.conf | sudo tee /tmp/nginx.conf >/dev/null
  sudo mv /tmp/nginx.conf /etc/nginx/nginx.conf
  sudo chown root:root /etc/nginx/nginx.conf
  sudo chmod 644 /etc/nginx/nginx.conf
  if ! sudo nginx -t; then
    echo "ERROR: Nginx config test failed after injection. Restoring backup."
    sudo cp "$BACKUP" /etc/nginx/nginx.conf
    exit 1
  fi
fi

sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx

# Skipping certificate provisioning (TLS assumed to be managed externally)
echo "==> Skipping certificate provisioning; HTTPS expected to be pre-configured"

# Ensure API_KEY not left as placeholder
if grep -q "API_KEY=replace_with_long_random_string" "$APP_DIR/.env"; then
  echo "==> Generating random API key"
  RANDKEY=$(openssl rand -hex 32)
  sudo sed -i "s/API_KEY=replace_with_long_random_string/API_KEY=$RANDKEY/" "$APP_DIR/.env"
fi

# Ensure admin token
if grep -q "ADMIN_TOKEN=replace_with_admin_token" "$APP_DIR/.env"; then
  echo "==> Generating admin token"
  ADM=$(openssl rand -hex 32)
  sudo sed -i "s/ADMIN_TOKEN=replace_with_admin_token/ADMIN_TOKEN=$ADM/" "$APP_DIR/.env"
fi

# Helpful guidance for nginx rate limit zone and HSTS
echo "==> NOTE: Rate limiting is configured via a shared zone named 'emailapi'. If you need to change rates, edit /etc/nginx/nginx.conf and adjust the line:"
echo "    limit_req_zone \$binary_remote_addr zone=emailapi:10m rate=5r/s;"
echo "   Then reload nginx. HSTS can be enabled on the HTTPS server block with:"
echo "    add_header Strict-Transport-Security 'max-age=31536000; includeSubDomains; preload' always;"

# Attempt to add HSTS to HTTPS server block (best-effort)
CONF_HTTPS=$(sudo grep -rl "server_name $DOMAIN;" /etc/nginx | head -n1 || true)
if [[ -n "$CONF_HTTPS" ]]; then
  if ! sudo grep -q "Strict-Transport-Security" "$CONF_HTTPS"; then
    echo "==> Adding HSTS to $CONF_HTTPS"
    sudo cp "$CONF_HTTPS" "$CONF_HTTPS.bak.$(date +%s)"
    sudo awk '/server\s*\{/{inserver=1} inserver && /server_name/{print;print "    add_header Strict-Transport-Security \x27max-age=31536000; includeSubDomains; preload\x27 always;"; next} {print} /\}/{inserver=0}' "$CONF_HTTPS" | sudo tee /tmp/emailapi_https.conf >/dev/null
    sudo mv /tmp/emailapi_https.conf "$CONF_HTTPS"
  fi
fi

sudo nginx -t && sudo systemctl reload nginx || true

cat <<SUMMARY

✅ Installation complete.

Next steps:
1) Edit credentials: sudo nano $APP_DIR/.env  (use your Gmail + app password)
2) Check service:    sudo systemctl status emailapi --no-pager
   Logs:             journalctl -u emailapi -f
3) Verify HTTP:      curl -s http://$DOMAIN/health
4) Verify HTTPS:     curl -s https://$DOMAIN/health
5) Test email:
   curl -X POST https://$DOMAIN/send-email \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $(grep ^API_KEY= "$APP_DIR/.env" | cut -d= -f2)" \
     -d '{"to_email":"self@6ray.com","subject":"API Test","message":"Hello from Email API","from_name":"Email API"}'

SUMMARY

echo "==> Launching Gmail configuration"
sudo -u "$APP_USER" bash "$APP_DIR/deploy/config-gmail.sh" || true
echo "ℹ️  You can re-run later with: sudo -u $APP_USER bash $APP_DIR/deploy/config-gmail.sh"
