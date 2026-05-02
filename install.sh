#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/Ahmadjamil888/connect.git"
INSTALL_DIR="${IMOS_INSTALL_DIR:-$HOME/imos}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

O='\033[38;5;208m'; W='\033[1;37m'; G='\033[32m'; R='\033[31m'; D='\033[90m'; X='\033[0m'

step() { printf "${O}[%s]${X} %s\n" "$1" "$2"; }
ok() { printf "${G}      OK${X} %s\n" "${1:+- $1}"; }
fail() { printf "${R}[!] %s${X}\n" "$1" >&2; exit 1; }
progress() {
  local label="$1"
  shift
  printf "${O}      ...${X} %s\n" "$label"
  "$@" >/dev/null 2>&1 || fail "$label failed"
  ok "$label"
}

echo ""
echo -e "${O}  ========================================================${X}"
echo -e "${W}    IMOS Installer${X}"
echo -e "${D}    One command, one runtime, one setup flow${X}"
echo -e "${O}  ========================================================${X}"
echo ""

step "1/7" "Resolving repository source"
if [[ -f "$SCRIPT_DIR/setup.py" && -d "$SCRIPT_DIR/imos" ]]; then
  REPO_DIR="$SCRIPT_DIR"
  ok "Using current repository"
elif [[ -f "$INSTALL_DIR/setup.py" && -d "$INSTALL_DIR/imos" ]]; then
  REPO_DIR="$INSTALL_DIR"
  if command -v git >/dev/null 2>&1; then
    progress "Updating repository" git -C "$REPO_DIR" pull --ff-only
  else
    ok "Using existing installation"
  fi
else
  REPO_DIR="$INSTALL_DIR"
  rm -rf "$REPO_DIR"
  mkdir -p "$REPO_DIR"
  if command -v git >/dev/null 2>&1; then
    progress "Cloning repository" git clone "$REPO_URL" "$REPO_DIR"
  else
    command -v curl >/dev/null 2>&1 || fail "curl is required when git is unavailable"
    TMP="$(mktemp)"
    progress "Downloading repository archive" curl -fsSL "https://github.com/Ahmadjamil888/connect/archive/refs/heads/main.tar.gz" -o "$TMP"
    progress "Extracting repository archive" tar -xzf "$TMP" --strip-components=1 -C "$REPO_DIR"
    rm -f "$TMP"
  fi
fi

step "2/7" "Checking Python runtime"
if command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  PY="python"
else
  fail "Python 3.10+ is required"
fi
ok "$($PY --version 2>&1)"

step "3/7" "Preparing virtual environment"
if [[ ! -d "$REPO_DIR/venv" ]]; then
  progress "Creating virtual environment" "$PY" -m venv "$REPO_DIR/venv"
else
  ok "Using existing virtual environment"
fi
VENV_PY="$REPO_DIR/venv/bin/python"
[[ -x "$VENV_PY" ]] || fail "Virtual environment is missing"

step "4/7" "Installing IMOS runtime"
progress "Upgrading pip" "$VENV_PY" -m pip install --upgrade pip
progress "Installing project dependencies" "$VENV_PY" -m pip install -r "$REPO_DIR/requirements.txt"
progress "Installing IMOS command" "$VENV_PY" -m pip install -e "$REPO_DIR"

step "5/7" "Preparing local configuration"
if [[ ! -f "$REPO_DIR/.env" ]]; then
  if [[ -f "$REPO_DIR/.env.example" ]]; then
    cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
    ok "Created .env from template"
  else
    touch "$REPO_DIR/.env"
    ok "Created empty .env"
  fi
else
  ok "Existing .env preserved"
fi
mkdir -p "$HOME/.imos"
progress "Initializing IMOS home" "$VENV_PY" -c "from imos.config import ensure_default_files; ensure_default_files()"

step "6/7" "Installing global launcher"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/imos" <<EOF
#!/usr/bin/env bash
exec "$VENV_PY" -m imos.cli "\$@"
EOF
chmod +x "$BIN_DIR/imos"
ok "Installed launcher at $BIN_DIR/imos"

case ":$PATH:" in
  *":$BIN_DIR:"*) ok "Launcher directory already on PATH" ;;
  *)
    echo ""
    echo -e "${O}  Add this to your shell profile:${X}"
    echo -e "  ${W}export PATH=\"\$HOME/.local/bin:\$PATH\"${X}"
    echo ""
    ;;
esac

step "7/7" "Running guided setup checks"
progress "Installing editor bridge config" "$VENV_PY" -m imos.cli mcp install
progress "Checking runtime status" "$VENV_PY" -m imos.cli status

echo ""
echo -e "${O}  ========================================================${X}"
echo -e "${G}    IMOS is installed${X}"
echo -e "${O}  ========================================================${X}"
echo ""
echo -e "  Start IMOS from any terminal with: ${W}imos${X}"
echo -e "  Open the dashboard with:          ${W}imos dashboard${X}"
echo -e "  Repository source:                ${D}$REPO_URL${X}"
echo ""
