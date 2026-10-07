#!/usr/bin/env python3
"""Plot every retained trial chronologically and the strict running-record subset."""
import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter

ROOT = Path(__file__).resolve().parents[1]


def load_trials(results_dir, stages_file):
    stages = json.loads(stages_file.read_text()) if stages_file.exists() else []
    decisions = {s['id']: s.get('decision', 'unknown') for s in stages}
    trials = []
    for path in results_dir.glob('*/result.json'):
        row = json.loads(path.read_text())
        stamp = row.get('started_at') or path.parent.name.split('-')[0]
        instant = dt.datetime.strptime(stamp, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
        score = row.get('score')
        valid = row.get('status') == 'passed' and isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score)
        if row.get('status') == 'passed' and not valid:
            raise ValueError(f'Passed trial has no finite numeric score: {path}')
        trials.append(dict(row, run=path.parent.name, instant=instant, valid=valid,
                           decision=decisions.get(row.get('stage'), 'unknown')))
    trials.sort(key=lambda r: (r['instant'], r['run']))
    if not trials:
        raise ValueError(f'No result.json records under {results_dir}')
    best = -math.inf
    for index, row in enumerate(trials, 1):
        row['trial'] = index
        row['record_high'] = row['valid'] and row['score'] > best
        if row['record_high']:
            best = row['score']
    return trials


def write_csv(path, trials):
    fields = ['trial', 'run', 'started_at', 'stage', 'decision', 'status', 'score',
              'reported_score', 'record_high', 'commit', 'diff_sha256']
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for row in trials:
            data = {key: row.get(key) for key in fields}
            # Never turn a failed/aborted benchmark's reported score into data.
            if not row['valid']:
                data['score'] = None
            writer.writerow(data)


def style(ax):
    ax.set_ylabel('Official benchmark score')
    ax.yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='y', alpha=.18)
    ax.spines[['top', 'right']].set_visible(False)


def save_all(trials, output):
    valid = [r for r in trials if r['valid']]
    failed = [r for r in trials if not r['valid']]
    maximum = max([r['score'] for r in valid] or [1])
    fig, ax = plt.subplots(figsize=(16, 6.5), layout='constrained')
    # NaN breaks the line at failed trials; these are not plotted as score zero.
    ax.plot([r['trial'] for r in trials], [r['score'] if r['valid'] else math.nan for r in trials],
            color='#93b4db', linewidth=1.2, zorder=1)
    for rejected, color, label in [(False, '#2563eb', 'Passed'), (True, '#d97706', 'Passed, rejected candidate')]:
        rows = [r for r in valid if (r['decision'] == 'rejected') == rejected]
        ax.scatter([r['trial'] for r in rows], [r['score'] for r in rows],
                   color=color, s=25, label=label, zorder=3)
    if failed:
        ax.scatter([r['trial'] for r in failed], [-maximum*.08]*len(failed),
                   marker='x', s=45, color='#dc2626', label='Failed / aborted (no score)', zorder=3)
    # Mark the start and final high without obscuring the other 100+ points.
    if valid:
        first, last = valid[0], max(valid, key=lambda r: r['score'])
        for row, offset in [(first, (12, 20)), (last, (-7, 18))]:
            ax.annotate(f"#{row['trial']}: {row['score']:,}", (row['trial'], row['score']),
                        xytext=offset, textcoords='offset points', ha='left' if row is first else 'right', fontsize=10)
    previous_day = None
    for row in trials:
        day = row['instant'].astimezone(dt.timezone(dt.timedelta(hours=9))).strftime('%Y-%m-%d')
        if day != previous_day:
            x = row['trial']-.5
            if previous_day is not None:
                ax.axvline(x, color='#64748b', alpha=.35, linestyle=':')
            ax.text(x+.5, .97, day+' JST', transform=ax.get_xaxis_transform(), fontsize=9, color='#475569', va='top')
            previous_day = day
    ax.set_xlim(.4, len(trials)+.8)
    ax.set_ylim(-maximum*.125, maximum*1.2)
    ticks = sorted({1, len(trials), *range(10, len(trials)+1, 10)})
    ax.set_xticks(ticks)
    ax.set_xlabel('Trial number in chronological order — every trial, no stage aggregation')
    ax.set_title(f'ISUCON14 — complete history: {len(trials)} trials ({len(valid)} passed, {len(failed)} failed/aborted)',
                 loc='left', fontweight='bold')
    ax.legend(loc='upper left', bbox_to_anchor=(.02, .9), frameon=False, fontsize=9)
    style(ax)
    fig.text(.01, -.035, 'All retained result.json records, from the first original-code run. ARM64 / 2 vCPU / 4 GiB / one VM. Rebuilds and configuration changes are retained; not a controlled single experiment.', fontsize=9, color='#555555')
    for extension in ['png', 'svg']:
        fig.savefig(output/f'score-all-trials.{extension}', dpi=180, bbox_inches='tight')
    plt.close(fig)


def save_records(trials, output):
    records = [r for r in trials if r['record_high']]
    if not records:
        return
    fig, ax = plt.subplots(figsize=(16, 6.5), layout='constrained')
    xs = list(range(1, len(records)+1))
    ax.plot(xs, [r['score'] for r in records], color='#2563eb', linewidth=2, marker='o', markersize=5)
    rejected = [(x, r) for x, r in zip(xs, records) if r['decision'] == 'rejected']
    if rejected:
        ax.scatter([x for x, r in rejected], [r['score'] for x, r in rejected], color='#d97706', s=36, zorder=3, label='Rejected candidate with a valid record score')
        ax.legend(loc='upper left', frameon=False, fontsize=9)
    for index, (x, row) in enumerate(zip(xs, records)):
        offset = 14 if index % 2 == 0 else -22
        ax.annotate(f"{row['score']:,}", (x, row['score']), xytext=(0, offset), textcoords='offset points', ha='center', fontsize=8)
    maximum = records[-1]['score']
    ax.set_xlim(.4, len(records)+.6)
    ax.set_ylim(-maximum*.035, maximum*1.15)
    ax.set_xticks(xs, [f"{x}\n#{r['trial']}" for x, r in zip(xs, records)], fontsize=8)
    ax.set_xlabel('Record update number / original trial number (#) — strictly increasing scores only')
    ax.set_title(f'ISUCON14 — all {len(records)} record-breaking passed trials', loc='left', fontweight='bold')
    style(ax)
    fig.text(.01, -.035, 'Included iff status=passed, numeric score, and score > every preceding valid score. Ties, decreases, failures and aborted runs are excluded. Adoption is not a filter.', fontsize=9, color='#555555')
    for extension in ['png', 'svg']:
        fig.savefig(output/f'score-record-highs.{extension}', dpi=180, bbox_inches='tight')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results-dir', type=Path, default=ROOT/'results')
    parser.add_argument('--output-dir', type=Path, default=ROOT)
    parser.add_argument('--stages-file', type=Path, default=ROOT/'stages.json')
    args = parser.parse_args()
    trials = load_trials(args.results_dir, args.stages_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir/'all-trials.csv', trials)
    write_csv(args.output_dir/'record-highs.csv', [r for r in trials if r['record_high']])
    save_all(trials, args.output_dir)
    save_records(trials, args.output_dir)
    print(f"Trials: {len(trials)}, passed: {sum(r['valid'] for r in trials)}, record highs: {sum(r['record_high'] for r in trials)}")
    print(args.output_dir/'score-all-trials.png')
    print(args.output_dir/'score-record-highs.png')


if __name__ == '__main__':
    main()
