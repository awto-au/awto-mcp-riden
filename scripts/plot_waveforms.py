#!/usr/bin/env python3
"""Generate layered waveform documentation graphs from captured JSONL files."""
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np


def load(path):
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def plot_waveform_panel(ax, rows, label, color_v="#1f77b4", color_i="#d62728"):
    if not rows:
        return
    t0 = rows[0]["ts"]
    t  = np.array([r["ts"] - t0 for r in rows])
    vs = np.array([r.get("v_set", r["v_out"]) for r in rows])
    v  = np.array([r["v_out"] for r in rows])
    i  = np.array([r["i_out"] for r in rows])

    dt_med = float(np.median(np.diff(t))) if len(t) > 1 else 0
    rate   = f"≈{1/dt_med:.1f} Hz" if dt_med > 0 else "?"

    ax.set_title(f"{label}  (poll {rate}, Δt median {dt_med*1000:.0f} ms)", pad=6, fontsize=9)
    ax.set_ylabel("Voltage (V)", color=color_v, fontsize=8)
    ax.tick_params(axis="y", labelcolor=color_v, labelsize=7)
    ax.tick_params(axis="x", labelsize=7)
    ax.set_ylim(7, 13)

    # V_set as dotted reference
    ax.plot(t, vs, "--", color=color_v, linewidth=0.8, alpha=0.5, label="V_set")
    # V_out solid
    ax.plot(t, v, "-", color=color_v, linewidth=1.4, label="V_out")

    ax2 = ax.twinx()
    ax2.set_ylabel("Current (A)", color=color_i, fontsize=8)
    ax2.tick_params(axis="y", labelcolor=color_i, labelsize=7)
    ax2.plot(t, i, "-", color=color_i, linewidth=1.2, alpha=0.85, label="I_out")
    ax2.set_ylim(bottom=0)

    # CC shading
    if "cv_cc" in rows[0]:
        in_cc, t_start = False, 0.0
        for idx, r in enumerate(rows):
            if r.get("cv_cc") == "CC" and not in_cc:
                t_start = t[idx]; in_cc = True
            elif r.get("cv_cc") != "CC" and in_cc:
                ax.axvspan(t_start, t[idx], alpha=0.12, color="orange")
                in_cc = False
        if in_cc:
            ax.axvspan(t_start, t[-1], alpha=0.12, color="orange", label="CC mode")

    # Legend
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    seen, hs, ls = set(), [], []
    for h, l in zip(h1 + h2, l1 + l2):
        if l not in seen:
            seen.add(l); hs.append(h); ls.append(l)
    ax.legend(hs, ls, loc="upper right", fontsize=7, framealpha=0.7)
    ax.set_xlabel("Time (s)", fontsize=8)


# --- Slow waveforms (1 Hz, 0.5s step) ---
slow_files = [
    ("/tmp/wf_sine_1s.jsonl",   "Sine 1 Hz (step 0.5 s)"),
    ("/tmp/wf_tri_1s.jsonl",    "Triangle 1 Hz (step 0.5 s)"),
    ("/tmp/wf_sq_1s.jsonl",     "Square 1 Hz (step 0.5 s)"),
]

fig, axes = plt.subplots(3, 1, figsize=(13, 12), tight_layout=True)
fig.suptitle("MR11 LED Lamp — Waveform Response (8–12 V, I_lim 1.5 A)\n"
             "Slow waveforms: 1 Hz period, 500 ms voltage steps",
             fontsize=11, fontweight="bold")
for ax, (path, label) in zip(axes, slow_files):
    plot_waveform_panel(ax, load(path), label)

out_slow = "/tmp/waveform_slow.png"
plt.savefig(out_slow, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"Saved: {out_slow}")

# --- Fast waveforms (5 Hz, 0.1s step) ---
fast_files = [
    ("/tmp/wf_sine_fast.jsonl", "Sine 5 Hz (step 0.1 s)"),
    ("/tmp/wf_sq_fast.jsonl",   "Square 5 Hz (step 0.1 s)"),
]

fig, axes = plt.subplots(2, 1, figsize=(13, 9), tight_layout=True)
fig.suptitle("MR11 LED Lamp — Waveform Response (8–12 V, I_lim 1.5 A)\n"
             "Fast waveforms: 5 Hz period, 100 ms voltage steps\n"
             "Note: Modbus RTU poll ≈ 100–200 ms → significant lag vs step period visible",
             fontsize=11, fontweight="bold")
for ax, (path, label) in zip(axes, fast_files):
    plot_waveform_panel(ax, load(path), label)

out_fast = "/tmp/waveform_fast.png"
plt.savefig(out_fast, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"Saved: {out_fast}")
