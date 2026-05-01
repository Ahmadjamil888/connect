#!/usr/bin/env bash
# IMOS — Intelligent Machine Operating System — Installer
set -euo pipefail

REPO_URL="https://github.com/Ahmadjamil888/connect.git"
INSTALL_DIR="${IMOS_INSTALL_DIR:-$HOME/imos}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

O='\033[38;5;208m'; W='\033[1;37m'; G='\033[32m'; R='\033[31m'; D='\033[90m'; X='\033[0m'

log()  { printf "${O}[%s]${X} %s\n" "$1" "$2"; }
ok()   { printf "${G}      ✓ %s${X}\n" "$1"; }
fail() { printf "${R}[!] %s${X}\n" "$1" >&2; exit 1; }

echo ""
echo -e "${O}  ========================================================"
echo -e "    IMOS — Intelligent Machine Operating System"
echo -e "    Installer"
echo -e "  ========================================================${X}"
echo ""

# ── Step 1: Resolve repo ──────────────────────────────────────────────────────
log "1/6" "Resolving repository..."
if [[ -f "$SCRIPT_DIR/imos_cli.py" ]]; then
    REPO_DIR="$SCRIPT_DIR"
    ok "Using existing repo at $REPO_DIR"
elif [[ -f "$INSTALL_DIR/imos_cli.py" ]]; then
    REPO_DIR="$INSTALL_DIR"
    ok "Updating existing install at $REPO_DIR"
    command -v git >/dev/null 2>&1 && git -C "$REPO_DIR" pull --ff-only || true
elif command -v git >/dev/null 2>&1; then
    REPO_DIR="$INSTALL_DIR"
    mkdir -p "$REPO_DIR"
    log "1/6" "Cloning IMOS into $REPO_DIR"
    git clone "$REPO_URL" "$REPO_DIR"
    ok "Cloned"
else
    REPO_DIR="$INSTALL_DIR"
    mkdir -p "$REPO_DIR"
    log "1/6" "Downloading IMOS archive..."
    command -v curl >/dev/null 2>&1 || fail "curl is required when git is not installed"
    TMP="$(mktemp)"
    curl -fsSL "https://github.com/Ahmadjamil888/connect/archive/refs/heads/main.tar.gz" -o "$TMP"
    tar -xzf "$TMP" --strip-components=1 -C "$REPO_DIR"
    rm -f "$TMP"
    ok "Downloaded"
fi

# ── Step 2: Python ────────────────────────────────────────────────────────────
log "2/6" "Checking Python..."
if command -v python3 >/dev/null 2>&1; then
    PY="python3"
elif command -v python >/dev/null 2>&1; then
    PY="python"
else
    fail "Python 3.10+ is required. Install from https://python.org"
fi
ok "Found: $($PY --version)"

# ── Step 3: Virtual environment ───────────────────────────────────────────────
log "3/6" "Creating virtual environment..."
if [[ ! -d "$REPO_DIR/venv" ]]; then
    "$PY" -m venv "$REPO_DIR/venv"
    ok "Created venv"
else
    ok "Using existing venv"
fi
VENV_PY="$REPO_DIR/venv/bin/python"
[[ -x "$VENV_PY" ]] || fail "Virtual environment creation failed"

# ── Step 4: Install requirements ──────────────────────────────────────────────
log "4/6" "Installing requirements..."
"$VENV_PY" -m pip install --upgrade pip -q
"$VENV_PY" -m pip install -r "$REPO_DIR/requirements.txt" -q
ok "Requirements installed"

# ── Step 5: Copy .env.example → .env ─────────────────────────────────────────
log "5/6" "Setting up environment file..."
if [[ ! -f "$REPO_DIR/.env" ]]; then
    if [[ -f "$REPO_DIR/.env.example" ]]; then
        cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
        ok "Created .env from .env.example"
    else
        touch "$REPO_DIR/.env"
        ok "Created empty .env"
    fi
else
    ok ".env already exists, skipping"
fi

# ── Step 6: Install imos command ──────────────────────────────────────────────
log "6/6" "Installing 'imos' command..."
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/imos" <<EOF
#!/usr/bin/env bash
exec "$VENV_PY" "$REPO_DIR/imos_cli.py" "\$@"
EOF
chmod +x "$BIN_DIR/imos"
ok "Installed at $BIN_DIR/imos"

# Check PATH
case ":$PATH:" in
    *":$BIN_DIR:"*) ok "$BIN_DIR already in PATH" ;;
    *)
        echo ""
        echo -e "${O}  Add this to your shell profile (~/.bashrc or ~/.zshrc):${X}"
        echo -e "  ${W}export PATH=\"\$HOME/.local/bin:\$PATH\"${X}"
        echo ""
        ;;
esac

echo ""
echo -e "${O}  ========================================================"
echo -e "${G}    IMOS installed successfully!"
echo -e "${O}  ========================================================${X}"
echo ""
echo -e "  Open a new terminal and type: ${O}imos${X}"
echo -e "  The setup wizard will run on first launch."
echo ""
echo -e "  ${D}Repo:      $REPO_DIR${X}"
echo -e "  ${D}Dashboard: http://localhost:5000${X}"
echo ""
