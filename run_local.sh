#!/usr/bin/env bash
# Launch the React research interface and direct streaming Python API together.
set -euo pipefail
cd "$(dirname "$0")"
if [[ $# -gt 0 ]]; then
  echo "Usage: ./run_local.sh (see README.md for setup and legacy Docker instructions)" >&2
  exit 1
fi
exec poetry run python scripts/dev.py
