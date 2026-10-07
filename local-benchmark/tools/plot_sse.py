#!/usr/bin/env python3
"""Plot the SSE experiments from retained official benchmark result files."""
import json
import statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
records = [json.loads(p.read_text()) for p in sorted((root/'results').glob('*/result.json'))]
groups = [
    ('sse-baseline', 'Current\nbaseline', False),
    ('notification-sse', 'SSE\ninitial attempt', True),
    ('notification-sse-capacity', 'SSE + nginx\ncapacity', False),
    ('nearby-open-rides', 'SSE + nearby\n[rejected]', True),
    ('notification-sse-repeat', 'SSE\nconfirmation', False),
    ('sse-baseline-deployment-failed', 'Old-code deploy\nfailed attempt', True),
    ('sse-baseline-capacity-check', 'Old code + nginx\ncapacity recheck', False),
    ('notification-sse-restart', 'SSE\nafter reboot', False),
    ('notification-sse-restored', 'Restored\nprevious code', False),
]
groups = [g for g in groups if any(r['stage']==g[0] for r in records)]
baseline = statistics.median(r['score'] for r in records if r['stage']=='sse-baseline' and r['status']=='passed')
fig, ax = plt.subplots(figsize=(max(7,len(groups)*1.6),5.0),layout='constrained')
for x,(sid,label,rejected) in enumerate(groups):
    rows = [r for r in records if r['stage']==sid]
    valid = [r['score'] for r in rows if r['status']=='passed' and r.get('score') is not None]
    if valid:
        median = statistics.median(valid)
        color = '#d97706' if rejected else ('#64748b' if sid.startswith('sse-baseline') else '#2563eb')
        ax.bar(x,median,color=color,alpha=.78,width=.6)
        ax.errorbar(x,median,yerr=[[median-min(valid)],[max(valid)-median]],color=color,capsize=5)
        ax.text(x,max(valid)+max(baseline*.025,1500), '\n'.join(f'{s:,}' for s in valid)+f'\n{median/baseline:.2f}× current',ha='center',fontsize=9)
    if any(r['status']=='failed' for r in rows):
        ax.text(x,baseline*.06,'FAIL\n(no valid score)',color='#dc2626',ha='center',fontsize=10)
ax.axhline(baseline,color='#64748b',linestyle='--',linewidth=1)
ax.set_xticks(range(len(groups)),[g[1] for g in groups])
ax.set_ylim(0,max([r['score'] for r in records if r['stage'] in [g[0] for g in groups] and r.get('score') is not None]+[baseline])*1.28)
ax.set_ylabel('Official benchmark score')
ax.set_title('ISUCON14 — event-driven SSE notification experiment',loc='left',fontweight='bold')
ax.grid(axis='y',alpha=.2)
ax.spines[['top','right']].set_visible(False)
fig.text(.01,-.04,'ARM64 / 2 vCPU / 4 GiB / one VM / 60-second benchmark. Failed validation is not a zero score.',fontsize=9,color='#555555')
fig.savefig(root/'score-sse.png',dpi=170,bbox_inches='tight')
print(root/'score-sse.png')
