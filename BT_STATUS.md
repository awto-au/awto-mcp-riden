# Bluetooth Status

## BT Adapter
- Controller: `F8:3D:C6:37:F1:FD` (powered on)
- BlueZ ≥5.66 confirmed

## Paired Riden RK6006 Devices
1. `88:BB:52:09:E5:43` (primary)
2. `89:BB:52:09:E5:43` (secondary)

## Connection methods

### USB Serial (recommended for now)
When the Riden is plugged in via USB:
```bash
ls /dev/ttyUSB0
python3 riden_daemon.py --port /dev/ttyUSB0 --baud 115200
python3 ttu_cli.py status
```

### Bluetooth Serial (deferred)
The current `riden_daemon.py` wraps `pyserial` which doesn't support raw BLE.
To enable BT support, would need:
1. Native BLE layer (e.g., `bleak` library)
2. Or: implement `/dev/rfcomm*` socket pair (requires `rfcomm` from bluez-tools)

Both are out of scope for v0.1. Focus on USB for now.
