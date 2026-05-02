#!/usr/bin/env bash
set -euo pipefail

# One-command regeneration for timing artifacts used in docs and README.

PORT="${1:-/dev/ttyUSB0}"
VOLTAGE="${2:-1.0}"
CURRENT="${3:-0.2}"

echo ""
echo "WARNING: this script turns the PSU output ON at ${VOLTAGE} V / ${CURRENT} A."
echo "  Ensure a compatible load is connected. Ctrl-C now to abort."
echo ""
sleep 3

source .venv/bin/activate
python3 scripts/timing_test_set.py \
  --port "$PORT" \
  --voltage "$VOLTAGE" \
  --current "$CURRENT" \
  --mode both \
  --quick-samples 12 \
  --comprehensive-samples 80 \
  --quick-poll-ms 0,100,150 \
  --comprehensive-poll-ms 0,20,50,100,150

echo "Done: regenerated timing suite artifacts in docs/."
