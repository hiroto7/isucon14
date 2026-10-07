#!/usr/bin/env python3
"""Aggregate MySQL FILE slow log by a lightweight normalized SQL fingerprint."""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
import re

parser = argparse.ArgumentParser()
parser.add_argument('slow_log', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
text = args.slow_log.read_text(errors='replace')
groups = defaultdict(lambda: [0, 0.0, 0, 0.0])
for block in re.split(r'(?=^# Time:)', text, flags=re.MULTILINE):
    match = re.search(r'^# Query_time: ([0-9.]+).*Rows_examined: (\d+)', block, re.MULTILINE)
    if not match or 'SET timestamp=' not in block:
        continue
    query = block.split('SET timestamp=', 1)[1].split(';\n', 1)[-1].strip()
    if query.startswith('use '):
        query = query.split(';\n', 1)[-1].strip()
    query = re.sub(r"'[^']*'", '?', query)
    query = re.sub(r'\b\d+\b', '?', query)
    query = re.sub(r'\s+', ' ', query).strip()[:180]
    if not query:
        continue
    value = groups[query]
    duration = float(match.group(1))
    value[0] += 1
    value[1] += duration
    value[2] += int(match.group(2))
    value[3] = max(value[3], duration)
with args.output.open('w', newline='') as file:
    writer = csv.writer(file, delimiter='\t')
    writer.writerow(['count', 'total_seconds', 'average_ms', 'rows_examined', 'max_ms', 'query'])
    for query, value in sorted(groups.items(), key=lambda item: item[1][1], reverse=True):
        count, total, rows, maximum = value
        writer.writerow([count, f'{total:.3f}', f'{total/count*1000:.2f}', rows, f'{maximum*1000:.2f}', query])
