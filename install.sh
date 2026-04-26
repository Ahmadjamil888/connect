#!/usr/bin/env bash

set -e

REPO_URL="https://github.com/Ahmadjamil888/connect"
PROJECT_DIR="connect"

echo "========================================"
echo " AI ASSISTANT - AUTO INSTALLER"
echo "========================================"

# ---------- Check Git ----------
echo "[*] Checking Git..."
if ! command -v git &> /dev/null; then
    echo "[!] Git not found. Installing..."

    sudo apt update && sudo apt install -y git
fi

# ---------- Clone Repo ----------
if [ -d "$PROJECT_DIR" ]; then
    echo "[!] Folder '$PROJECT_DIR' already exists. Skipping clone."
else
    echo "[*] Cloning repository..."
    git clone "$REPO_URL"
fi

cd "$PROJECT_DIR"

# ---------- Check Python ----------
echo "[*] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "[!] Python3 not found. Installing..."
    sudo apt update && sudo apt install -y python3 python3-pip python3-venv
fi

echo "[✓] Python: $(python3 --version)"

# ---------- Setup Virtual Env ----------
echo "[*] Creating virtual environment..."
python3 -m venv venv

echo "[*] Activating virtual environment..."
source venv/bin/activate

# ---------- Install Dependencies ----------
echo "[*] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# ---------- Setup .env ----------
if [ ! -f ".env" ]; then
    echo "[*] Creating .env file..."

    cat <<EOF > .env
AI_PROVIDER=groq
GROQ_API_KEY=

ANTHROPIC_API_KEY=
OPENAI_API_KEY=
OPENROUTER_API_KEY=
GOOGLE_GEMINI_API_KEY=
HUGGINGFACE_API_KEY=

AI_ASSISTANT_DEBUG=false
EOF
fi

# ---------- Data Directory ----------
DATA_DIR="$HOME/.ai_assistant"
mkdir -p "$DATA_DIR"

touch "$DATA_DIR/user_data.json"
touch "$DATA_DIR/history.json"
touch "$DATA_DIR/projects.json"
touch "$DATA_DIR/analytics.json"
touch "$DATA_DIR/credentials.enc.json"

echo "[✓] Data directory ready at $DATA_DIR"

# ---------- Ask API Key ----------
echo ""
read -p "Enter your GROQ API Key (or press Enter to skip): " GROQ_KEY

if [ ! -z "$GROQ_KEY" ]; then
    sed -i "s/GROQ_API_KEY=/GROQ_API_KEY=$GROQ_KEY/" .env
    echo "[✓] API key saved"
fi

# ---------- Run Assistant ----------
echo ""
echo "========================================"
echo " STARTING AI ASSISTANT..."
echo "========================================"
echo ""

python ai_assistant.py
