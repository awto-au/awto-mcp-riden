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


def _period_plot(ax, rows, label):
    if not rows:
        ax.set_title(f"{label} (no data)")
        return
    # Use explicit captured phase if available; fallback to normalized elapsed.
    if "phase" in rows[0]:
        phase = np.array([r["phase"] for r in rows])
    else:
        t = np.array([r["ts"] for r in rows])
        dt = t - t.min()
        duration = dt.max() if dt.max() > 0 else 1.0
        phase = (dt / duration) % 1.0

    order = np.argsort(phase)
    x = phase[order]
    v_set = np.array([r.get("v_set", 0.0) for r in rows])[order]
    v_out = np.array([r.get("v_out", 0.0) for r in rows])[order]
    i_out = np.array([r.get("i_out", 0.0) for r in rows])[order]

    ax.plot(x, v_set, "--", linewidth=1.0, alpha=0.6, label="V_set")
    ax.plot(x, v_out, "-", linewidth=1.4, label="V_out")
    ax.set_xlim(0, 1)
    ax.set_xlabel("Phase (0..1, one period)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title(label)
    ax.grid(True, alpha=0.25)

    ax2 = ax.twinx()
    ax2.plot(x, i_out, "-", linewidth=1.0, alpha=0.85, color="#d62728", label="I_out")
    ax2.set_ylabel("Current (A)", color="#d62728")
    ax2.tick_params(axis="y", labelcolor="#d62728")

    overshoot = float(np.max(v_out - v_set)) if len(v_out) else 0.0
    ax.text(0.02, 0.92, f"max overshoot: {overshoot:.3f} V", transform=ax.transAxes, fontsize=8)

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

    ax.plot(t, v_set, "--", linewidth=1.0, alpha=0.6, label="V_set")
    ax.plot(t, v_out, "-", linewidth=1.4, label="V_out")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Voltage (V)")
    ax.grid(True, alpha=0.25)
    ax.set_title("Sine under current limiting (clipping / CC transitions)")

    ax2 = ax.twinx()
    ax2.plot(t, i_out, "-", linewidth=1.0, alpha=0.85, color="#d62728", label="I_out")
    ax2.set_ylabel("Current (A)", color="#d62728")
    ax2.tick_params(axis="y", labelcolor="#d62728")

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


def main() -> int:
    in_dir = Path("docs")

    period_sets = [
        (in_dir / "mr11_sine_period.jsonl", "Sine (period-wide)"),
        (in_dir / "mr11_sawtooth_period.jsonl", "Sawtooth (period-wide)"),
        (in_dir / "mr11_triangle_period.jsonl", "Triangle (period-wide)"),
        (in_dir / "mr11_square_period.jsonl", "Square on/off (period-wide)"),
    ]

    fig, axes = plt.subplots(4, 1, figsize=(13, 14), tight_layout=True)
    fig.suptitle(
        "MR11 waveform tracking — one-period view (same settings, overshoot visible)",
        fontsize=12,
        fontweight="bold",
    )
    for ax, (path, label) in zip(axes, period_sets):
        _period_plot(ax, load(path), label)
    out_period = in_dir / "mr11_period_wide.png"
    plt.savefig(out_period, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_period}")

    clip_rows = load(in_dir / "mr11_sine_clipped_current_limit.jsonl")
    fig, ax = plt.subplots(1, 1, figsize=(13, 5.6), tight_layout=True)
    _clip_plot(ax, clip_rows)
    out_clip = in_dir / "mr11_current_limit_clip.png"
    plt.savefig(out_clip, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_clip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
