set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE_NAME=${SERVICE_NAME:-botvmar}

log() { printf "\033[1;36m==>\033[0m %s\n" "$*"; }

log "Updating Python dependencies"
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip wheel >/dev/null
pip install --upgrade -r requirements.txt

# Réinstalle le package en editable (no-op si déjà à jour, mais pris en compte
# si pyproject.toml a changé — nouvelle dépendance, version, etc.).
pip install -e .

log "Ensuring Playwright browsers are installed"
python -m playwright install chromium >/dev/null 2>&1 || true
python -m playwright install firefox >/dev/null 2>&1 || true

log "Restarting systemd service"
if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
    sudo systemctl restart "${SERVICE_NAME}"
    sleep 3
    if ! sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
        echo "Service failed to start — last 50 log lines:"
        sudo journalctl -u "${SERVICE_NAME}" --no-pager -n 50
        exit 1
    fi
    echo "  service restarted OK"
else
    echo "  ${SERVICE_NAME}.service not installed — skipping restart"
    echo "  (run install.sh first to set up the service)"
fi

log "Deploy complete"
