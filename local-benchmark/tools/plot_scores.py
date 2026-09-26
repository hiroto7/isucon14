#!/usr/bin/env python3
"""Regenerate the PNG and CSV from retained result.json records."""
import csv
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
records = [json.loads(p.read_text()) | {"run": p.parent.name} for p in sorted((ROOT / "results").glob("*/result.json"))]
stages = json.loads((ROOT / "stages.json").read_text())
present = [stage for stage in stages if any(r["stage"] == stage["id"] for r in records)]
with (ROOT / "scores.csv").open("w") as f:
    fields = ["run", "stage", "status", "score", "reported_score", "commit", "diff_sha256"]
    writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows({key: r.get(key) for key in fields} for r in records)

fig, ax = plt.subplots(figsize=(12, 6.5), layout="constrained")
reference_stage = "rebuilt-baseline" if any(r["stage"] == "rebuilt-baseline" and r["status"] == "passed" for r in records) else "baseline"
baseline = [r["score"] for r in records if r["stage"] == reference_stage and r["status"] == "passed"]
base = statistics.median(baseline) if baseline else None
max_score = max([r["score"] for r in records if r.get("score") is not None] or [1])
for x, stage in enumerate(present):
    rows = [r for r in records if r["stage"] == stage["id"]]
    scores = [r["score"] for r in rows if r["status"] == "passed" and r.get("score") is not None]
    color = "#2563eb" if stage["decision"] != "rejected" else "#9ca3af"
    if scores:
        median = statistics.median(scores)
        ax.errorbar(x, median, yerr=[[median - min(scores)], [max(scores) - median]], fmt="D", color=color, capsize=7, markersize=8, zorder=3)
        offsets = [(i - (len(scores) - 1) / 2) * 0.07 for i in range(len(scores))]
        for index, (offset, score) in enumerate(zip(offsets, scores)):
            ax.scatter(x + offset, score, color=color, alpha=.75, s=30, zorder=4)
            ratio = f" ({score / base:.0%})" if base else ""
            vertical = 12 if index % 2 == 0 else -18
            horizontal = (index - (len(scores) - 1) / 2) * 10
            align = "right" if index < (len(scores) - 1) / 2 else "left" if index > (len(scores) - 1) / 2 else "center"
            ax.annotate(f"{score:,}{ratio}", (x + offset, score), xytext=(horizontal, vertical), textcoords="offset points", ha=align, fontsize=8, color="#333333")
        base_ratio = f" ({median / base:.0%})" if base else ""
        ax.annotate(
            f"median {median:,.0f}{base_ratio}\n{min(scores):,}–{max(scores):,}",
            (x, median), xytext=(0, -58), textcoords="offset points", ha="center", va="top", fontsize=9,
            bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "#d1d5db", "alpha": .9},
        )
    failures = sum(r["status"] == "failed" for r in rows)
    if failures:
        ax.annotate(f"FAIL x{failures} (no score)", (x, 0), xycoords=ax.get_xaxis_transform(),
                    xytext=(0, -36), textcoords="offset points", ha="center",
                    color="#dc2626", fontsize=9, annotation_clip=False)

ax.set_xticks(range(len(present)), [stage["label"] + ("\n[rejected]" if stage["decision"] == "rejected" else "") for stage in present])
ax.set_ylim(0, max_score * 1.3)
ax.set_xlim(-.6, max(len(present) - .4, .6))
ax.set_ylabel("Official benchmark score")
ax.set_title("ISUCON14 — local score progression", loc="left", fontweight="bold")
ax.grid(axis="y", alpha=.2)
ax.spines[["top", "right"]].set_visible(False)
fig.text(.01, -.10, "ARM64 / Ubuntu 24.04 / 2 vCPU / 4 GiB / app + benchmark on one VM\nDots: individual scores and baseline ratio. Diamond: median. Whiskers and labels: min–max. Failed runs shown below the axis without a numeric score.", fontsize=9, color="#555555")
fig.savefig(ROOT / "score-history.png", dpi=180, bbox_inches="tight")
print(ROOT / "score-history.png")
