#!/usr/bin/env python3
"""Set and persist the local VM matcher's polling interval."""
import argparse
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('seconds', choices=['0.1', '0.5'])
args = parser.parse_args()

subprocess.run([
    'multipass', 'exec', 'isucon14', '--', 'sudo', 'sed', '-i',
    f's/^ISUCON_MATCHING_INTERVAL=.*/ISUCON_MATCHING_INTERVAL={args.seconds}/',
    '/home/isucon/env.sh',
], check=True)
subprocess.run([
    'multipass', 'exec', 'isucon14', '--', 'sudo', 'systemctl', 'restart', 'isuride-matcher',
], check=True)
subprocess.run([
    'multipass', 'exec', 'isucon14', '--', 'grep', '^ISUCON_MATCHING_INTERVAL=', '/home/isucon/env.sh',
], check=True)
