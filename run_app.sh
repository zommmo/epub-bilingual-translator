#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

if ! .venv/bin/python -m streamlit --version >/dev/null 2>&1; then
  .venv/bin/python -m pip install -r requirements.txt
fi

.venv/bin/python -m streamlit run app.py
