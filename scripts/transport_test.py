#!/usr/bin/env python3
# transport_test.py — quick sanity check for SerialTransport / RidenWorker.
#
# Opens the first available ttyUSB* (or --port override), reads status,
# and prints a summary. Does NOT change any PSU settings.
#
# Usage:
#   python3 scripts/transport_test.py
#   python3 scripts/transport_test.py --port /dev/ttyUSB1
#   python3 scripts/transport_test.py --port /dev/ttyUSB1 --baud 115200 --address 1

import argparse
import glob
import sys
import os

# Allow running from repo root or scripts/ directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from riden_daemon import RidenWorker


def auto_detect_port() -> str:
    for pattern in ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/rfcomm*"):
        candidates = sorted(glob.glob(pattern))
        if candidates:
            return candidates[0]
    return "/dev/ttyUSB0"


def main() -> None:
    p = argparse.ArgumentParser(description="Quick SerialTransport sanity check")
    p.add_argument("--port",    default=None,  help="Serial device (default: auto-detect)")
    p.add_argument("--baud",    type=int, default=115200)
    p.add_argument("--address", type=int, default=1)
    args = p.parse_args()

    port = args.port or auto_detect_port()
    print(f"Connecting to {port}  baud={args.baud}  addr={args.address} …")

    w = RidenWorker(port=port, baud=args.baud, address=args.address)
    try:
        w.open()
    except IOError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        s = w.status()
    except Exception as e:
        print(f"FAIL reading status: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        w.close()

    print(f"  model    : {s.get('model_type', '?')}  id={s.get('device_id', '?')}  fw={s.get('fw_version', '?')}")
    print(f"  v_set    : {s.get('v_set', '?')} V")
    print(f"  i_set    : {s.get('i_set', '?')} A")
    print(f"  v_out    : {s.get('v_out', '?')} V")
    print(f"  i_out    : {s.get('i_out', '?')} A")
    print(f"  p_out    : {s.get('p_out', '?')} W")
    print(f"  output   : {'ON' if s.get('output') else 'OFF'}")
    print(f"  cv_cc    : {s.get('cv_cc', '?')}")
    print(f"  protect  : {s.get('protect', '?') or 'none'}")
    print(f"  temp_c   : {s.get('temp_c', '?')} °C")
    print("OK")


if __name__ == "__main__":
    main()
