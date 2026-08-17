#!/usr/bin/env bash
# Configure Bedolaga personal cabinet on the main domain and split services:
#   CABINET_DOMAIN      -> Bedolaga web cabinet (default: panel.fastervpn.shop)
#   ADMIN_PANEL_DOMAIN  -> Remnawave admin UI (default: admin.fastervpn.shop)
#   SUB_PUBLIC_DOMAIN   -> Remnawave subscription page (default: sub.fastervpn.shop)
#
# Run on the VPS as root after Remnawave + Bedolaga bot are installed.

set -euo pipefail

CABINET_DOMAIN="${CABINET_DOMAIN:-panel.fastervpn.shop}"
ADMIN_PANEL_DOMAIN="${ADMIN_PANEL_DOMAIN:-admin.fastervpn.shop}"
SUB_PUBLIC_DOMAIN="${SUB_PUBLIC_DOMAIN:-sub.fastervpn.shop}"
BOT_DIR="${BOT_DIR:-/root/remnawave-bedolaga-telegram-bot}"
CADDY_DIR="${CADDY_DIR:-/opt/remnawave/caddy}"
REMNAWAVE_DIR="${REMNAWAVE_DIR:-/opt/remnawave}"
CABINET_STATIC_DIR="${CABINET_STATIC_DIR:-/srv/cabinet}"
BOT_USERNAME="${BOT_USERNAME:-chatgptirobot}"

if [[ ! -d "$BOT_DIR" ]]; then
  echo "ERROR: bot directory not found: $BOT_DIR" >&2
  exit 1
fi

echo "==> Remnawave domains: admin=${ADMIN_PANEL_DOMAIN}, sub=${SUB_PUBLIC_DOMAIN}"
cd "$REMNAWAVE_DIR"
sed -i "s|^FRONT_END_DOMAIN=.*|FRONT_END_DOMAIN=${ADMIN_PANEL_DOMAIN}|" .env
sed -i "s|^PANEL_DOMAIN=.*|PANEL_DOMAIN=${ADMIN_PANEL_DOMAIN}|" .env
sed -i "s|^SUB_PUBLIC_DOMAIN=.*|SUB_PUBLIC_DOMAIN=${SUB_PUBLIC_DOMAIN}|" .env
docker compose up -d remnawave

echo "==> Enable Bedolaga Cabinet in bot .env"
JWT_SECRET="$(openssl rand -hex 32)"
ENV_FILE="$BOT_DIR/.env"
touch "$ENV_FILE"

set_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    echo "${key}=${val}" >> "$ENV_FILE"
  fi
}

set_env CABINET_ENABLED true
set_env CABINET_URL "https://${CABINET_DOMAIN}"
set_env CABINET_JWT_SECRET "$JWT_SECRET"
set_env CABINET_ALLOWED_ORIGINS "https://${CABINET_DOMAIN}"
set_env CABINET_EMAIL_AUTH_ENABLED true

if grep -q '^REMNAWAVE_API_URL=' "$ENV_FILE"; then
  sed -i "s|^REMNAWAVE_API_URL=.*|REMNAWAVE_API_URL=https://${ADMIN_PANEL_DOMAIN}|" "$ENV_FILE"
fi

echo "==> Pull Bedolaga cabinet frontend"
docker pull ghcr.io/bedolaga-dev/bedolaga-cabinet:latest
docker rm -f tmp_bedolaga_cabinet 2>/dev/null || true
docker create --name tmp_bedolaga_cabinet ghcr.io/bedolaga-dev/bedolaga-cabinet:latest
mkdir -p "$CABINET_STATIC_DIR"
rm -rf "${CABINET_STATIC_DIR:?}"/*
docker cp tmp_bedolaga_cabinet:/usr/share/nginx/html/. "$CABINET_STATIC_DIR/"
docker rm tmp_bedolaga_cabinet

echo "==> Optional: run cabinet as docker service (for reverse_proxy mode)"
cat > "$BOT_DIR/docker-compose.cabinet.yml" <<YAML
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

cd "$BOT_DIR"
docker compose -f docker-compose.yml -f docker-compose.cabinet.yml up -d cabinet-frontend 2>/dev/null || \
  docker compose -f docker-compose.cabinet.yml up -d

echo "==> Connect Caddy to bot network"
docker network connect remnawave-bedolaga-telegram-bot_bot_network caddy 2>/dev/null || true

echo "==> Write Caddyfile"
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

# Mount cabinet static as fallback if container mode fails
if ! grep -q '/srv/cabinet' "$CADDY_DIR/docker-compose.yml" 2>/dev/null; then
  if grep -q 'volumes:' "$CADDY_DIR/docker-compose.yml"; then
    sed -i "\|volumes:|a\\      - ${CABINET_STATIC_DIR}:/srv/cabinet:ro" "$CADDY_DIR/docker-compose.yml" || true
  fi
fi

cd "$CADDY_DIR"
docker compose up -d
docker exec caddy caddy reload --config /etc/caddy/Caddyfile 2>/dev/null || docker compose restart

cd "$BOT_DIR"
docker compose restart bot

echo
echo "=============================================="
echo "Bedolaga cabinet (main):  https://${CABINET_DOMAIN}"
echo "Remnawave admin:          https://${ADMIN_PANEL_DOMAIN}"
echo "Subscriptions:            https://${SUB_PUBLIC_DOMAIN}/{uuid}"
echo
echo "DNS required:"
echo "  ${CABINET_DOMAIN} -> server IP (already used as main)"
echo "  ${ADMIN_PANEL_DOMAIN} -> server IP"
echo "  ${SUB_PUBLIC_DOMAIN} -> server IP"
echo
echo "BotFather -> Bot Settings -> Domain: ${CABINET_DOMAIN}"
echo "Bot username for cabinet: ${BOT_USERNAME}"
echo "=============================================="
