# BLE Support Roadmap

**Status:** v0.1 is USB-serial only. BLE support is planned for v0.2+.

## Motivation

Two Bluetooth RK6006 power supplies are available on the system:
- `88:BB:52:09:E5:43` (primary)
- `89:BB:52:09:E5:43` (secondary)

These are paired but not yet integrated with the daemon.

## Current State

- ✅ USB/serial transport working (via ShayBox/Riden library)
- ✅ Modbus RTU protocol understood (slave addr 1, 115200 baud)
- ✅ `bleak>=0.22` already in `pyproject.toml` (BLE client library)
- ⏳ Native BLE transport **not yet implemented**

## Discovery Attempt (v0.1.0-alpha)

**File:** `ble_discover.py` (created but incomplete)

```python
# Attempted to connect and enumerate RK6006 BLE GATT profile
async with BleakClient("88:BB:52:09:E5:43") as client:
    services = await client.get_services()
    # enumerate UUIDs...
```

**Result:** Connection initiated but GATT service enumeration timed out after 10s.

**Likely causes:**
1. RK6006 BLE GATT database is large (many services/characteristics)
2. BlueZ stack on this system is slow or has high latency
3. Device may be asleep or requires additional pairing handshake
4. `/dev/rfcomm0` binding not yet established

## Path to v0.2 (BLE Support)

### Phase 1: Profile Discovery
**Goal:** Identify RK6006 BLE GATT services and characteristic UUIDs.

**Steps:**
1. Update `ble_discover.py` to add timeout **per service** (not per scan)
   - Try 5s timeout for discovery, 2s per service enumeration
   - Log which service/characteristic causes delays
2. Cross-reference with RK6006 manufacturer docs or reverse-engineer from firmware
3. Identify:
   - Modbus TX characteristic (client writes to PSU)
   - Modbus RX characteristic (client reads from PSU, or subscribes to notify)
4. Document UUIDs in code comment

**References:**
- ShayBox/Riden library (serial Modbus RTU): https://github.com/ShayBox/Riden
- BLE spec: https://www.bluetooth.com/
- `bleak` docs: https://github.com/hbldh/bleak

### Phase 2: Transport Layer
**Goal:** Implement native Modbus RTU over BLE in daemon.

**Changes to `riden_daemon.py`:**

1. Add BLE connection logic to `RidenWorker.open()`:
   ```python
   if self._is_ble_mac(self._port):
       self._psu = None  # No pyserial object for BLE
       self._ble_client = await BleakClient(self._port).connect()
       self._ble_rx_char = <discovered RX characteristic UUID>
       self._ble_tx_char = <discovered TX characteristic UUID>
   else:
       self._psu = Riden(port=self._port, ...)
   ```

2. Update `RidenWorker.query()` to branch on BLE vs serial:
   ```python
   if self._ble_client:
       # Write to TX characteristic, wait for RX notify
       await self._ble_client.write_gatt_char(self._ble_tx_char, request)
       response = await asyncio.wait_for(self._ble_rx_queue.get(), timeout=1.0)
   else:
       # Serial write/read (existing code)
       self._psu.write(request)
       response = self._psu.read()
   ```

3. Background task to subscribe to BLE RX notifications:
   ```python
   async def _ble_notify_callback(sender, data):
       self._ble_rx_queue.put_nowait(data)
   
   await self._ble_client.start_notify(
       self._ble_rx_char,
       _ble_notify_callback
   )
   ```

### Phase 3: Integration & Testing
**Goal:** Full integration test with real RK6006 device.

**Steps:**
1. Run daemon with BLE device MAC:
   ```bash
   python3 riden_daemon.py --port 88:BB:52:09:E5:43 --baud 115200
   ```

2. Query status via CLI:
   ```bash
   python3 ttu_cli.py status
   ```

3. Verify response matches USB serial baseline

4. Stress test: Rapid command sequences, concurrent clients, network latency

5. Add unit tests to `test_harness.py` for BLE path (mock `BleakClient`)

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| RK6006 BLE GATT profile unknown | Research manufacturer docs, reverse-engineer from firmware or Wireshark capture |
| BlueZ latency or pairing issues | Add detailed logging, test with `bluetoothctl` first |
| Async/sync bridging complexity | Use `asyncio.run()` wrapper in daemon (single-threaded event loop per BLE client) or run in thread pool |
| Bluetooth range/stability | Test at multiple distances, add automatic reconnect with exponential backoff |

## Deferred (v0.3+)

- BLE bonding & persistent pairing
- Multiple BLE devices in parallel (requires multiple daemons or multiplex via single daemon)
- BLE security (encrypted pairing, PIN verification)
- Over-the-air firmware updates via BLE

## Quick Start (When Ready)

```bash
# Install dependencies
pip install bleak>=0.22

# Run discovery
python3 ble_discover.py

# Update RK6006 GATT UUIDs in riden_daemon.py

# Launch daemon
python3 riden_daemon.py --port 88:BB:52:09:E5:43

# Test
python3 ttu_cli.py status
```

## References

- RK6006 specs: https://www.riden.net/
- ShayBox/Riden (Modbus RTU): https://github.com/ShayBox/Riden
- bleak library: https://github.com/hbldh/bleak
- Modbus RTU spec: https://en.wikipedia.org/wiki/Modbus
