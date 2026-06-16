#!/usr/bin/env bash
# Keeps the trading bot running — restarts on crash or exit.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOG_DIR="${ROOT}/data/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/bot-supervisor.log"

log() {
  echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"
}

BACKOFF=5
MAX_BACKOFF=60

log "Supervisor started (pid $$)"

while true; do
  log "Starting bot: python3 -m app.main"
  if python3 -m app.main >>"$LOG_FILE" 2>&1; then
    code=0
  else
    code=$?
  fi

  if [[ $code -eq 130 ]] || [[ $code -eq 143 ]]; then
    log "Bot stopped by signal (code $code), supervisor exiting."
    exit 0
  fi

  log "Bot exited (code $code). Restarting in ${BACKOFF}s..."
  sleep "$BACKOFF"
  BACKOFF=$((BACKOFF * 2))
  if [[ $BACKOFF -gt $MAX_BACKOFF ]]; then
    BACKOFF=$MAX_BACKOFF
  fi
done
