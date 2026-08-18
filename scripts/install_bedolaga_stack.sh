#!/usr/bin/env bash
# Install Remnawave Panel + Caddy + Bedolaga Bot on a fresh Ubuntu server.
# Docs: https://docs.bedolagam.ru/getting-started/quickstart
#       https://docs.rw/install/remnawave-panel/
#
# Required env:
#   CABINET_DOMAIN=fastervpn.shop   (main domain = Bedolaga personal cabinet)
#   BOT_TOKEN=...                       (from @BotFather)
#   ADMIN_IDS=123456789                   (Telegram user id)
# Optional:
#   ADMIN_PANEL_DOMAIN=panel.fastervpn.shop  (Remnawave admin UI)
#   SUB_PUBLIC_DOMAIN=sub.fastervpn.shop     (subscription links)
#   REMNAWAVE_API_KEY=...                    (if already created in panel)
#   INSTALL_DIR=/root/remnawave-bedolaga-telegram-bot

set -euo pipefail

CABINET_DOMAIN="${CABINET_DOMAIN:-fastervpn.shop}"
ADMIN_PANEL_DOMAIN="${ADMIN_PANEL_DOMAIN:-panel.fastervpn.shop}"
SUB_PUBLIC_DOMAIN="${SUB_PUBLIC_DOMAIN:-sub.fastervpn.shop}"
INSTALL_DIR="${INSTALL_DIR:-/root/remnawave-bedolaga-telegram-bot}"
REMNAWAVE_DIR="${REMNAWAVE_DIR:-/opt/remnawave}"
CADDY_DIR="${CADDY_DIR:-/opt/remnawave/caddy}"

if [[ -z "${BOT_TOKEN:-}" ]]; then
  echo "ERROR: set BOT_TOKEN" >&2
  exit 1
fi
if [[ -z "${ADMIN_IDS:-}" ]]; then
  echo "ERROR: set ADMIN_IDS" >&2
  exit 1
fi

echo "==> Installing Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
apt-get update -qq
apt-get install -y -qq make git curl openssl

echo "==> Remnawave Panel at ${REMNAWAVE_DIR}"
mkdir -p "$REMNAWAVE_DIR"
cd "$REMNAWAVE_DIR"
if [[ ! -f docker-compose.yml ]]; then
  curl -fsSL -o docker-compose.yml \
    https://raw.githubusercontent.com/remnawave/backend/refs/heads/main/docker-compose-prod.yml
  curl -fsSL -o .env \
    https://raw.githubusercontent.com/remnawave/backend/refs/heads/main/.env.sample
fi

sed -i "s/^APP_SECRET=.*/APP_SECRET=$(openssl rand -hex 64)/" .env
sed -i "s/^METRICS_PASS=.*/METRICS_PASS=$(openssl rand -hex 64)/" .env
sed -i "s/^WEBHOOK_SECRET_HEADER=.*/WEBHOOK_SECRET_HEADER=$(openssl rand -hex 64)/" .env
pw=$(openssl rand -hex 24)
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$pw/" .env
sed -i "s|^\(DATABASE_URL=\"postgresql://postgres:\)[^@]*\(@.*\)|\1${pw}\2|" .env
sed -i "s|^FRONT_END_DOMAIN=.*|FRONT_END_DOMAIN=${ADMIN_PANEL_DOMAIN}|" .env
sed -i "s|^SUB_PUBLIC_DOMAIN=.*|SUB_PUBLIC_DOMAIN=${SUB_PUBLIC_DOMAIN}|" .env
sed -i "s|^PANEL_DOMAIN=.*|PANEL_DOMAIN=${ADMIN_PANEL_DOMAIN}|" .env || echo "PANEL_DOMAIN=${ADMIN_PANEL_DOMAIN}" >> .env

docker compose up -d
echo "Waiting for Remnawave..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:3001/health" >/dev/null 2>&1; then
    break
  fi
  sleep 3
done

