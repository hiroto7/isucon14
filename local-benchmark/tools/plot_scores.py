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

fig, ax = plt.subplots(figsize=(max(12, 1.8 * len(present)), 6.5), layout="constrained")
reference_stage = "rebuilt-baseline" if any(r["stage"] == "rebuilt-baseline" and r["status"] == "passed" for r in records) else "baseline"
baseline = [r["score"] for r in records if r["stage"] == reference_stage and r["status"] == "passed"]
base = statistics.median(baseline) if baseline else None
max_score = max([r["score"] for r in records if r.get("score") is not None] or [1])
for x, stage in enumerate(present):
    rows = [r for r in records if r["stage"] == stage["id"]]
    scores = [r["score"] for r in rows if r["status"] == "passed" and r.get("score") is not None]
    color = "#9ca3af" if stage["decision"] == "rejected" else "#d97706" if stage["decision"] == "diagnostic" else "#2563eb"
    if scores:
        median = statistics.median(scores)
        ax.errorbar(x, median, yerr=[[median - min(scores)], [max(scores) - median]], fmt="D", color=color, capsize=7, markersize=8, zorder=3)
        offsets = [(i - (len(scores) - 1) / 2) * 0.07 for i in range(len(scores))]
        for index, (offset, score) in enumerate(zip(offsets, scores)):
            ax.scatter(x + offset, score, color=color, alpha=.75, s=30, zorder=4)
            vertical = [15, -22, 43][index % 3]
            ax.annotate(f"{score:,}", (x + offset, score), xytext=(0, vertical), textcoords="offset points", ha="center", fontsize=8, color="#333333")
        base_ratio = f" ({median / base:.0%})" if base else ""
        ax.annotate(
            f"median {median:,.0f}{base_ratio}\n{min(scores):,}–{max(scores):,}",
            (x, .10), xycoords=ax.get_xaxis_transform(), ha="center", va="center", fontsize=9,
            bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "#d1d5db", "alpha": .9},
        )
    failures = sum(r["status"] == "failed" for r in rows)
    if failures:
        ax.annotate(f"FAIL x{failures} (no score)", (x, 0), xycoords=ax.get_xaxis_transform(),
                    xytext=(0, -36), textcoords="offset points", ha="center",
                    color="#dc2626", fontsize=9, annotation_clip=False)

ax.set_xticks(range(len(present)), [stage["label"] + ("\n[rejected]" if stage["decision"] == "rejected" else "\n[profile overhead]" if stage["decision"] == "diagnostic" else "") for stage in present])
ax.set_ylim(0, max_score * 1.3)
ax.set_xlim(-.6, max(len(present) - .4, .6))
ax.set_ylabel("Official benchmark score")
ax.set_title("ISUCON14 — local score progression", loc="left", fontweight="bold")
ax.grid(axis="y", alpha=.2)
ax.spines[["top", "right"]].set_visible(False)
fig.text(.01, -.10, "ARM64 / Ubuntu 24.04 / 2 vCPU / 4 GiB / app + benchmark on one VM\nDots: individual scores. Diamond: median. Box: median, baseline ratio and min–max. Whiskers: min–max. Failed runs shown below the axis without a numeric score.", fontsize=9, color="#555555")
fig.savefig(ROOT / "score-history.png", dpi=180, bbox_inches="tight")
print(ROOT / "score-history.png")

