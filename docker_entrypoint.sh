#!/usr/bin/env bash
set -euo pipefail

################################################################################
ROLE="${ROLE:-ui}"                # only 'ui' needed for this repo
ENVIRONMENT="${ENVIRONMENT:-local}"
UI_PORT="${UI_PORT:-8501}"
################################################################################

run_ui() {
  FLAGS="--server.headless true --server.enableCORS false"
  [[ "$ENVIRONMENT" == "local" ]] && FLAGS+=" --server.runOnSave true"
  echo "♦ Streamlit on :${UI_PORT}  (${ENVIRONMENT})"
  streamlit run dash/00_IPD_Tournament.py \
      --server.address 0.0.0.0 \
      --server.port "$UI_PORT" \
      $FLAGS
}

case "$ROLE" in
  ui) run_ui ;;
  *)  echo "✘ ROLE must be ui (got: $ROLE)" && exit 1 ;;
esac
