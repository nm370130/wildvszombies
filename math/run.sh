#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Wild vs Zombies — local simulation runner
#
# Usage:
#   bash run.sh          # smoke test (1 K sims, fast)
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
GAME_DIR="$SDK/games/wild_vs_zombies"

if [ ! -f "$VENV" ]; then
    echo "ERROR: venv not found at $VENV"
    echo "Run:  cd $SDK && python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Sync game files into SDK so analytics/format-check relative paths resolve.
# Clear library first so stale _0 LUT files from previous runs don't cause
# index mismatches in the analytics module.
mkdir -p "$GAME_DIR"
rm -rf "$GAME_DIR/library"
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='library/' \
    "$SCRIPT_DIR/" "$GAME_DIR/"

# Run from SDK root — the SDK writes output to games/wild_vs_zombies/library/
# using paths relative to the SDK root
cd "$SDK"
PYTHONPATH="$SDK:$GAME_DIR" "$VENV" "$GAME_DIR/run.py" "$@"
