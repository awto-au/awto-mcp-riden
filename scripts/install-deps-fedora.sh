#!/usr/bin/env bash
# Install awto-mcp-riden dependencies on Fedora.
# dnf is used where packages exist; pip fallback for anything not in repos.
set -euo pipefail

echo "==> awto-mcp-riden: installing system dependencies via dnf"

sudo dnf install -y \
    python3 \
    python3-pip \
    python3-psutil \
    python3-colorlog \
    python3-pyserial

# python3.14 free-threaded (recommended for daemon performance)
if ! command -v python3.14t &>/dev/null; then
    echo "==> installing python3.14 free-threaded"
    sudo dnf install -y python3.14 || true
    # Free-threaded build — may need copr or manual build on older Fedora
    sudo dnf install -y python3.14-freethreading 2>/dev/null || \
        echo "    NOTE: python3.14-freethreading not available — daemon will run with GIL"
fi

echo "==> installing pip-only packages (not in Fedora repos)"
pip install --user \
    "mcp[cli]" \
    "rich-argparse>=1.4" \
    "riden @ git+https://github.com/ShayBox/Riden.git"

echo ""
echo "==> done. Set up the free-threaded venv:"
echo "    uv venv --python python3.14t .venv-ft"
echo "    uv pip install -e . --python .venv-ft/bin/python"
echo ""
echo "==> start the daemon:"
echo "    .venv-ft/bin/python riden_daemon.py --port /dev/ttyUSB0"
echo "    # or for BT serial:"
echo "    .venv-ft/bin/python riden_daemon.py --port /dev/rfcomm0"