# A compact view for reading the major accepted milestones in a chat or report.
focus_ids = [
    "rebuilt-baseline", "ride-status-index", "rides-user-index",
    "matching-batch-pool-cap", "nearest-batch-prefetch",
    "matching-batch-update", "materialized-chair-stats",
    "read-only-rollback-highload", "ride-fare-cache", "final-restart-stable", "final-restored", "final-adopted-check",
]
focus_labels = [
    "Rebuilt\nbaseline", "Status\nindex", "Ride\nindex",
    "Batch\nmatching", "Nearest\nmatching", "Batch\nupdates",
    "Chair\nstats", "Read-only\nrollback", "Best\naccepted", "After\nrestart", "MySQL\nrestored", "Final\nadopted",
]
fig2, ax2 = plt.subplots(figsize=(13, 5.5), layout="constrained")
for x, (stage_id, label) in enumerate(zip(focus_ids, focus_labels)):
    rows = [r for r in records if r["stage"] == stage_id]
    scores = [r["score"] for r in rows if r["status"] == "passed" and r.get("score") is not None]
    if not scores:
        continue
    median = statistics.median(scores)
    color = "#d97706" if stage_id in {"final-restart-stable", "final-restored", "final-adopted-check"} else "#2563eb"
    ax2.errorbar(x, median, yerr=[[median-min(scores)], [max(scores)-median]], fmt="o", color=color, capsize=5, markersize=7, zorder=3)
    for score in scores:
        ax2.scatter(x, score, color=color, alpha=.5, s=28, zorder=3)
    ax2.annotate(f"{median:,.0f}\n{median/base:.1f}x", (x, median), xytext=(0, 12), textcoords="offset points", ha="center", fontsize=9)
