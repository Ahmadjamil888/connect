#!/bin/bash
set -euo pipefail

echo "========================================"
echo " IMOS — Intelligent Machine OS Setup"
echo "========================================"
echo ""

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found. Install from https://python.org"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[*] Python: $(python3 --version)"
echo ""

if [[ ! -d venv ]]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate

echo "[*] Installing dependencies..."
python3 -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

echo "[*] Installing operator extras (voice, desktop control)..."
pip install faster-whisper sounddevice numpy scipy pystray pillow elevenlabs pyttsx3 pyautogui pygetwindow 2>/dev/null || true

echo "[*] Installing Playwright Chromium..."
python3 -m playwright install chromium

echo "[*] Bootstrapping IMOS runtime (home, providers, services)..."
python3 -c "
from pathlib import Path
from setup.bootstrap import initialize_imos_runtime, print_bootstrap_summary
summary = initialize_imos_runtime(Path('.'))
print_bootstrap_summary(summary)
"

if [[ ! -f .env ]] && [[ -f .env.example ]]; then
    cp .env.example .env
    echo "[*] Created .env from .env.example"
fi

read -r -p "Configure Cursor / Windsurf MCP now? [y/N]: " IMOS_MCP
if [[ "$IMOS_MCP" =~ ^[Yy]$ ]]; then
    python3 -m imos.cli mcp install || true
fi

read -r -p "Run IMOS first-time setup wizard (models + services)? [Y/n]: " IMOS_WIZARD
if [[ ! "$IMOS_WIZARD" =~ ^[Nn]$ ]]; then
    python3 -c "
from pathlib import Path
from setup.wizard import run_setup_wizard
run_setup_wizard(Path('.'), Path('.'), forced=True)
" || true
fi

if [[ -f install_connect_command.sh ]]; then
    echo "[*] Installing global connect launcher..."
    bash ./install_connect_command.sh || true
fi

echo "[*] Installing IMOS background service (optional)..."
python3 setup/install_service.py 2>/dev/null || true

echo ""
echo "========================================"
echo " IMOS Setup Complete"
echo "========================================"
echo ""
echo "  Start operator CLI:     imos"
echo "  Open dashboard:         imos dashboard  (or http://127.0.0.1:7070)"
echo "  List all services:      imos  →  /services"
echo "  Add any model:          /model add <type> <model-id> [api_key] [base_url]"
echo "  Model types:            /model types"
echo ""
echo "========================================"
