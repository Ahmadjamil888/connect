#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/connect"
mkdir -p "$BIN_DIR"

cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
REPO_DIR="$REPO_DIR"
VENV_PYTHON="\$REPO_DIR/venv/bin/python"
if [[ -x "\$VENV_PYTHON" ]]; then
  exec "\$VENV_PYTHON" "\$REPO_DIR/ai_assistant.py" "\$@"
fi
if command -v python3 >/dev/null 2>&1; then
  exec python3 "\$REPO_DIR/ai_assistant.py" "\$@"
fi
exec python "\$REPO_DIR/ai_assistant.py" "\$@"
EOF

chmod +x "$LAUNCHER"
echo "[*] Installed launcher: $LAUNCHER"
echo "[*] Make sure $BIN_DIR is in PATH, then run: connect --doctor"
