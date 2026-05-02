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

    freq_hz = float(rows[0].get("freq_hz", 0.5))
    freq_hz = max(freq_hz, 1e-6)
    cycles = elapsed * freq_hz

    cycles_max = float(np.max(cycles)) if len(cycles) else 0.0
    target_max = min_cycles if cycles_max >= min_cycles else cycles_max
    mask = cycles <= target_max

    x = cycles[mask]
    v_set = np.array([r.get("v_set", 0.0) for r in rows], dtype=float)[mask]
    v_out = np.array([r.get("v_out", 0.0) for r in rows], dtype=float)[mask]
    i_out = np.array([r.get("i_out", 0.0) for r in rows], dtype=float)[mask]

    # Build smooth traces from sparse samples while keeping raw points visible.
    if len(x) >= 2:
        x_dense = np.linspace(float(np.min(x)), float(np.max(x)), 320)
        vs_dense = np.interp(x_dense, x, v_set)
        vo_dense = np.interp(x_dense, x, v_out)
        io_dense = np.interp(x_dense, x, i_out)
    else:
        x_dense = x
        vs_dense = v_set
        vo_dense = v_out
        io_dense = i_out

    ax.plot(x_dense, vs_dense, "--", linewidth=1.8, alpha=0.75, color="#4C90C0", label="V_set")
    ax.plot(x_dense, vo_dense, "-", linewidth=2.2, color="#D06700", label="V_out")
    ax.scatter(x, v_out, s=12, color="#D06700", alpha=0.6, zorder=3, label="V_out samples")
    ax.set_xlim(0, max(1.5, float(np.max(x)) if len(x) else 1.5))
    ax.set_xlabel("Cycle index (phase-0 markers at integers)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title(label)
    ax.grid(True, alpha=0.28)

    # Explicitly mark phase 0 for each cycle boundary.
    max_cycle_line = int(np.ceil(float(np.max(x)) if len(x) else 0.0))
    for c in range(0, max_cycle_line + 1):
        ax.axvline(float(c), color="#777777", alpha=0.18, linewidth=1.0)

    if len(x) > 0:
        ax.scatter([x[0]], [v_out[0]], s=44, color="#B00020", zorder=5, label="sample @ cycle 0")

    v_min = min(float(np.min(v_set)), float(np.min(v_out)))
    v_max = max(float(np.max(v_set)), float(np.max(v_out)))
    pad = max(0.25, 0.08 * (v_max - v_min))
    ax.set_ylim(v_min - pad, v_max + pad)

    ax2 = ax.twinx()
    ax2.plot(x_dense, io_dense, "-", linewidth=1.8, alpha=0.9, color="#CC2F2F", label="I_out")
    ax2.scatter(x, i_out, s=10, color="#CC2F2F", alpha=0.5, zorder=3, label="I_out samples")
    ax2.set_ylabel("Current (A)", color="#d62728")
    ax2.tick_params(axis="y", labelcolor="#d62728")

    i_min = float(np.min(i_out))
    i_max = float(np.max(i_out))
    i_pad = max(0.02, 0.12 * (i_max - i_min if i_max > i_min else 0.1))
    ax2.set_ylim(i_min - i_pad, i_max + i_pad)

    overshoot = float(np.max(v_out - v_set)) if len(v_out) else 0.0
    ax.text(
        0.02,
        0.92,
        f"max overshoot: {overshoot:.3f} V | plotted window: {max(1.5, float(np.max(x)) if len(x) else 1.5):.2f} cycles",
        transform=ax.transAxes,
        fontsize=8,
    )

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8)


