# BLE Over-the-Air Trace Analysis (2026-05-02)

## Scope
This note captures what is happening on-air (HCI/ATT level) for RK6006 BLE-UART traffic, based on btmon snoop capture and concurrent `scripts/ble_profile.py` runs.

- Device: RK6006 (`88:BB:52:09:E5:43`)
- Host adapter: `hci0`
- Capture file: `/tmp/bt_trace.snoop`
- Profiler run: 12 polls at `--sleep-ms 150`
- Observed application RTTs: `141.5, 134.8, 5004.0, 125.3, 134.7, 134.6, 142.7, 134.5, 5001.3, 128.0, 134.9, 5000.8` ms

## Key On-Air Findings

### 1) Link setup is healthy and fast
From LE connection complete / update events:

- Connection interval negotiated: `7.50 ms` (`0x0006`)
- Connection latency: `0`
- Supervision timeout: `1000 ms`
- No disconnect events during the 5 second application timeouts

Interpretation: the BLE link itself is stable and not dropping.

### 2) ATT traffic pattern is normal when successful
Successful transactions show the expected pair:

1. `ATT Write Command (0x52)` to FFE1
2. `ATT Handle Value Notification (0x1b)` from FFE1 with Modbus reply payload

Measured wire RTTs (write -> notify) from trace timestamps:

- 95 ms
- 125 ms
- 127 ms
- 134 ms (common)
- 141 ms
- 142 ms

These values align with your observed 125-143 ms mode under 150 ms polling and map to multiples of the 7.5 ms connection interval.

### 3) The 5 second failures are missing notifications, not RF loss
For timeout polls, the trace shows:

- Host `Write Command` goes out over air
- Controller confirms packet completion (`Number of Completed Packets`)
- No matching `Handle Value Notification` ever arrives
- Connection remains up

Interpretation: the command is sent, but the peripheral side fails to emit the notify reply for that transaction.

## Root Cause Assessment
Most likely issue is in the RK6006 BLE-UART bridge firmware path (or its internal UART-to-notify queue handling):

- Not BlueZ API misuse at this point
- Not connection parameter negotiation failure
- Not host adapter RF disconnect
- Failure mode is per-transaction reply drop on peripheral side

## Practical Mitigations

1. Add immediate retry on timeout
- On a single transaction timeout, resend once (or twice) before surfacing an error.
- This converts a 5000 ms stall into roughly one extra transaction latency.

2. Keep poll cadence conservative
- `--sleep-ms 200` showed much better stability in your runs.
- Avoid aggressive cadence if long-term reliability is the priority.

3. Keep notify session persistent
- Already implemented and correct: start notify once per connection, stop at end.

4. Keep queue-drain before each write
- Already implemented and correct: avoids stale packet poisoning across polls.

## Suggested Next Step
Implement timeout retry in `scripts/ble_profile.py` and `scripts/ble_globe_turnon.py` transaction loops, then re-run:

- 30 polls at 150 ms
- 30 polls at 200 ms

Record both drop rate and effective median RTT to pick production defaults.

## Repro Commands

```bash
# Capture on-air traffic
sudo btmon -w /tmp/bt_trace.snoop

# In parallel, run BLE profile
source .venv/bin/activate
python3 scripts/ble_profile.py --count 12 --sleep-ms 150

# Decode capture
sudo btmon -r /tmp/bt_trace.snoop
```

## Bottom Line
The air trace confirms the API-level suspicion: the 5 second outliers come from missing ATT notifications while the BLE link remains connected and healthy. This points to a peripheral bridge/firmware reply-loss behavior under load, not host-side transport setup.
