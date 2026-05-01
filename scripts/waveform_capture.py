#!/usr/bin/env python3
"""Capture waveform data for documentation graphs.

Runs sine/triangle/square at slow (1 Hz) and fast (5 Hz) periods,
8–12 V range, recording V_set, V_out, I_out, CV/CC, protect, output.
"""
import time, json, math, sys
sys.path.insert(0, "/home/dan/git/awto-mcp-riden")
from riden_transport import SerialTransport
from riden_daemon import RidenDevice

PORT     = "/dev/ttyUSB0"
REG_VOUT = 10
REG_CNT  = 9
PROT_MAP = {0: "none", 1: "OVP", 2: "OCP"}
V_CENTER = 10.0
V_AMP    = 2.0   # 8–12 V

captures = [
    # sine step must NOT be a multiple of 1/(2*freq) to avoid aliasing where sin(nπ)=0
    ("sine",     0.5, 0.45, 20, "/tmp/wf_sine_slow.jsonl"),
    ("triangle", 0.5, 0.5,  20, "/tmp/wf_tri_slow.jsonl"),
    ("square",   0.5, 0.5,  20, "/tmp/wf_sq_slow.jsonl"),
    ("sine",     2.0, 0.09, 10, "/tmp/wf_sine_fast.jsonl"),
    ("square",   2.0, 0.1,  10, "/tmp/wf_sq_fast.jsonl"),
]

tr = SerialTransport(PORT, 115200, 1)
tr.open()
psu = RidenDevice(tr)
psu.set_i_set(1.5)

for shape, freq, step, dur, log_path in captures:
    rows = []
    psu.set_v_set(8.0)
    psu.set_output(True)
    t0 = time.perf_counter()
    last_v_set = None
    while True:
        now = time.perf_counter()
        elapsed = now - t0
        if elapsed >= dur:
            break
        # Target voltage based on continuous time (not step-quantised)
        phase = (elapsed * freq) % 1.0
        if shape == "sine":
            v = V_CENTER + V_AMP * math.sin(2 * math.pi * phase)
        elif shape == "triangle":
            v = V_CENTER + V_AMP * (4 * abs(phase - 0.5) - 1)
        else:  # square
            v = (V_CENTER + V_AMP) if phase < 0.5 else (V_CENTER - V_AMP)
        v = max(8.0, min(12.0, round(v, 2)))
        if v != last_v_set:
            psu.set_v_set(v)
            last_v_set = v
        raw   = tr.read(REG_VOUT, REG_CNT)
        v_out = round(psu.get_v_out(raw[0]), 3)
        i_out = round(psu.get_i_out(raw[1]), 4)
        cv_cc = "CV" if raw[7] == 0 else "CC"
        prot  = PROT_MAP.get(raw[6], "none")
        out   = bool(raw[8])
        rows.append({"ts": time.time(), "v_set": v, "v_out": v_out, "i_out": i_out,
                     "cv_cc": cv_cc, "protect": prot, "output": out})
    psu.set_output(False)
    with open(log_path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"{shape:8s} {freq:4.1f}Hz  -> {len(rows):3d} rows  {log_path}")
    time.sleep(1.5)

# Reset PSU — output OFF, voltage back to safe standby
psu.set_v_set(12.0)
psu.set_i_set(1.0)
psu.set_output(False)
tr.close()
print("Done — PSU reset to 12V/1A, output OFF")
