#!/usr/bin/env bash
# Deploy BTC Trading Bot to a VPS/dedicated server over SSH.
#
# Usage (from your machine or Cloud Agent):
#   export DEPLOY_HOST=1.2.3.4
#   export DEPLOY_USER=root
#   export DEPLOY_PATH=/opt/btc-trading-bot
#   export DEPLOY_BRANCH=cursor/bingx-alerts-bde0
#   bash scripts/deploy_dedik.sh
#
# Optional: DEPLOY_SSH_KEY=~/.ssh/id_ed25519
# Requires: ssh, rsync, git clone access to GitHub repo

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DEPLOY_HOST="${DEPLOY_HOST:?Set DEPLOY_HOST (server IP or hostname)}"
DEPLOY_USER="${DEPLOY_USER:-root}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/btc-trading-bot}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-cursor/bingx-alerts-bde0}"
DEPLOY_SSH_KEY="${DEPLOY_SSH_KEY:-}"
REPO_URL="${REPO_URL:-https://github.com/krutoinastile/Jdkfkc.git}"

SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)
if [[ -n "$DEPLOY_SSH_KEY" ]]; then
  SSH_OPTS+=(-i "$DEPLOY_SSH_KEY")
fi

SSH=(ssh "${SSH_OPTS[@]}" "${DEPLOY_USER}@${DEPLOY_HOST}")
RSYNC_SSH="ssh ${SSH_OPTS[*]}"

echo "==> Deploying to ${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH} (branch ${DEPLOY_BRANCH})"

# Preserve .env from server if exists; otherwise upload local .env
ENV_BACKUP=""
if "${SSH[@]}" "test -f ${DEPLOY_PATH}/.env" 2>/dev/null; then
  echo "==> Keeping existing .env on server"
else
  if [[ -f "$ROOT/.env" ]]; then
    echo "==> Uploading local .env (first deploy)"
    ENV_BACKUP=1
  else
    echo "ERROR: No .env on server and no local .env found" >&2
    exit 1
  fi
fi

echo "==> Preparing server directories"
"${SSH[@]}" bash -s <<REMOTE
set -euo pipefail
mkdir -p "${DEPLOY_PATH}"
if ! command -v python3 >/dev/null; then
  apt-get update -qq && apt-get install -y -qq python3 python3-pip python3-venv git rsync
fi
REMOTE

if [[ -d "$ROOT/.git" ]]; then
  echo "==> Rsync project files"
  rsync -az --delete \
    --exclude '.git' \
    --exclude 'data/' \
    --exclude '__pycache__' \
    --exclude '.env' \
    -e "$RSYNC_SSH" \
    "$ROOT/" "${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/"
else
  echo "==> Git clone/pull on server"
  "${SSH[@]}" bash -s <<REMOTE
set -euo pipefail
if [[ -d "${DEPLOY_PATH}/.git" ]]; then
  cd "${DEPLOY_PATH}"
  git fetch origin
  git checkout "${DEPLOY_BRANCH}"
  git pull origin "${DEPLOY_BRANCH}"
else
  git clone -b "${DEPLOY_BRANCH}" "${REPO_URL}" "${DEPLOY_PATH}"
fi
REMOTE
fi

if [[ -n "${ENV_BACKUP:-}" ]]; then
  rsync -az -e "$RSYNC_SSH" "$ROOT/.env" "${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/.env"
fi

echo "==> Install deps, stop old bot, start supervisor"
"${SSH[@]}" bash -s <<REMOTE
set -euo pipefail
cd "${DEPLOY_PATH}"
mkdir -p data/logs

python3 -m venv .venv 2>/dev/null || true
if [[ -d .venv ]]; then
  source .venv/bin/activate
fi
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Stop duplicate instances (Telegram allows only one poller)
pkill -f "python3 -m app.main" 2>/dev/null || true
pkill -f "supervise_bot.sh" 2>/dev/null || true
sleep 2

# systemd (preferred)
if command -v systemctl >/dev/null && [[ \$(id -u) -eq 0 ]]; then
  cat > /etc/systemd/system/btc-trading-bot.service <<'UNIT'
[Unit]
Description=BTC Trading Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${DEPLOY_PATH}
Environment=PATH=${DEPLOY_PATH}/.venv/bin:/usr/local/bin:/usr/bin
ExecStart=/bin/bash ${DEPLOY_PATH}/scripts/supervise_bot.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable btc-trading-bot
  systemctl restart btc-trading-bot
  sleep 3
  systemctl --no-pager status btc-trading-bot || true
else
  # tmux fallback
  if ! command -v tmux >/dev/null; then
    apt-get install -y -qq tmux 2>/dev/null || true
  fi
  tmux kill-session -t btc-trading-bot 2>/dev/null || true
  tmux new-session -d -s btc-trading-bot "cd ${DEPLOY_PATH} && bash scripts/supervise_bot.sh"
fi

echo "==> Last log lines:"
tail -15 data/logs/bot-supervisor.log 2>/dev/null || echo "(no logs yet)"
REMOTE

echo "==> Deploy complete. Bot should be running on ${DEPLOY_HOST}"
