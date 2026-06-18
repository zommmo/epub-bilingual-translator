#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

log() {
  printf "\n[Paperford] %s\n" "$1"
}

python_ok() {
  command -v "$1" >/dev/null 2>&1 || return 1
  timeout 8s "$1" -c 'import sys; raise SystemExit(0 if (3, 10) <= sys.version_info < (3, 14) else 1)' >/dev/null 2>&1
}

select_python() {
  for candidate in python3.12 python3.11 /usr/bin/python3 python3; do
    if python_ok "$candidate"; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

log "Selecting a Python runtime..."
PYTHON_BIN="$(select_python || true)"
if [ -z "${PYTHON_BIN}" ]; then
  cat <<'MSG'

Paperford needs a working Python between 3.10 and 3.13.
Your current Python may be too new or not responding.

Try installing Python 3.12:
  brew install python@3.12

Then run:
  ./run_web.sh
MSG
  exit 1
fi
log "Using Python: $("$PYTHON_BIN" --version 2>&1) at ${PYTHON_BIN}"

if [ -x "/opt/homebrew/opt/node@22/bin/node" ]; then
  export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
fi
log "Using Node: $(node --version) at $(command -v node)"

if [ -x ".venv/bin/python" ]; then
  if ! timeout 8s .venv/bin/python -c 'import sys; raise SystemExit(0 if (3, 10) <= sys.version_info < (3, 14) else 1)' >/dev/null 2>&1; then
    backup=".venv.broken.$(date +%Y%m%d%H%M%S)"
    log "Existing .venv is not usable for this project. Moving it to ${backup} ..."
    mv .venv "$backup"
  fi
fi

if [ ! -x ".venv/bin/python" ]; then
  log "Creating Python virtual environment..."
  "$PYTHON_BIN" -m venv .venv
fi

log "Installing Python dependencies..."
.venv/bin/python -m pip install -r requirements.txt

if [ ! -d "frontend/node_modules" ]; then
  log "Installing frontend dependencies..."
  (cd frontend && npm install)
fi

log "Building frontend with Vite..."
(cd frontend && npm run build)

log "Checking backend imports..."
.venv/bin/python -c 'import api_app; print("backend import ok")'

log "Starting Paperford. Open http://127.0.0.1:8000 in your browser."
.venv/bin/python -m uvicorn api_app:app --host 127.0.0.1 --port 8000
