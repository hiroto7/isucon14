#!/usr/bin/env python3
"""Deploy the tracked Go/SQL files, build on ARM64, and verify source hashes."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
GIT = '/Library/Developer/CommandLineTools/usr/bin/git'

def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

files = subprocess.check_output([GIT, 'ls-files', 'webapp/go', 'webapp/sql'], cwd=ROOT, text=True).splitlines()
manifest = {p.removeprefix('webapp/'): hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files}
with tempfile.TemporaryDirectory(prefix='isucon14-deploy-') as tmp:
    archive = Path(tmp) / 'source.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for file in files:
            tar.add(ROOT / file, arcname=file.removeprefix('webapp/'))
    run('multipass', 'transfer', str(archive), 'isucon14:/tmp/isucon14-source.tar.gz')
    run('multipass', 'exec', 'isucon14', '--', 'sudo', 'tar', 'xzf', '/tmp/isucon14-source.tar.gz', '-C', '/home/isucon/webapp', '--no-same-owner')
    run('multipass', 'exec', 'isucon14', '--', 'sudo', 'chown', '-R', 'isucon:isucon', '/home/isucon/webapp/go', '/home/isucon/webapp/sql')
    # A removed source file left on the VM can silently change the compiled app.
    inventory_code = 'import json; from pathlib import Path; print(json.dumps(sorted(p.name for p in Path("/home/isucon/webapp/go").glob("*.go"))))'
    remote_go_files = set(json.loads(subprocess.check_output(['multipass', 'exec', 'isucon14', '--', 'python3', '-c', inventory_code], text=True)))
    expected_go_files = {Path(p).name for p in files if p.startswith('webapp/go/') and p.endswith('.go')}
    if remote_go_files != expected_go_files:
        raise SystemExit(f'VM Go source inventory mismatch: extra={sorted(remote_go_files - expected_go_files)}, missing={sorted(expected_go_files - remote_go_files)}')
    run('multipass', 'exec', 'isucon14', '--', 'sudo', '-iu', 'isucon', 'bash', '-lc', 'cd /home/isucon/webapp/go && /home/isucon/local/golang/bin/go build -o isuride -ldflags "-s -w"')
    code = 'import hashlib,json; from pathlib import Path; root=Path("/home/isucon/webapp"); files=' + repr(list(manifest)) + '; print(json.dumps({p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files}))'
    remote = json.loads(subprocess.check_output(['multipass', 'exec', 'isucon14', '--', 'python3', '-c', code], text=True))
    if manifest != remote:
        raise SystemExit('Host/VM source hash mismatch')
    (ROOT / 'local-benchmark/deployed-source.json').write_text(json.dumps(manifest, indent=2) + '\n')
run('multipass', 'exec', 'isucon14', '--', 'sudo', 'systemctl', 'restart', 'isuride-go', 'isuride-matcher')
print(f'Deployed and verified {len(files)} Go/SQL files.')
