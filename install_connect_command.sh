#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/connect" <<EOF
#!/bin/bash
python3 "$REPO_DIR/ai_assistant.py" "\$@"
EOF

chmod +x "$BIN_DIR/connect"
echo "[*] Installed launcher: $BIN_DIR/connect"
echo "[*] Make sure $BIN_DIR is in PATH, then run: connect"
