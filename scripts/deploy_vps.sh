#!/usr/bin/env bash
set -euo pipefail

DEPLOY_PATH="${DEPLOY_PATH:-/opt/biztrace}"
REPO_URL="${REPO_URL:-https://github.com/krutoinastile/jdkfkc.git}"

echo "==> Installing Docker if needed"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi

echo "==> Preparing project directory ${DEPLOY_PATH}"
mkdir -p "${DEPLOY_PATH}"
if [ ! -d "${DEPLOY_PATH}/.git" ]; then
  git clone "${REPO_URL}" "${DEPLOY_PATH}"
fi

cd "${DEPLOY_PATH}"
git fetch origin
git checkout cursor/business-chat-monitor-bde0 || git checkout main
git pull --ff-only || true

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from example — set BOT_TOKEN and ADMIN_IDS before starting."
fi

mkdir -p data
docker compose up -d --build --remove-orphans
docker compose ps
docker compose logs --tail=30
