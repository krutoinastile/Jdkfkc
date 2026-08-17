#!/usr/bin/env bash
# Long-running bot terminal. Runs the live Telegram bot when BOT_TOKEN is
# configured (as a Cloud Agent secret); otherwise it idles with guidance so the
# terminal stays available and the environment never fails to start.
set -uo pipefail

cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
  echo "Virtualenv missing. Run '.cursor/install.sh' (the install phase) first."
  exec sleep infinity
fi

TOKEN="${BOT_TOKEN:-}"
if [ -z "$TOKEN" ] || [ "$TOKEN" = "dummy" ]; then
  cat <<'MSG'
BOT_TOKEN is not set, so the live Telegram bot is not started.

To run the bot end-to-end:
  1. Create a bot with @BotFather and copy its token.
  2. Add BOT_TOKEN (and optionally ADMIN_IDS) as a Cloud Agent secret.
  3. Restart this terminal.

The code, database and strategy/backtest/chart engine are fully installed and
can be exercised without a token, e.g.:
  .venv/bin/python -m app.main            # live bot (needs BOT_TOKEN)
MSG
  exec sleep infinity
fi

echo "Starting BTC Trading Bot..."
exec .venv/bin/python -m app.main
