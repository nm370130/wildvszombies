#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Wild vs Zombies — local simulation runner
#
# Usage:
#   bash run.sh          # smoke test (10 K sims, fast)
#   bash run.sh prod     # production run (1 M / 500 K sims)
#
# Requirements:
#   Local math-sdk at ~/go/src/math-sdk (already cloned)
#   Virtualenv already created with:
#     cd ~/go/src/math-sdk && python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
# ─────────────────────────────────────────────────────────────────────────────

SDK="$HOME/go/src/math-sdk"
VENV="$SDK/.venv/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$VENV" ]; then
    echo "ERROR: venv not found at $VENV"
    echo "Run:  cd $SDK && python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

cd "$SCRIPT_DIR"
PYTHONPATH="$SDK" "$VENV" run.py "$@"
