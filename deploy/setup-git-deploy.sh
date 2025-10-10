#!/usr/bin/env bash
# One-time setup for push-to-deploy via a bare Git repo on the server.
# Usage: sudo bash setup-git-deploy.sh -k "<your-ssh-public-key>" [-u emaildeploy] [-w /opt/emailapi] [-s emailapi] [-b main]
set -euo pipefail

DEPLOY_USER="emaildeploy"
WORK_TREE="/opt/emailapi"
SERVICE_NAME="emailapi"
BRANCH="main"
PUBKEY=""

while getopts ":k:u:w:s:b:" opt; do
  case $opt in
    k) PUBKEY="$OPTARG" ;;
    u) DEPLOY_USER="$OPTARG" ;;
    w) WORK_TREE="$OPTARG" ;;
    s) SERVICE_NAME="$OPTARG" ;;
    b) BRANCH="$OPTARG" ;;
    *) echo "Usage: $0 -k '<ssh-pub-key>' [-u deployuser] [-w /opt/emailapi] [-s emailapi] [-b main]"; exit 1 ;;
  esac
done

if [[ -z "$PUBKEY" ]]; then
  echo "ERROR: Missing -k '<ssh-pub-key>' argument."
  echo "Example: sudo bash $0 -k 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... you@host'"
  exit 2
fi

echo "==> Verifying prerequisites"
command -v git >/dev/null || { echo "git is required"; exit 3; }

GIT_SHELL=$(command -v git-shell || true)
if [[ -z "$GIT_SHELL" ]]; then
  # Common fallback path
  if [[ -x "/usr/bin/git-shell" ]]; then
    GIT_SHELL="/usr/bin/git-shell"
  else
    echo "ERROR: git-shell not found"; exit 4
  fi
fi

echo "==> Creating deploy user '$DEPLOY_USER' with shell $GIT_SHELL"
if ! id -u "$DEPLOY_USER" >/dev/null 2>&1; then
  sudo useradd --create-home --shell "$GIT_SHELL" "$DEPLOY_USER"
fi

DEPLOY_HOME=$(getent passwd "$DEPLOY_USER" | cut -d: -f6)
BARE_REPO="$DEPLOY_HOME/emailapi.git"

echo "==> Installing SSH key for $DEPLOY_USER"
sudo -u "$DEPLOY_USER" mkdir -p "$DEPLOY_HOME/.ssh"
sudo -u "$DEPLOY_USER" chmod 700 "$DEPLOY_HOME/.ssh"
echo "$PUBKEY" | sudo tee -a "$DEPLOY_HOME/.ssh/authorized_keys" >/dev/null
sudo chown "$DEPLOY_USER":"$DEPLOY_USER" "$DEPLOY_HOME/.ssh/authorized_keys"
sudo chmod 600 "$DEPLOY_HOME/.ssh/authorized_keys"

echo "==> Initializing bare repo at $BARE_REPO"
if [[ ! -d "$BARE_REPO" ]]; then
  sudo -u "$DEPLOY_USER" git init --bare "$BARE_REPO"
fi

echo "==> Creating root-only deploy helper at /usr/local/bin/${SERVICE_NAME}-postdeploy.sh"
POSTDEPLOY="/usr/local/bin/${SERVICE_NAME}-postdeploy.sh"
sudo tee "$POSTDEPLOY" >/dev/null <<EOSH
#!/usr/bin/env bash
set -euo pipefail
WORK_TREE="$WORK_TREE"
SERVICE_NAME="$SERVICE_NAME"

if [[ -d "\"$WORK_TREE\"/.git" ]]; then
  echo "Removing embedded .git in work tree to avoid conflicts"
  rm -rf "\"$WORK_TREE\"/.git"
fi

if [[ -x "\"$WORK_TREE\"/venv/bin/activate" ]]; then
  sudo -u ${SERVICE_NAME} bash -lc "source '$WORK_TREE/venv/bin/activate' && pip install --upgrade pip && pip install -r '$WORK_TREE/requirements.txt'"
fi

systemctl restart "$SERVICE_NAME"
EOSH
sudo chmod 0755 "$POSTDEPLOY"
sudo chown root:root "$POSTDEPLOY"

echo "==> Granting deploy permission via sudoers for $DEPLOY_USER"
SUDOERS_FILE="/etc/sudoers.d/${DEPLOY_USER}-${SERVICE_NAME}-deploy"
echo "${DEPLOY_USER} ALL=(root) NOPASSWD: $POSTDEPLOY" | sudo tee "$SUDOERS_FILE" >/dev/null
sudo chmod 440 "$SUDOERS_FILE"

echo "==> Installing post-receive hook"
HOOK_PATH="$BARE_REPO/hooks/post-receive"
sudo tee "$HOOK_PATH" >/dev/null <<'EOHOOK'
#!/usr/bin/env bash
set -euo pipefail

WORK_TREE="__WORK_TREE__"
SERVICE_NAME="__SERVICE_NAME__"
BRANCH="__BRANCH__"

read oldrev newrev refname
if [[ "$refname" == "refs/heads/${BRANCH}" ]]; then
  echo "Deploying $BRANCH to $WORK_TREE"
  GIT_WORK_TREE="$WORK_TREE" git checkout -f "$BRANCH"
  echo "Running post-deploy tasks"
  sudo "/usr/local/bin/${SERVICE_NAME}-postdeploy.sh"
else
  echo "Ref $refname not targeted; skipping deploy"
fi
EOHOOK

# Token replace vars in hook (avoid shell expansion issues with a separate step)
sudo sed -i "s#__WORK_TREE__#$WORK_TREE#g" "$HOOK_PATH"
sudo sed -i "s#__SERVICE_NAME__#$SERVICE_NAME#g" "$HOOK_PATH"
sudo sed -i "s#__BRANCH__#$BRANCH#g" "$HOOK_PATH"
sudo chmod +x "$HOOK_PATH"
sudo chown -R "$DEPLOY_USER":"$DEPLOY_USER" "$BARE_REPO"

echo "==> Push-to-deploy is ready. Add a remote from your local repo and push:"
SERVER_HOST="$(hostname -f || hostname)"
cat <<EOM

From your local machine (within your project repo):

  git remote add ec ssh://${DEPLOY_USER}@${SERVER_HOST}:${BARE_REPO}
  git push ec ${BRANCH}

This will checkout into ${WORK_TREE}, install dependencies, and restart '${SERVICE_NAME}'.
EOM
