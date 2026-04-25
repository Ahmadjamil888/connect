#!/bin/bash

echo "========================================"
echo " AI ASSISTANT - Setup"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found. Install from https://python.org"
    exit 1
fi

echo "[*] Python found: $(python3 --version)"
echo ""

# Create virtual environment (optional but recommended)
echo "[*] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "[*] Installing dependencies..."
pip install -r requirements.txt

echo "[*] Installing Playwright Chromium..."
playwright install chromium

echo "[*] Installing global CONNECT command..."
bash ./install_connect_command.sh

echo ""
echo "========================================"
echo " Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Verify your .env file contains GROQ_API_KEY"
echo ""
echo "2. Open a new terminal and run:"
echo "   connect"
echo ""
echo "========================================"
