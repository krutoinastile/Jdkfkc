#!/usr/bin/env bash
# Full stack install per:
#   https://docs.bedolagam.ru/getting-started/quickstart
#   https://docs.bedolagam.ru/cabinet/setup
#   https://docs.rw/install/subscription-page/bundled/
#
# Domains (defaults):
#   fastervpn.shop        -> Bedolaga personal cabinet (main)
#   panel.fastervpn.shop  -> Remnawave admin panel
#   sub.fastervpn.shop    -> Remnawave subscription page
#
# Required:
#   export BOT_TOKEN=...
#   export ADMIN_IDS=...
# Optional:
#   export REMNAWAVE_API_KEY=...   (skip auto-create if set)

set -euo pipefail

CABINET_DOMAIN="${CABINET_DOMAIN:-fastervpn.shop}"
ADMIN_PANEL_DOMAIN="${ADMIN_PANEL_DOMAIN:-panel.fastervpn.shop}"
SUB_PUBLIC_DOMAIN="${SUB_PUBLIC_DOMAIN:-sub.fastervpn.shop}"
BOT_DIR="${BOT_DIR:-/root/remnawave-bedolaga-telegram-bot}"
REMNAWAVE_DIR="${REMNAWAVE_DIR:-/opt/remnawave}"
CADDY_DIR="${CADDY_DIR:-/opt/remnawave/caddy}"
SUB_DIR="${SUB_DIR:-/opt/remnawave/subscription}"

: "${BOT_TOKEN:?Set BOT_TOKEN}"
: "${ADMIN_IDS:?Set ADMIN_IDS}"

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "==> Docker + tools"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq make git curl openssl python3 jq

log "==> Remnawave panel (${REMNAWAVE_DIR})"
mkdir -p "$REMNAWAVE_DIR"
cd "$REMNAWAVE_DIR"
if [[ ! -f docker-compose.yml ]]; then
  curl -fsSL -o docker-compose.yml \
    https://raw.githubusercontent.com/remnawave/backend/refs/heads/main/docker-compose-prod.yml
  curl -fsSL -o .env \
    https://raw.githubusercontent.com/remnawave/backend/refs/heads/main/.env.sample
  pw="$(openssl rand -hex 24)"
  sed -i "s/^APP_SECRET=.*/APP_SECRET=$(openssl rand -hex 64)/" .env
  sed -i "s/^METRICS_PASS=.*/METRICS_PASS=$(openssl rand -hex 64)/" .env
  sed -i "s/^WEBHOOK_SECRET_HEADER=.*/WEBHOOK_SECRET_HEADER=$(openssl rand -hex 64)/" .env
  sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${pw}/" .env
  sed -i "s|^\(DATABASE_URL=\"postgresql://postgres:\)[^@]*\(@.*\)|\1${pw}\2|" .env
fi

sed -i "s|^FRONT_END_DOMAIN=.*|FRONT_END_DOMAIN=${ADMIN_PANEL_DOMAIN}|" .env
sed -i "s|^PANEL_DOMAIN=.*|PANEL_DOMAIN=${ADMIN_PANEL_DOMAIN}|" .env
grep -q '^PANEL_DOMAIN=' .env || echo "PANEL_DOMAIN=${ADMIN_PANEL_DOMAIN}" >> .env
sed -i "s|^SUB_PUBLIC_DOMAIN=.*|SUB_PUBLIC_DOMAIN=${SUB_PUBLIC_DOMAIN}|" .env

docker compose up -d
log "Waiting for Remnawave health..."
for _ in $(seq 1 40); do
  curl -fsS --max-time 5 http://127.0.0.1:3001/health >/dev/null 2>&1 && break
  sleep 3
done

