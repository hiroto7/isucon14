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
present = [s for s in stages if any(r["stage"] == s["id"] for r in records)]
with (ROOT / "scores.csv").open("w") as f:
    writer = csv.DictWriter(f, fieldnames=["run", "stage", "status", "score", "reported_score", "commit", "diff_sha256"])
    writer.writeheader()
    writer.writerows({key: r.get(key) for key in writer.fieldnames} for r in records)
fig, ax = plt.subplots(figsize=(11, 6), layout="constrained")
baseline = [r["score"] for r in records if r["stage"] == "baseline" and r["status"] == "passed"]
base = statistics.median(baseline) if baseline else None
max_score = max([r["score"] for r in records if r.get("score") is not None] or [1])
for x, stage in enumerate(present):
    rows = [r for r in records if r["stage"] == stage["id"]]
    scores = [r["score"] for r in rows if r["status"] == "passed"]
    color = "#2563eb" if stage["decision"] != "rejected" else "#9ca3af"
    if scores:
        median = statistics.median(scores)
        ax.errorbar(x, median, yerr=[[median-min(scores)], [max(scores)-median]], fmt="D", color=color, capsize=7, markersize=8)
        offsets = [(i - (len(scores)-1)/2)*0.06 for i in range(len(scores))]
        ax.scatter([x+d for d in offsets], scores, color=color, alpha=.65, s=28)
        ratio = f" / {median/base:.2f}x" if base and stage["id"] != "baseline" else ""
        ax.annotate(f"{median:,.0f}{ratio}", (x, max(scores)), xytext=(0, 13), textcoords="offset points", ha="center", fontsize=10)
    failures = sum(r["status"] == "failed" for r in rows)
    if failures:
        ax.text(x, .03, f"FAIL x{failures}\n(no score)", transform=ax.get_xaxis_transform(), ha="center", color="#dc2626", fontsize=9)
ax.set_xticks(range(len(present)), [s["label"] + ("\n[rejected]" if s["decision"] == "rejected" else "") for s in present])
ax.set_ylim(0, max_score*1.25)
ax.set_xlim(-.6, max(len(present)-.4, .6))
ax.set_ylabel("Official benchmark score")
ax.set_title("ISUCON14 — local score progression", loc="left", fontweight="bold")
ax.grid(axis="y", alpha=.2)
ax.spines[["top", "right"]].set_visible(False)
fig.text(.01, -.02, "ARM64 / Ubuntu 24.04 / 2 vCPU / 4 GiB / app + benchmark on one VM\nDots: individual runs. Diamond: median. Whiskers: min–max. Failed runs excluded from medians.", fontsize=9, color="#555555")
fig.savefig(ROOT / "score-history.png", dpi=180, bbox_inches="tight")
print(ROOT / "score-history.png")
