#!/usr/bin/env python3
"""Generate waveform documentation graphs from captured JSONL files."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
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


def _period_plot(ax, rows, label, min_cycles=1.5):
    if not rows:
        ax.set_title(f"{label} (no data)")
        return

    elapsed = np.array([r.get("elapsed_s", 0.0) for r in rows], dtype=float)
    if np.all(elapsed == 0.0):
        t0 = rows[0]["ts"]
        elapsed = np.array([r["ts"] - t0 for r in rows], dtype=float)

    freq_hz = max(float(rows[0].get("freq_hz", 0.5)), 1e-6)
    cycles = elapsed * freq_hz
    cycles_max = float(np.max(cycles)) if len(cycles) else 0.0
    target_max = min_cycles if cycles_max >= min_cycles else cycles_max
    mask = cycles <= target_max

    x     = cycles[mask]
    v_set = np.array([r.get("v_set", 0.0) for r in rows], dtype=float)[mask]
    v_out = np.array([r.get("v_out", 0.0) for r in rows], dtype=float)[mask]
    i_out = np.array([r.get("i_out", 0.0) for r in rows], dtype=float)[mask]

    if len(x) >= 2:
        xd = np.linspace(float(x.min()), float(x.max()), 400)
        vsd = np.interp(xd, x, v_set)
        vod = np.interp(xd, x, v_out)
        iod = np.interp(xd, x, i_out)
    else:
        xd, vsd, vod, iod = x, v_set, v_out, i_out

    ax.plot(xd, vsd, "--", lw=1.6, color="#5588BB", label="V_set")
    ax.plot(xd, vod, "-",  lw=2.4, color="#E07000", label="V_out")
    ax.set_xlim(0, max(1.5, float(x.max()) if len(x) else 1.5))
    ax.set_xlabel("Cycles")
    ax.set_ylabel("Voltage (V)")
    ax.set_title(label, fontsize=10)
    ax.grid(True, alpha=0.22, linestyle=":")

    v_min = min(float(v_set.min()), float(v_out.min()))
    v_max = max(float(v_set.max()), float(v_out.max()))
    pad = max(0.3, 0.07 * (v_max - v_min))
    ax.set_ylim(v_min - pad, v_max + pad)

    ax2 = ax.twinx()
    ax2.plot(xd, iod, "-", lw=1.8, color="#CC2222", label="I_out")
    ax2.set_ylabel("Current (A)", color="#CC2222")
    ax2.tick_params(axis="y", labelcolor="#CC2222")
    i_min, i_max = float(i_out.min()), float(i_out.max())
    i_pad = max(0.02, 0.12 * max(i_max - i_min, 0.05))
    ax2.set_ylim(i_min - i_pad, i_max + i_pad)

    overshoot = float(np.max(v_out - v_set)) if len(v_out) else 0.0
    ax.text(0.02, 0.05, f"max overshoot: {overshoot:+.3f} V",
            transform=ax.transAxes, fontsize=8, color="#555")

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8, framealpha=0.9)


def _clip_plot(ax, rows):
    if not rows:
        ax.set_title("Current-limited sine clipping (no data)")
        return
    t0 = rows[0]["ts"]
    t     = np.array([r["ts"] - t0            for r in rows], dtype=float)
    v_set = np.array([r.get("v_set",    0.0)  for r in rows], dtype=float)
    v_out = np.array([r.get("v_out",    0.0)  for r in rows], dtype=float)
    i_out = np.array([r.get("i_out",    0.0)  for r in rows], dtype=float)
    cc    = np.array([r.get("cv_cc",   "CV")  for r in rows])
    prot  = np.array([r.get("protect", "none") for r in rows])
    in_cc = cc == "CC"

    # V_set dashed, V_out solid; CC portion overdrawn in red.
    ax.plot(t, v_set, "--", lw=1.5, color="#5588BB", label="V_set")
    ax.plot(t, np.where(~in_cc, v_out, np.nan), "-", lw=2.2, color="#E07000", label="V_out (CV)")
    ax.plot(t, np.where( in_cc, v_out, np.nan), "-", lw=2.5, color="#CC2222", label="V_out (CC)")

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Voltage (V)")
    ax.grid(True, alpha=0.22, linestyle=":")
    ax.set_title("Sine under current limiting — CV=orange, CC=red")

    v_min = min(float(v_set.min()), float(v_out.min()))
    v_max = max(float(v_set.max()), float(v_out.max()))
    pad = max(0.25, 0.08 * (v_max - v_min))
    ax.set_ylim(v_min - pad, v_max + pad)

    ax2 = ax.twinx()
    ax2.plot(t, np.where(~in_cc, i_out, np.nan), "-", lw=1.8, color="#E07000", label="I_out (CV)")
    ax2.plot(t, np.where( in_cc, i_out, np.nan), "-", lw=2.2, color="#CC2222", label="I_out (CC)")
    ax2.set_ylabel("Current (A)", color="#CC2222")
    ax2.tick_params(axis="y", labelcolor="#CC2222")
    i_min, i_max = float(i_out.min()), float(i_out.max())
    ax2.set_ylim(i_min - max(0.01, 0.12*max(i_max-i_min,0.05)),
                 i_max + max(0.01, 0.12*max(i_max-i_min,0.05)))

    n_oc = int(np.sum(prot != "none"))
    ax.text(0.02, 0.05,
            f"CC samples: {int(np.sum(in_cc))}/{len(rows)}  |  OCP events: {n_oc}",
            transform=ax.transAxes, fontsize=8, color="#555")

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8, framealpha=0.9)


def _cc_demo_plot(ax, rows, title):
    if not rows:
        ax.set_title(f"{title} (no data)")
        return

    t0    = rows[0]["ts"]
    t     = np.array([r["ts"] - t0            for r in rows], dtype=float)
    v_set = np.array([r.get("v_set",    0.0)  for r in rows], dtype=float)
    v_out = np.array([r.get("v_out",    0.0)  for r in rows], dtype=float)
    i_out = np.array([r.get("i_out",    0.0)  for r in rows], dtype=float)
    cc    = np.array([r.get("cv_cc",   "CV")  for r in rows])
    in_cc = cc == "CC"

    # V_set dashed reference; V_out CV=orange, CC=red.
    ax.plot(t, v_set, "--", lw=1.5, color="#5588BB", label="V_set")
    ax.plot(t, np.where(~in_cc, v_out, np.nan), "-", lw=2.2, color="#E07000", label="V_out (CV)")
    ax.plot(t, np.where( in_cc, v_out, np.nan), "-", lw=2.5, color="#CC2222", label="V_out (CC)")

    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Voltage (V)")
    ax.grid(True, alpha=0.22, linestyle=":")

    v_min = min(float(v_set.min()), float(v_out.min()))
    v_max = max(float(v_set.max()), float(v_out.max()))
    v_pad = max(0.3, 0.07 * max(v_max - v_min, 0.5))
    ax.set_ylim(v_min - v_pad, v_max + v_pad)

    ax2 = ax.twinx()
    ax2.plot(t, np.where(~in_cc, i_out, np.nan), "-", lw=1.8, color="#E07000", label="I_out (CV)")
    ax2.plot(t, np.where( in_cc, i_out, np.nan), "-", lw=2.2, color="#CC2222", label="I_out (CC)")
    ax2.set_ylabel("Current (A)", color="#CC2222")
    ax2.tick_params(axis="y", labelcolor="#CC2222")
    i_min, i_max = float(i_out.min()), float(i_out.max())
    i_pad = max(0.01, 0.12 * max(i_max - i_min, 0.05))
    ax2.set_ylim(i_min - i_pad, i_max + i_pad)

    ax.text(0.02, 0.05,
            f"CC samples: {int(np.sum(in_cc))}/{len(rows)}",
            transform=ax.transAxes, fontsize=8, color="#555")

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8, framealpha=0.9)


def main() -> int:
    in_dir = Path("docs")
    period_png = in_dir / "mr11_waveform_tracking_at_least_1p5_cycle_view_same_settings_overshoot_visible.png"
    clip_png = in_dir / "mr11_sine_under_current_limiting_clipping_cc_transitions.png"
    cc_demo_png = in_dir / "mr11_current_limit_demo_i200ma_sine_0_12v_and_i300ma_fixed_12v.png"

    period_sets = [
        (in_dir / "mr11_sine_period.jsonl", "Sine (period-wide)"),
        (in_dir / "mr11_sawtooth_period.jsonl", "Sawtooth (period-wide)"),
        (in_dir / "mr11_triangle_period.jsonl", "Triangle (period-wide)"),
        (in_dir / "mr11_square_period.jsonl", "Square on/off (period-wide)"),
    ]

    fig, axes = plt.subplots(4, 1, figsize=(13, 14), tight_layout=True)
    fig.suptitle(
        "MR11 waveform tracking — >=1.5-cycle view (same settings, overshoot visible)",
        fontsize=12,
        fontweight="bold",
    )
    for ax, (path, label) in zip(axes, period_sets):
        _period_plot(ax, load(path), label)
    plt.savefig(period_png, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {period_png}")

    clip_rows = load(in_dir / "mr11_sine_clipped_current_limit.jsonl")
    fig, ax = plt.subplots(1, 1, figsize=(13, 5.6), tight_layout=True)
    _clip_plot(ax, clip_rows)
    plt.savefig(clip_png, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {clip_png}")

    # Dedicated current-limit demo: red segments indicate CC-limited operation.
    fig, axes = plt.subplots(2, 1, figsize=(13, 9.2), tight_layout=True)
    _cc_demo_plot(
        axes[0],
        load(in_dir / "mr11_current_limit_demo_sine_0_12v_i200ma.jsonl"),
        "Current-limit demo: sine 0-12 V with fixed 200 mA limit",
    )
    _cc_demo_plot(
        axes[1],
        load(in_dir / "mr11_current_limit_demo_fixed_12v_i300ma.jsonl"),
        "Current-limit demo: fixed 12 V with fixed 300 mA limit",
    )
    plt.savefig(cc_demo_png, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {cc_demo_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