log "==> Remnawave admin (if missing)"
ADMIN_FILE="/root/remnawave-admin-credentials.txt"
if [[ ! -f "$ADMIN_FILE" ]]; then
  ADMIN_PASS="Rw$(openssl rand -hex 10)Aa1"
  REG=$(curl -sk --max-time 20 -X POST http://127.0.0.1:3000/api/auth/register \
    -H 'Content-Type: application/json' \
    -H 'Host: '"${ADMIN_PANEL_DOMAIN}" \
    -H 'X-Forwarded-Proto: https' \
    -H 'X-Forwarded-For: 127.0.0.1' \
    -d "{\"username\":\"admin\",\"password\":\"${ADMIN_PASS}\"}" || true)
  if echo "$REG" | jq -e '.response.accessToken' >/dev/null 2>&1; then
    printf 'Panel: https://%s\nUsername: admin\nPassword: %s\n' \
      "$ADMIN_PANEL_DOMAIN" "$ADMIN_PASS" > "$ADMIN_FILE"
    chmod 600 "$ADMIN_FILE"
  fi
fi

log "==> API tokens for subscription page + bot"
ADMIN_PASS=$(grep Password "$ADMIN_FILE" 2>/dev/null | awk '{print $2}' || true)
ADMIN_JWT=""
if [[ -n "$ADMIN_PASS" ]]; then
  ADMIN_JWT=$(curl -sk --max-time 20 -X POST http://127.0.0.1:3000/api/auth/login \
    -H 'Content-Type: application/json' \
    -H 'Host: '"${ADMIN_PANEL_DOMAIN}" \
    -H 'X-Forwarded-Proto: https' \
    -H 'X-Forwarded-For: 127.0.0.1' \
    -d "{\"username\":\"admin\",\"password\":\"${ADMIN_PASS}\"}" \
    | jq -r '.response.accessToken // empty' || true)
fi

HDR=(-H "Host: ${ADMIN_PANEL_DOMAIN}" -H 'X-Forwarded-Proto: https' -H 'X-Forwarded-For: 127.0.0.1')

create_token() {
  local name="$1"
  curl -sk --max-time 20 -X POST http://127.0.0.1:3000/api/tokens \
    -H "Authorization: Bearer ${ADMIN_JWT}" \
    -H 'Content-Type: application/json' \
    "${HDR[@]}" \
    -d "{\"tokenName\":\"${name}\",\"scopes\":[\"*\"]}" \
    | jq -r '.response.token // empty' || true
}

SUB_TOKEN=""
BOT_TOKEN_RW=""
if [[ -n "$ADMIN_JWT" ]]; then
  SUB_TOKEN=$(create_token "subscription-page")
  BOT_TOKEN_RW=$(create_token "bedolaga-bot")
fi

log "==> Subscription page (${SUB_DIR})"
mkdir -p "$SUB_DIR"
if [[ ! -f "$SUB_DIR/docker-compose.yml" ]]; then
  cat > "$SUB_DIR/docker-compose.yml" <<'YAML'
services:
  remnawave-subscription-page:
    image: remnawave/subscription-page:latest
    container_name: remnawave-subscription-page
    hostname: remnawave-subscription-page
    restart: always
    env_file:
      - .env
    ports:
      - '127.0.0.1:3010:3010'
    networks:
      - remnawave-network

networks:
  remnawave-network:
    driver: bridge
    external: true
YAML
fi

if [[ ! -f "$SUB_DIR/.env" ]]; then
  cat > "$SUB_DIR/.env" <<ENV
APP_PORT=3010
REMNAWAVE_PANEL_URL=http://remnawave:3000
REMNAWAVE_API_TOKEN=${SUB_TOKEN:-}
CUSTOM_SUB_PREFIX=
MARZBAN_LEGACY_LINK_ENABLED=false
TRUST_PROXY=1
ENV
elif [[ -n "$SUB_TOKEN" ]]; then
  sed -i "s|^REMNAWAVE_API_TOKEN=.*|REMNAWAVE_API_TOKEN=${SUB_TOKEN}|" "$SUB_DIR/.env"
fi

cd "$SUB_DIR"
docker compose up -d

log "==> Bedolaga bot quickstart (${BOT_DIR})"
if [[ ! -d "$BOT_DIR/.git" ]]; then
  git clone https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot.git "$BOT_DIR"
fi
cd "$BOT_DIR"
git pull --ff-only || true
mkdir -p ./logs ./data ./data/backups ./data/referral_qr
chmod -R 755 ./logs ./data
chown -R 1000:1000 ./logs ./data 2>/dev/null || true

