#!/usr/bin/env bash
# BotVMAR — installation initiale sur Ubuntu VPS.
# Idempotent : peut être relancé sans casser quoi que ce soit.
#
# Usage:
#   bash install.sh                  # full install, configure le service systemd
#   INSTALL_SERVICE=0 bash install.sh   # full install sans service (dev local)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

INSTALL_SERVICE=${INSTALL_SERVICE:-1}
SERVICE_USER=${SERVICE_USER:-$(whoami)}
SERVICE_NAME=${SERVICE_NAME:-botvmar}

log() { printf "\033[1;36m==>\033[0m %s\n" "$*"; }

log "System packages (apt)"
sudo apt-get update -y
sudo apt-get install -y \
    python3 python3-venv python3-pip \
    xvfb wget curl unzip ca-certificates \
    build-essential

log "Python virtualenv"
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip wheel >/dev/null

log "Python dependencies"
pip install -r requirements.txt

log "Installing botvmar package (editable)"
pip install -e .

log "Playwright browsers + system deps"
python -m playwright install chromium --with-deps
python -m playwright install firefox --with-deps

log "Runtime directories"
mkdir -p data logs/screenshots sessions
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  .env créé depuis .env.example — édite-le avant de démarrer"
fi

if [ "$INSTALL_SERVICE" = "1" ]; then
    if [ ! -f "$SCRIPT_DIR/botvmar.service" ]; then
        echo "  botvmar.service manquant — service systemd non installé"
    else
        log "Installing systemd service ($SERVICE_NAME, user=$SERVICE_USER)"
        sed \
            -e "s|__USER__|$SERVICE_USER|g" \
            -e "s|__DIR__|$SCRIPT_DIR|g" \
            "$SCRIPT_DIR/botvmar.service" \
            | sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null
        sudo systemctl daemon-reload
        sudo systemctl enable "${SERVICE_NAME}"
        echo "  service installé. Démarre-le après config du .env :"
        echo "    sudo systemctl start ${SERVICE_NAME}"
    fi
fi

cat <<EOF

==========================================================
  Installation complete.
==========================================================

Prochaines étapes :

  1. Édite le .env :
     nano .env

  2. Login plateformes (sessions manuelles, une seule fois) :
     xvfb-run python scripts/login.py            # Yahoo Finance
     xvfb-run python scripts/login_reddit.py     # Reddit (Firefox)
     xvfb-run python scripts/login_stocktwits.py # StockTwits

  3. Démarre le service :
     sudo systemctl start ${SERVICE_NAME}

  4. Surveille les logs :
     sudo journalctl -u ${SERVICE_NAME} -f

EOF
