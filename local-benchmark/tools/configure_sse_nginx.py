#!/usr/bin/env python3
"""Apply/restore the nginx connection capacity needed for persistent SSE streams."""
from pathlib import Path
import subprocess
import sys
original = (Path(__file__).parent / "nginx-before-sse.conf").read_text()
config = original if "--restore" in sys.argv else original.replace("worker_processes auto;", "worker_processes auto;\nworker_rlimit_nofile 65536;").replace("worker_connections 768;", "worker_connections 8192;")
code = "from pathlib import Path; Path('/etc/nginx/nginx.conf').write_text(" + repr(config) + ")"
subprocess.run(["multipass", "exec", "isucon14", "--", "sudo", "python3", "-c", code], check=True)
subprocess.run(["multipass", "exec", "isucon14", "--", "sudo", "nginx", "-t"], check=True)
subprocess.run(["multipass", "exec", "isucon14", "--", "sudo", "systemctl", "daemon-reload"], check=True)
subprocess.run(["multipass", "exec", "isucon14", "--", "sudo", "systemctl", "reload", "nginx"], check=True)
print("Restored nginx capacity" if "--restore" in sys.argv else "nginx: 8192 connections/worker, 65536 file limit")
