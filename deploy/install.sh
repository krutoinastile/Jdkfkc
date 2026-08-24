#!/bin/bash
# Idempotent installer for the DeepSeek Harness web UI on guardshop.shop.
#
# Run as root on a fresh Ubuntu 24.04 host. Safe to re-run: every step checks
# for its own result first. See deploy/README.md for the design constraints.
set -euo pipefail

DOMAIN="${DOMAIN:-guardshop.shop}"
APP_PORT="${APP_PORT:-8099}"
TLS_PORT="${TLS_PORT:-9443}"
APP_USER="${APP_USER:-dsh}"
APP_ROOT="/opt/${APP_USER}"
REPO="https://github.com/deepseek-ai/deepseek-harness.git"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { printf '\n==> %s\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { echo "must run as root" >&2; exit 1; }

log "Checking port ${TLS_PORT} and 80 are free"
for p in 80 "$TLS_PORT"; do
  if ss -tlnH "sport = :$p" | grep -q . ; then
    owner=$(ss -tlnpH "sport = :$p" | grep -oP 'users:\(\("\K[^"]+' | head -1 || true)
    if [ "$owner" != "nginx" ]; then
      echo "port $p already held by '${owner:-unknown}'; refusing to fight over it" >&2
      exit 1
    fi
  fi
done

log "Ensuring swap is large enough to build the monorepo"
# The TypeScript build across ~246 workspace projects peaks around 2 GB of
# anonymous memory; a 2 GB box needs swap or tsc gets OOM-killed mid-build.
want=$((4 * 1024 * 1024 * 1024))
have=$(swapon --show=SIZE --noheadings --bytes 2>/dev/null | head -1 || echo 0)
if [ "${have:-0}" -lt "$want" ]; then
  swapoff /swapfile 2>/dev/null || true
  rm -f /swapfile
  fallocate -l 4G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=4096 status=none
  chmod 600 /swapfile && mkswap -q /swapfile && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
swapon --show

log "Installing packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx apache2-utils \
  ca-certificates curl git gnupg build-essential
if ! command -v node >/dev/null || ! node -e 'process.exit(process.versions.node.split(".")[0]>=22?0:1)'; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y -qq nodejs
fi
# node-pty and koffi build native addons, so build-essential above is required.
corepack enable >/dev/null 2>&1 || true
corepack prepare pnpm@latest --activate >/dev/null 2>&1 || npm i -g pnpm >/dev/null 2>&1
node --version; pnpm --version

log "Creating service user ${APP_USER}"
id "$APP_USER" >/dev/null 2>&1 || \
  useradd --system --create-home --home-dir "$APP_ROOT" --shell /bin/bash "$APP_USER"

log "Cloning ${REPO}"
if [ ! -d "$APP_ROOT/app/.git" ]; then
  sudo -u "$APP_USER" git clone --depth 1 "$REPO" "$APP_ROOT/app"
fi

log "Building (this is the slow part on a 1-vCPU box)"
sudo -u "$APP_USER" env HOME="$APP_ROOT" NODE_OPTIONS=--max-old-space-size=3072 CI=1 \
  bash -c "cd $APP_ROOT/app && pnpm install --reporter=append-only && pnpm run build"

log "Installing run script and systemd unit"
install -o "$APP_USER" -g "$APP_USER" -m 755 "$HERE/run-web.sh" "$APP_ROOT/run-web.sh"
install -m 644 "$HERE/systemd/dsh-web.service" /etc/systemd/system/dsh-web.service
touch /var/log/dsh-web.log && chown "$APP_USER:$APP_USER" /var/log/dsh-web.log
systemctl daemon-reload
systemctl enable dsh-web >/dev/null

log "Generating basic-auth credentials"
# The harness has no login of its own, so this is the only authentication.
if [ ! -f /etc/nginx/.htpasswd-dsh ]; then
  PASS=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24)
  htpasswd -bc /etc/nginx/.htpasswd-dsh admin "$PASS" >/dev/null
  chown root:www-data /etc/nginx/.htpasswd-dsh && chmod 640 /etc/nginx/.htpasswd-dsh
  printf '\n  BASIC AUTH USER: admin\n  BASIC AUTH PASS: %s\n  (store this now; it is not recoverable)\n\n' "$PASS"
else
  echo "  /etc/nginx/.htpasswd-dsh exists, leaving it alone"
fi

log "Obtaining certificate for ${DOMAIN}"
mkdir -p /var/www/letsencrypt/.well-known/acme-challenge
# Port 80 vhost must exist before certbot so HTTP-01 can be served.
install -m 644 "$HERE/nginx/upgrade-map.conf" /etc/nginx/conf.d/upgrade-map.conf
rm -f /etc/nginx/sites-enabled/default
if [ ! -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
  cat > /etc/nginx/sites-available/"$DOMAIN" <<EOF
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    location /.well-known/acme-challenge/ { root /var/www/letsencrypt; }
    location / { return 200 "provisioning\n"; }
}
EOF
  ln -sfn /etc/nginx/sites-available/"$DOMAIN" /etc/nginx/sites-enabled/"$DOMAIN"
  nginx -t && systemctl restart nginx
  certbot certonly --webroot -w /var/www/letsencrypt \
    -d "$DOMAIN" -d "www.$DOMAIN" \
    --agree-tos --register-unsafely-without-email --non-interactive --keep-until-expiring
fi

log "Installing final vhost"
install -m 644 "$HERE/nginx/${DOMAIN}.conf" /etc/nginx/sites-available/"$DOMAIN"
ln -sfn /etc/nginx/sites-available/"$DOMAIN" /etc/nginx/sites-enabled/"$DOMAIN"
mkdir -p /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nsystemctl reload nginx\n' > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
nginx -t
systemctl restart nginx
systemctl restart dsh-web

log "Verifying"
for i in $(seq 1 20); do
  sleep 3
  ss -tlnH "sport = :$APP_PORT" | grep -q . && break
done
printf '  app bound to      : %s\n' "$(ss -tlnH "sport = :$APP_PORT" | awk '{print $4}')"
printf '  no-auth  -> %s (expect 401)\n' "$(curl -sk -o /dev/null -w '%{http_code}' "https://${DOMAIN}:${TLS_PORT}/")"
printf '  manifest -> %s (expect 200)\n' "$(curl -sk -o /dev/null -w '%{http_code}' "https://${DOMAIN}:${TLS_PORT}/manifest.webmanifest")"
echo
echo "Done. https://${DOMAIN}:${TLS_PORT}/"
