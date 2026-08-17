#!/usr/bin/env bash
# Idempotent dependency setup for the BTC Trading Bot.
# Safe to run repeatedly and on branches that do not yet contain the app.
set -euo pipefail

cd "$(dirname "$0")/.."

if command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
else
  SUDO=""
fi

# System packages: venv/ensurepip for isolated deps, libfreetype6 for matplotlib charts.
need_apt=0
python3 -c 'import ensurepip' >/dev/null 2>&1 || need_apt=1
dpkg -s libfreetype6 >/dev/null 2>&1 || need_apt=1
if [ "$need_apt" -eq 1 ]; then
  $SUDO apt-get update -qq
  $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv libfreetype6
fi

if [ ! -f requirements.txt ]; then
  echo "requirements.txt not found in $(pwd); skipping Python setup."
  exit 0
fi

# Isolated virtualenv keeps deps reproducible regardless of the base image.
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

mkdir -p data/logs
echo "Install complete: $(.venv/bin/python --version)"