[[ -f .env ]] || cp .env.example .env

# Remove broken placeholder lines from .env.example copies
python3 <<'PY'
import re, pathlib
p = pathlib.Path(".env")
lines = p.read_text().splitlines()
out = []
for line in lines:
    s = line.strip()
    if not s or s.startswith("#"):
        out.append(line); continue
    if "=" not in s:
        continue
    k, v = s.split("=", 1)
    v = v.strip()
    if re.search(r"[<>]|your_|example\.com|changeme|TODO|REPLACE", v, re.I):
        continue  # drop placeholders so pydantic defaults apply
    elif v.startswith("#") or " #" in v:
        continue
    elif v.strip() == "":
        continue
    else:
        out.append(line)
p.write_text("\n".join(out) + "\n")
PY

EXISTING_PG=$(grep '^POSTGRES_PASSWORD=' .env 2>/dev/null | cut -d= -f2- || true)
PG_PASS="${POSTGRES_PASSWORD:-${EXISTING_PG:-$(openssl rand -hex 16)}}"
set_kv() {
  local k="$1" v="$2"
  if grep -q "^${k}=" .env; then sed -i "s|^${k}=.*|${k}=${v}|" .env; else echo "${k}=${v}" >> .env; fi
}

set_kv BOT_TOKEN "$BOT_TOKEN"
set_kv ADMIN_IDS "$ADMIN_IDS"
set_kv BOT_RUN_MODE polling
set_kv WEB_API_ENABLED true
set_kv POSTGRES_PASSWORD "$PG_PASS"
set_kv REMNAWAVE_API_URL "http://remnawave:3000"
set_kv REMNAWAVE_AUTH_TYPE api_key
if [[ -n "${REMNAWAVE_API_KEY:-}" ]]; then
  set_kv REMNAWAVE_API_KEY "$REMNAWAVE_API_KEY"
elif [[ -n "$BOT_TOKEN_RW" ]]; then
  set_kv REMNAWAVE_API_KEY "$BOT_TOKEN_RW"
fi

JWT_SECRET="$(openssl rand -hex 32)"
set_kv CABINET_ENABLED true
set_kv CABINET_URL "https://${CABINET_DOMAIN}"
set_kv CABINET_JWT_SECRET "$JWT_SECRET"
set_kv CABINET_ALLOWED_ORIGINS "https://${CABINET_DOMAIN}"
set_kv CABINET_EMAIL_AUTH_ENABLED true

make up

log "==> Cabinet frontend"
docker pull ghcr.io/bedolaga-dev/bedolaga-cabinet:latest
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

log "==> Caddy"
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

if [[ ! -f "$CADDY_DIR/docker-compose.yml" ]]; then
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
fi

cd "$CADDY_DIR"
docker compose up -d
docker network connect remnawave-bedolaga-telegram-bot_bot_network caddy 2>/dev/null || true
docker exec caddy caddy reload --config /etc/caddy/Caddyfile 2>/dev/null || docker compose restart caddy

cd "$BOT_DIR"
docker compose restart bot

log "==> Health checks"
sleep 8
docker ps --format 'table {{.Names}}\t{{.Status}}' | head -20

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
curl -sk --max-time 20 -o /dev/null -w "cabinet: %{http_code}\n" -A "$UA" "https://${CABINET_DOMAIN}/" || true
curl -sk --max-time 20 -o /dev/null -w "cabinet api: %{http_code}\n" "https://${CABINET_DOMAIN}/api/health" || true
curl -sk --max-time 20 -o /dev/null -w "admin panel: %{http_code}\n" "https://${ADMIN_PANEL_DOMAIN}/" || true

log "Done."
echo "Cabinet:  https://${CABINET_DOMAIN}"
echo "Admin:    https://${ADMIN_PANEL_DOMAIN}"
echo "Sub:      https://${SUB_PUBLIC_DOMAIN}/{uuid}"
echo "Admin creds: ${ADMIN_FILE}"
echo "BotFather domain: ${CABINET_DOMAIN}"
