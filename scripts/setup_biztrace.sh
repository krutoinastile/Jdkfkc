#!/usr/bin/env bash
# Run on VPS:
#   BOT_TOKEN=xxx ADMIN_IDS=123 bash setup_biztrace.sh
set -euo pipefail

DEPLOY_PATH="${DEPLOY_PATH:-/opt/biztrace}"
REPO_URL="${REPO_URL:-https://github.com/krutoinastile/Jdkfkc.git}"
BRANCH="${BRANCH:-cursor/business-chat-monitor-bde0}"

: "${BOT_TOKEN:?Set BOT_TOKEN}"
: "${ADMIN_IDS:?Set ADMIN_IDS}"

echo "==> Installing Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi

echo "==> Cloning/updating repo"
mkdir -p "${DEPLOY_PATH}"
if [ ! -d "${DEPLOY_PATH}/.git" ]; then
  git clone "${REPO_URL}" "${DEPLOY_PATH}"
fi
cd "${DEPLOY_PATH}"
git fetch origin
git checkout "${BRANCH}"
git pull origin "${BRANCH}" || true

echo "==> Writing .env"
cat > .env << EOF
BOT_TOKEN=${BOT_TOKEN}
ADMIN_IDS=${ADMIN_IDS}
DATABASE_URL=sqlite+aiosqlite:///./data/biztrace.db
SUPPORT_URL=${SUPPORT_URL:-}
RATE_LIMIT_SECONDS=0.5
LOG_LEVEL=INFO
TRIAL_DAYS=3
SUBSCRIPTION_PRICE_TEXT=Свяжитесь с поддержкой для продления подписки.
EOF

mkdir -p data
docker compose down 2>/dev/null || true
docker compose up -d --build --remove-orphans
sleep 3
docker compose ps
docker compose logs --tail=20
