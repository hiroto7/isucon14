#!/bin/bash
set -u
cd /home/isucon
vmstat -t 1 > /tmp/isucon14-vmstat.log &
vmstat_pid=$!
(
  while true; do
    date --iso-8601=seconds
    ps -eo comm,pcpu,rss --sort=-pcpu | head -10
    sleep 2
  done
) > /tmp/isucon14-processes.log &
process_pid=$!
trap 'kill "$vmstat_pid" "$process_pid" 2>/dev/null || true' EXIT
./bench run --addr 127.0.0.1:443 --target https://isuride.xiv.isucon.net --payment-url http://127.0.0.1:12346 --payment-bind-port 12346 -t 60
