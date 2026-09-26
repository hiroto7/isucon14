#!/usr/bin/env python3
"""Run the unmodified official benchmark and keep each attempt, including failures."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "local-benchmark/results"
GIT = "/Library/Developer/CommandLineTools/usr/bin/git"
BENCH = "./bench run --addr 127.0.0.1:443 --target https://isuride.xiv.isucon.net --payment-url http://127.0.0.1:12346 --payment-bind-port 12346 -t 60"

def capture(args):
    return subprocess.check_output(args, cwd=ROOT, text=True)

def checked_multipass(args, **kwargs):
    for attempt in range(3):
        result = subprocess.run(["multipass", *args], **kwargs)
        if result.returncode == 0:
            return result
        if attempt == 2:
            raise subprocess.CalledProcessError(
                result.returncode, result.args, output=result.stdout, stderr=result.stderr,
            )
        print(f"Multipass command failed; retrying in 5s ({attempt + 1}/3)", flush=True)
        time.sleep(5)

def database_snapshot(run, label):
    query = "SHOW GLOBAL VARIABLES WHERE Variable_name IN ('innodb_buffer_pool_size','innodb_flush_log_at_trx_commit','sync_binlog');"
    result = checked_multipass(
        ["exec", "isucon14", "--", "sudo", "mysql", "--batch", "--raw", "-e", query],
        capture_output=True, text=True,
    )
    (run / f"database-variables-{label}.tsv").write_text(result.stdout)
    lines = [line.split("\t", 1) for line in result.stdout.splitlines() if "\t" in line]
    return {name: value for name, value in lines[1:]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for _ in range(args.runs):
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run = OUT / f"{stamp}-{args.stage}"
        run.mkdir()
        patch = capture([GIT, "diff", "HEAD"])
        (run / "git-diff.patch").write_text(patch)
        record = {
            "stage": args.stage, "started_at": stamp,
            "commit": capture([GIT, "rev-parse", "HEAD"]).strip(),
            "diff_sha256": hashlib.sha256(patch.encode()).hexdigest(),
            "command": BENCH, "vm": "isucon14", "cpus": 2,
            "memory_gib": 4, "cooldown_seconds": 20,
            "duration_seconds": 60, "status": "running", "score": None,
        }
        (run / "result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
        # Same restart and cooldown for every scored attempt. No database tuning here.
        try:
            checked_multipass(["exec", "isucon14", "--", "sudo", "systemctl", "restart", "isuride-go", "isuride-matcher"])
            time.sleep(20)
            checked_multipass(["exec", "isucon14", "--", "sudo", "mysql", "-e", "TRUNCATE TABLE performance_schema.events_statements_summary_by_digest"])
            checked_multipass(["exec", "isucon14", "--", "sudo", "truncate", "-s", "0", "/var/log/nginx/isucon-timing.log"])
            record["database_settings_before"] = database_snapshot(run, "before")
        except subprocess.CalledProcessError as exc:
            record.update({"status": "failed", "score": None, "reported_score": None,
                           "failure_stage": "setup", "error": str(exc)})
            if exc.stderr:
                (run / "setup-error.log").write_text(exc.stderr)
            (run / "result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
            print(f"END {run.name}: failed during setup", flush=True)
            continue
        start = time.monotonic()
        print(f"START {run.name}", flush=True)
        with (run / "benchmark.log").open("w") as log:
            proc = subprocess.run(["multipass", "exec", "isucon14", "--", "sudo", "-iu", "isucon", "bash", "/home/isucon/guest-run.sh"], stdout=log, stderr=subprocess.STDOUT)
        raw = (run / "benchmark.log").read_text()
        matches = re.findall(r'msg=結果 pass=(true|false) スコア=(-?\d+)', raw)
        passed, raw_score = matches[-1] if matches else ("false", None)
        record.update({"exit_code": proc.returncode, "elapsed_seconds": round(time.monotonic() - start, 2),
                       "status": "passed" if passed == "true" and proc.returncode == 0 else "failed",
                       "score": int(raw_score) if passed == "true" and proc.returncode == 0 else None,
                       "reported_score": int(raw_score) if raw_score is not None else None})
        record["database_settings_after"] = database_snapshot(run, "after")
        (run / "result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
        for remote, name in [("/tmp/isucon14-vmstat.log", "vmstat.log"), ("/tmp/isucon14-processes.log", "processes.log"), ("/var/log/nginx/isucon-timing.log", "http-timing.tsv")]:
            with (run / name).open("w") as f:
                checked_multipass(["exec", "isucon14", "--", "sudo", "cat", remote], stdout=f, stderr=subprocess.STDOUT)
        sql = (ROOT / "local-benchmark/tools/profile.sql").read_text()
        with (run / "sql-profile.tsv").open("w") as f:
            checked_multipass(["exec", "isucon14", "--", "sudo", "mysql", "--batch", "-e", sql], stdout=f, stderr=subprocess.STDOUT)
        with (run / "resources.txt").open("w") as f:
            checked_multipass(["exec", "isucon14", "--", "bash", "-lc", "free -m; uptime; ps -eo comm,pcpu,rss --sort=-pcpu | head -12; df -h /"], stdout=f, stderr=subprocess.STDOUT)
        print(f"END {run.name}: {record['status']} score={record['score']}", flush=True)
        if record["status"] != "passed":
            print(raw[-5000:], flush=True)

if __name__ == "__main__":
    main()