echo "==> Caddy reverse proxy"
mkdir -p "$CADDY_DIR"
cat > "$CADDY_DIR/Caddyfile" <<CADDY
https://${CABINET_DOMAIN} {
    encode gzip zstd
    handle /api/* {
        uri strip_prefix /api
        reverse_proxy remnawave_bot:8080
    }
    handle {
        reverse_proxy cabinet_frontend:80
    }
}

https://${ADMIN_PANEL_DOMAIN} {
    encode gzip
    reverse_proxy * http://remnawave:3000
}

https://${SUB_PUBLIC_DOMAIN} {
    encode gzip
    reverse_proxy * http://remnawave-subscription-page:3010
}

:443 {
    tls internal
    respond 204
}
CADDY

cat > "$CADDY_DIR/docker-compose.yml" <<YAML
services:
  caddy:
    image: caddy:2.9
    container_name: caddy
    restart: always
    ports:
      - '0.0.0.0:443:443'
      - '0.0.0.0:80:80'
    networks:
      - remnawave-network
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy-ssl-data:/data

networks:
  remnawave-network:
    name: remnawave-network
    external: true

volumes:
  caddy-ssl-data:
    name: caddy-ssl-data
YAML

cd "$CADDY_DIR"
docker compose up -d

echo "==> Bedolaga Bot at ${INSTALL_DIR}"
if [[ ! -d "$INSTALL_DIR/.git" ]]; then
  git clone https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot.git "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"
git pull --ff-only || true

mkdir -p ./logs ./data ./data/backups ./data/referral_qr
chmod -R 755 ./logs ./data
chown -R 1000:1000 ./logs ./data 2>/dev/null || true

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -hex 16)}"
sed -i "s|^BOT_TOKEN=.*|BOT_TOKEN=${BOT_TOKEN}|" .env
sed -i "s|^ADMIN_IDS=.*|ADMIN_IDS=${ADMIN_IDS}|" .env
sed -i "s|^REMNAWAVE_API_URL=.*|REMNAWAVE_API_URL=http://remnawave:3000|" .env
CABINET_JWT="$(openssl rand -hex 32)"
sed -i "s|^CABINET_ENABLED=.*|CABINET_ENABLED=true|" .env || echo "CABINET_ENABLED=true" >> .env
sed -i "s|^CABINET_URL=.*|CABINET_URL=https://${CABINET_DOMAIN}|" .env || echo "CABINET_URL=https://${CABINET_DOMAIN}" >> .env
sed -i "s|^CABINET_JWT_SECRET=.*|CABINET_JWT_SECRET=${CABINET_JWT}|" .env || echo "CABINET_JWT_SECRET=${CABINET_JWT}" >> .env
sed -i "s|^CABINET_ALLOWED_ORIGINS=.*|CABINET_ALLOWED_ORIGINS=https://${CABINET_DOMAIN}|" .env || echo "CABINET_ALLOWED_ORIGINS=https://${CABINET_DOMAIN}" >> .env
if [[ -n "${REMNAWAVE_API_KEY:-}" ]]; then
  sed -i "s|^REMNAWAVE_API_KEY=.*|REMNAWAVE_API_KEY=${REMNAWAVE_API_KEY}|" .env
fi
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|" .env
sed -i "s|^BOT_RUN_MODE=.*|BOT_RUN_MODE=polling|" .env || echo "BOT_RUN_MODE=polling" >> .env

make up

echo "==> Bedolaga cabinet frontend"
docker pull ghcr.io/bedolaga-dev/bedolaga-cabinet:latest
cat > "$INSTALL_DIR/docker-compose.cabinet.yml" <<YAML
services:
  cabinet-frontend:
    image: ghcr.io/bedolaga-dev/bedolaga-cabinet:latest
    container_name: cabinet_frontend
    restart: unless-stopped
    networks:
      - bot_network
      - remnawave-network

networks:
  bot_network:
    external: true
    name: remnawave-bedolaga-telegram-bot_bot_network
  remnawave-network:
    external: true
    name: remnawave-network
YAML
cd "$INSTALL_DIR"
docker compose -f docker-compose.yml -f docker-compose.cabinet.yml up -d cabinet-frontend 2>/dev/null || \
  docker compose -f docker-compose.cabinet.yml up -d
docker network connect remnawave-bedolaga-telegram-bot_bot_network caddy 2>/dev/null || true
cd "$CADDY_DIR" && docker compose up -d

echo
echo "=============================================="
echo "Bedolaga cabinet (main): https://${CABINET_DOMAIN}"
echo "Remnawave admin:         https://${ADMIN_PANEL_DOMAIN}"
echo "Subscriptions:           https://${SUB_PUBLIC_DOMAIN}/{uuid}"
echo "Bot dir:                 ${INSTALL_DIR}"
echo
echo "Next steps:"
echo "1. Add DNS A-record: ${ADMIN_PANEL_DOMAIN} -> this server"
echo "2. BotFather -> Domain: ${CABINET_DOMAIN}"
echo "3. Open admin panel, create API key for bot"
echo "4. Set REMNAWAVE_API_KEY in ${INSTALL_DIR}/.env && docker compose restart bot"
echo "5. Or run: bash scripts/setup_bedolaga_cabinet.sh"
echo "=============================================="
