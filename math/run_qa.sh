#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Wild vs Zombies — QA Test Runner
#
# Usage:
#   bash run_qa.sh
# ─────────────────────────────────────────────────────────────────

SDK="$HOME/go/src/math-sdk"
VENV="$SDK/.venv/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$VENV" ]; then
    echo "ERROR: venv not found at $VENV"
    exit 1
fi

cd "$SCRIPT_DIR"
PYTHONPATH="$SDK" "$VENV" qa_tests.py
