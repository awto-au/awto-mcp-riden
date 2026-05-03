#!/usr/bin/env bash
# mcp_restart.sh — kill any running mcp_server.py so VS Code restarts it fresh.
#
# Usage:
#   bash scripts/mcp_restart.sh
#
# After running this, click "Restart" in the VS Code MCP panel, or run
# the command palette action "MCP: Restart Server > awto-riden".

set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== awto-riden MCP restart helper ==="

# 1. Show which serial device will be used
PORT=""
CANDIDATES=()
for pat in /dev/ttyUSB* /dev/ttyACM* /dev/rfcomm*; do
    [[ -e "$pat" ]] && CANDIDATES+=("$pat")
done
# sort candidates
IFS=$'\n' CANDIDATES=($(printf '%s\n' "${CANDIDATES[@]}" | sort -V 2>/dev/null || printf '%s\n' "${CANDIDATES[@]}" | sort))
unset IFS
if [[ ${#CANDIDATES[@]} -gt 0 ]]; then
    PORT="${CANDIDATES[0]}"
    echo "  serial device : $PORT  (auto-detect)"
    [[ ${#CANDIDATES[@]} -gt 1 ]] && echo "  other devices : ${CANDIDATES[*]:1}"
else
    echo "  WARNING: no serial devices found — mcp_server.py will fall back to /dev/ttyUSB0"
fi

# 2. Kill any running mcp_server.py
PIDS=$(pgrep -f "python.*mcp_server\.py" 2>/dev/null || true)
if [[ -n "$PIDS" ]]; then
    echo "  killing PIDs  : $PIDS"
    kill $PIDS
    sleep 0.5
    echo "  killed."
else
    echo "  mcp_server.py : not running"
fi

echo ""
echo "Done. In VS Code: open the MCP panel and click Restart (or Ctrl+Shift+P → MCP: Restart Server)."
