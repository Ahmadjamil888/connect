#!/usr/bin/env bash

set -euo pipefail

REPO_URL="https://github.com/Ahmadjamil888/connect.git"
ARCHIVE_URL="https://github.com/Ahmadjamil888/connect/archive/refs/heads/main.tar.gz"
INSTALL_DIR="${CONNECT_INSTALL_DIR:-$HOME/connect}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$HOME/.ai_assistant"

log() {
  printf '[*] %s\n' "$1"
}

fail() {
  printf '[!] %s\n' "$1" >&2
  exit 1
}

ensure_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$2"
}

resolve_repo_dir() {
  if [[ -f "$SCRIPT_DIR/ai_assistant.py" ]]; then
    REPO_DIR="$SCRIPT_DIR"
    log "Using existing repo at $REPO_DIR"
    return
  fi

  REPO_DIR="$INSTALL_DIR"
  mkdir -p "$REPO_DIR"

  if [[ -d "$REPO_DIR/.git" ]]; then
    ensure_command git "Git is required to update the existing CONNECT clone."
    log "Updating existing clone in $REPO_DIR"
    git -C "$REPO_DIR" pull --ff-only
    return
  fi

  if [[ -f "$REPO_DIR/ai_assistant.py" ]]; then
    log "Reusing existing install in $REPO_DIR"
    return
  fi

  if command -v git >/dev/null 2>&1; then
    if [[ -n "$(find "$REPO_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
      fail "$REPO_DIR already exists and is not a CONNECT repo. Set CONNECT_INSTALL_DIR to an empty directory or run install.sh from the repo itself."
    fi
    log "Cloning CONNECT into $REPO_DIR"
    git clone "$REPO_URL" "$REPO_DIR"
    return
  fi

  ensure_command curl "curl is required when git is not installed."
  ensure_command tar "tar is required when git is not installed."
  if [[ -n "$(find "$REPO_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" && ! -f "$REPO_DIR/ai_assistant.py" ]]; then
    fail "$REPO_DIR already exists and is not empty. Set CONNECT_INSTALL_DIR to an empty directory or install from a repo clone."
  fi

  log "Downloading CONNECT archive into $REPO_DIR"
  tmp_archive="$(mktemp)"
  trap 'rm -f "$tmp_archive"' EXIT
  curl -fsSL "$ARCHIVE_URL" -o "$tmp_archive"
  mkdir -p "$REPO_DIR"
  tar -xzf "$tmp_archive" --strip-components=1 -C "$REPO_DIR"
  rm -f "$tmp_archive"
  trap - EXIT
}

resolve_python() {
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    fail "Python 3 is required. Install Python 3.10+ and rerun the installer."
  fi
}

create_venv() {
  if [[ ! -d "$REPO_DIR/venv" ]]; then
    log "Creating virtual environment"
    "$PYTHON_BIN" -m venv "$REPO_DIR/venv"
  else
    log "Using existing virtual environment"
  fi
  VENV_PYTHON="$REPO_DIR/venv/bin/python"
  [[ -x "$VENV_PYTHON" ]] || fail "Virtual environment creation failed."
}

install_requirements() {
  log "Installing Python dependencies"
  "$VENV_PYTHON" -m pip install --upgrade pip
  "$VENV_PYTHON" -m pip install -r "$REPO_DIR/requirements.txt"
}

ensure_env_file() {
  if [[ ! -f "$REPO_DIR/.env" ]]; then
    if [[ -f "$REPO_DIR/.env.example" ]]; then
      log "Creating .env from .env.example"
      cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
    else
      log "Creating minimal .env"
      cat > "$REPO_DIR/.env" <<'EOF'
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
  fi
}

ensure_data_dir() {
  log "Preparing local data directory"
  mkdir -p "$DATA_DIR"
  touch \
    "$DATA_DIR/user_data.json" \
    "$DATA_DIR/history.json" \
    "$DATA_DIR/projects.json" \
    "$DATA_DIR/analytics.json" \
    "$DATA_DIR/credentials.enc.json"
}

install_launcher() {
  local bin_dir="$HOME/.local/bin"
  local launcher="$bin_dir/connect"
  mkdir -p "$bin_dir"

  cat > "$launcher" <<EOF
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

  chmod +x "$launcher"
  log "Installed launcher at $launcher"

  case ":$PATH:" in
    *":$bin_dir:"*) ;;
    *)
      printf '[!] %s is not in PATH. Add this line to your shell profile:\n' "$bin_dir"
      printf '    export PATH="%s:$PATH"\n' "$bin_dir"
      ;;
  esac
}

print_next_steps() {
  cat <<EOF

========================================
 CONNECT INSTALL COMPLETE
========================================
Repo: $REPO_DIR
Launcher: $HOME/.local/bin/connect

Next steps:
  1. Add an API key to $REPO_DIR/.env
  2. Open a new shell if PATH was updated
  3. Run: connect --doctor
  4. Run: connect
EOF
}

log "Starting CONNECT installer"
resolve_repo_dir
resolve_python
create_venv
install_requirements
ensure_env_file
ensure_data_dir
install_launcher
print_next_steps