ax2.plot(range(len(focus_ids)), [statistics.median([r["score"] for r in records if r["stage"] == sid and r["status"] == "passed" and r.get("score") is not None]) for sid in focus_ids], color="#93c5fd", linewidth=2, zorder=1)
ax2.text(.99, .04, "Immediate restart attempt: FAILED (no score)", transform=ax2.transAxes,
         ha="right", va="bottom", color="#dc2626", fontsize=9,
         bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#dc2626"})
ax2.set_xticks(range(len(focus_ids)), focus_labels)
ax2.set_ylim(-2000, 80000)
ax2.set_ylabel("Official benchmark score")
ax2.set_title("ISUCON14 local score — major milestones", loc="left", fontweight="bold")
ax2.grid(axis="y", alpha=.2)
ax2.spines[["top", "right"]].set_visible(False)
fig2.text(.01, -.04, "ARM64 / 2 vCPU / 4 GiB / single VM. Points: valid runs; labels: median and ratio to rebuilt baseline. All trials, including rejected candidates, are in score-history.png.", fontsize=9, color="#555555")
fig2.savefig(ROOT / "score-focus.png", dpi=160, bbox_inches="tight")
print(ROOT / "score-focus.png")

# Compact comparison of the scoring-manual follow-up. Failed validation is
# deliberately drawn as FAIL rather than a zero score.
review_ids = [
    "rebuilt-baseline", "final-restored", "manual-score-review",
    "notification-read-autocommit", "chair-notification-autocommit",
    "coordinate-batch-10ms", "coordinate-async-50ms",
    "manual-review-restored",
]
review_labels = [
    "Initial\nbaseline", "Best adopted\nbefore review", "Review\nbaseline",
    "Both\nnotifications", "Chair\nnotification", "Sync\ncoordinate", "Async\ncoordinate",
    "Restored\ncode",
]
fig3, ax3 = plt.subplots(figsize=(12, 5.4), layout="constrained")
for x, (stage_id, label) in enumerate(zip(review_ids, review_labels)):
    rows = [r for r in records if r["stage"] == stage_id]
    scores = [r["score"] for r in rows if r["status"] == "passed" and r.get("score") is not None]
    rejected = stage_id in {"notification-read-autocommit", "chair-notification-autocommit", "coordinate-batch-10ms", "coordinate-async-50ms"}
    if scores:
        score = statistics.median(scores)
        color = "#d97706" if rejected else "#2563eb"
        ax3.bar(x, score, color=color, width=.65, alpha=.78)
        ax3.text(x, score + 1400, f"{score:,.0f}", ha="center", fontsize=9, fontweight="bold")
    if any(r["status"] == "failed" for r in rows):
        ax3.text(x, 2000, "FAIL\n(no score)", ha="center", va="bottom", color="#dc2626", fontsize=10, fontweight="bold")
    if rejected:
        review_labels[x] += "\n[rejected]"
ax3.axhline(70028, color="#64748b", linestyle="--", linewidth=1, label="Best adopted: 70,028")
ax3.set_xticks(range(len(review_ids)), review_labels)
ax3.set_ylim(0, 81000)
ax3.set_ylabel("Official benchmark score")
ax3.set_title("ISUCON14 — scoring manual follow-up", loc="left", fontweight="bold")
ax3.grid(axis="y", alpha=.2)
ax3.legend(loc="upper right", frameon=False)
ax3.spines[["top", "right"]].set_visible(False)
fig3.text(.01, -.04, "ARM64 / 2 vCPU / 4 GiB / one VM. Orange: rejected candidate. FAIL has no numeric score. All runs and logs are retained under results/.", fontsize=9, color="#555555")
fig3.savefig(ROOT / "score-manual-review.png", dpi=170, bbox_inches="tight")
print(ROOT / "score-manual-review.png")

# Follow-up after reading the official problem commentary. Keep the repeat
# measurements visible inside each stage instead of hiding their variation.
followup_groups = [
    ("Rebuilt\nbaseline", ["rebuilt-baseline"], "#64748b"),
    ("Prior best\nadopted", ["final-restored"], "#64748b"),
    ("Owner distance\nmaterialized", ["materialized-distance", "materialized-distance-repeat"], "#2563eb"),
    ("Regional\nmatching", ["regional-matching", "regional-matching-repeat"], "#2563eb"),
    ("Chair notification\ncache", ["chair-notification-cache", "chair-notification-cache-repeat"], "#2563eb"),
    ("App notification\ncache [rejected]", ["app-notification-cache"], "#d97706"),
    ("After restart\nadopted", ["article-followup-restored"], "#2563eb"),
]
fig4, ax4 = plt.subplots(figsize=(12, 5.5), layout="constrained")
for x, (label, ids, color) in enumerate(followup_groups):
    scores = [r["score"] for r in records if r["stage"] in ids and r["status"] == "passed" and r.get("score") is not None]
    if not scores:
        continue
    median = statistics.median(scores)
    ax4.errorbar(x, median, yerr=[[median - min(scores)], [max(scores) - median]], fmt="D", color=color, capsize=6, markersize=8, zorder=3)
    for index, score in enumerate(scores):
        offset = (index - (len(scores) - 1) / 2) * (.24 if x == 0 else .12)
        ax4.scatter(x + offset, score, color=color, alpha=.65, s=38, zorder=4)
        label_offset = (-20 if index == 1 else 12) if x == 0 else (12 if index % 2 == 0 else -18)
        ax4.annotate(f"{score:,}", (x + offset, score), xytext=(0, label_offset), textcoords="offset points", ha="center", fontsize=8)
    ax4.text(x, 15000, f"median {median:,.0f}\n{median/base:.1f}× initial", ha="center", va="center", fontsize=8,
             bbox={"boxstyle": "round,pad=.25", "facecolor": "white", "edgecolor": "#cbd5e1"})
ax4.set_xticks(range(len(followup_groups)), [g[0] for g in followup_groups])
ax4.tick_params(axis="x", pad=18)
ax4.set_ylim(0, 106000)
ax4.set_xlim(-.5, len(followup_groups) - .5)
ax4.set_ylabel("Official benchmark score")
ax4.set_title("ISUCON14 — follow-up to the official commentary", loc="left", fontweight="bold")
ax4.grid(axis="y", alpha=.2)
ax4.spines[["top", "right"]].set_visible(False)
fig4.text(.01, -.04, "ARM64 / 2 vCPU / 4 GiB / app and benchmark on one VM. Dots: individual valid runs; diamond and whiskers: median and range. Orange: rejected candidate.", fontsize=9, color="#555555")
fig4.savefig(ROOT / "score-article-followup.png", dpi=170, bbox_inches="tight")
print(ROOT / "score-article-followup.png")
