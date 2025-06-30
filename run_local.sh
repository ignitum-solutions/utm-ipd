#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Local launcher for the UTM-IPD project.
#
# Flags
#   --prune       : After containers are up, remove dangling images.
#   --no-cache    : Rebuild images from scratch (no cache).
#
# Examples
#   ./run_local.sh                   # normal rebuild + follow logs
#   ./run_local.sh --prune           # rebuild, then prune images
#   ./run_local.sh --no-cache        # cache-busting rebuild
#   ./run_local.sh --no-cache --prune
# ──────────────────────────────────────────────────────────────
set -e

PRUNE=0
NOCACHE=0

for arg in "$@"; do
  case "$arg" in
    --prune)    PRUNE=1 ;;
    --no-cache) NOCACHE=1 ;;
    *)
      echo "Unknown flag: $arg" >&2
      exit 1
      ;;
  esac
done

# ----------------------------------------------------------------------
# Environment tweaks that prevent Streamlit hot-reload + Axelrod CSV dump
# ----------------------------------------------------------------------
export STREAMLIT_SERVER_RUN_ON_SAVE="false"
export AXELROD_SAVE_INTERACTIONS="0"

if [[ $PRUNE -eq 1 ]]; then
  echo "🧹 Pruning dangling images…"
  docker image prune -f
fi

echo "⏳ Building & starting containers…"
if [[ $NOCACHE -eq 1 ]]; then
  docker compose build --no-cache
fi

docker compose up --build

echo "✅ Streamlit UI → http://localhost:8501"