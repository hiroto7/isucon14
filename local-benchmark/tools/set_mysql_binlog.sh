#!/usr/bin/env bash
set -euo pipefail

mode="${1:?usage: set_mysql_binlog.sh on|off}"
case "$mode" in
  off)
    multipass exec isucon14 -- sudo sh -c 'printf "[mysqld]\nskip-log-bin\n" > /etc/mysql/mysql.conf.d/99-isucon14-local-binlog.cnf'
    ;;
  on)
    multipass exec isucon14 -- sudo rm -f /etc/mysql/mysql.conf.d/99-isucon14-local-binlog.cnf
    ;;
  *)
    echo 'usage: set_mysql_binlog.sh on|off' >&2
    exit 2
    ;;
esac
multipass exec isucon14 -- sudo systemctl restart --no-block mysql
for attempt in $(seq 1 60); do
  if multipass exec isucon14 -- sudo mysqladmin ping --silent >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
multipass exec isucon14 -- sudo mysql -N -e "SHOW GLOBAL VARIABLES WHERE Variable_name IN ('log_bin','sync_binlog','innodb_flush_log_at_trx_commit','slow_query_log','long_query_time')"