def _clip_plot(ax, rows):
    if not rows:
        ax.set_title("Current-limited sine clipping (no data)")
        return
    t0 = rows[0]["ts"]
    t = np.array([r["ts"] - t0 for r in rows])
    v_set = np.array([r.get("v_set", 0.0) for r in rows])
    v_out = np.array([r.get("v_out", 0.0) for r in rows])
    i_out = np.array([r.get("i_out", 0.0) for r in rows])
    cv = np.array([r.get("cv_cc", "CV") for r in rows])
    prot = np.array([r.get("protect", "none") for r in rows])

    ax.plot(t, v_set, "--", linewidth=1.8, alpha=0.75, color="#4C90C0", label="V_set")
    ax.plot(t, v_out, "-", linewidth=2.2, color="#D06700", label="V_out")
    ax.scatter(t, v_out, s=12, color="#D06700", alpha=0.6, zorder=3, label="V_out samples")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Voltage (V)")
    ax.grid(True, alpha=0.28)
    ax.set_title("Sine under current limiting (clipping / CC transitions)")

    v_min = min(float(np.min(v_set)), float(np.min(v_out)))
    v_max = max(float(np.max(v_set)), float(np.max(v_out)))
    pad = max(0.25, 0.08 * (v_max - v_min))
    ax.set_ylim(v_min - pad, v_max + pad)

    ax2 = ax.twinx()
    ax2.plot(t, i_out, "-", linewidth=1.8, alpha=0.9, color="#CC2F2F", label="I_out")
    ax2.scatter(t, i_out, s=10, color="#CC2F2F", alpha=0.5, zorder=3, label="I_out samples")
    ax2.set_ylabel("Current (A)", color="#d62728")
    ax2.tick_params(axis="y", labelcolor="#d62728")

    i_min = float(np.min(i_out))
    i_max = float(np.max(i_out))
    i_pad = max(0.01, 0.12 * (i_max - i_min if i_max > i_min else 0.05))
    ax2.set_ylim(i_min - i_pad, i_max + i_pad)

    in_cc = cv == "CC"
    if np.any(in_cc):
        start = None
        for idx, is_cc in enumerate(in_cc):
            if is_cc and start is None:
                start = t[idx]
            if (not is_cc) and start is not None:
                ax.axvspan(start, t[idx], color="orange", alpha=0.15)
                start = None
        if start is not None:
            ax.axvspan(start, t[-1], color="orange", alpha=0.15)

    oc_idx = np.where(prot != "none")[0]
    if len(oc_idx) > 0:
        ax.scatter(t[oc_idx], v_out[oc_idx], color="black", s=14, label="protect != none")
    ax.text(
        0.02,
        0.92,
        f"CC samples: {int(np.sum(in_cc))} / {len(rows)} | protect events: {len(oc_idx)}",
        transform=ax.transAxes,
        fontsize=8,
    )

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8)


def _plot_series_with_cc(ax, x, y, cc_mask, base_label, base_color, cc_color):
    if len(x) == 0:
        return
    y_base = np.where(cc_mask, np.nan, y)
    y_cc = np.where(cc_mask, y, np.nan)
    ax.plot(x, y_base, "-", linewidth=2.0, color=base_color, label=base_label)
    ax.plot(x, y_cc, "-", linewidth=2.4, color=cc_color, label=f"{base_label} (CC)")


def _mark_missed_intervals(ax, x):
    if len(x) < 4:
        return 0
    dt = np.diff(x)
    med = float(np.median(dt)) if len(dt) else 0.0
    if med <= 0:
        return 0
    bad = np.where(dt > (2.2 * med))[0]
    for i in bad:
        ax.axvspan(x[i], x[i + 1], color="#b00020", alpha=0.15)
    return int(len(bad))


def _cc_demo_plot(ax, rows, title):
    if not rows:
        ax.set_title(f"{title} (no data)")
        return

    t0 = rows[0]["ts"]
    t = np.array([r["ts"] - t0 for r in rows])
    v_set = np.array([r.get("v_set", 0.0) for r in rows])
    v_out = np.array([r.get("v_out", 0.0) for r in rows])
    i_out = np.array([r.get("i_out", 0.0) for r in rows])
    cv = np.array([r.get("cv_cc", "CV") for r in rows])
    cc_mask = cv == "CC"

    missed = _mark_missed_intervals(ax, t)

    ax.plot(t, v_set, "--", linewidth=1.8, alpha=0.8, color="#4C90C0", label="V_set")
    _plot_series_with_cc(ax, t, v_out, cc_mask, "V_out", "#D06700", "#B00020")
    ax.scatter(t, v_out, s=11, color="#D06700", alpha=0.45, zorder=3, label="V_out samples")

    ax2 = ax.twinx()
    _plot_series_with_cc(ax2, t, i_out, cc_mask, "I_out", "#2D7F5E", "#B00020")
    ax2.scatter(t, i_out, s=9, color="#2D7F5E", alpha=0.45, zorder=3, label="I_out samples")

    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Voltage (V)")
    ax2.set_ylabel("Current (A)")
    ax.grid(True, alpha=0.28)

    v_min = min(float(np.min(v_set)), float(np.min(v_out)))
    v_max = max(float(np.max(v_set)), float(np.max(v_out)))
    v_pad = max(0.25, 0.08 * (v_max - v_min if v_max > v_min else 1.0))
    ax.set_ylim(v_min - v_pad, v_max + v_pad)

    i_min = float(np.min(i_out))
    i_max = float(np.max(i_out))
    i_pad = max(0.01, 0.12 * (i_max - i_min if i_max > i_min else 0.05))
    ax2.set_ylim(i_min - i_pad, i_max + i_pad)

    ax.text(
        0.02,
        0.92,
        f"CC samples: {int(np.sum(cc_mask))}/{len(rows)} | missed intervals: {missed}",
        transform=ax.transAxes,
        fontsize=8,
    )

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8)


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
