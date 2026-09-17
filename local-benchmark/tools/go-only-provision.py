#!/usr/bin/env python3
"""Limit the upstream provisioning checkout to the selected Go implementation."""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]) / 'provisioning/ansible'
base = root / 'application-base.yml'
base.write_text(base.read_text().replace('    - xbuildwebapp\n', ''))
tasks = root / 'roles/webapp/tasks/main.yaml'
s = tasks.read_text()
for lang in ('node', 'perl', 'php', 'python', 'ruby', 'rust'):
    s = re.sub(r'\n- name: Tasks for isuride-' + lang + r'\n  include_tasks: ' + lang + r'\.yaml\n', '\n', s)
tasks.write_text(s)
print('Provisioning limited to Go, matcher, payment mock; application source unchanged.')
