#!/usr/bin/env bash
set -euo pipefail
case "${1:?usage: set_nginx_log_buffer.sh on|off}" in
  on)
    multipass exec isucon14 -- sudo sed -i 's|access_log /var/log/nginx/access.log;|access_log /var/log/nginx/access.log combined buffer=64k flush=1s;|' /etc/nginx/nginx.conf
    multipass exec isucon14 -- sudo sed -i 's|access_log /var/log/nginx/isucon-timing.log isucon_timing;|access_log /var/log/nginx/isucon-timing.log isucon_timing buffer=64k flush=1s;|' /etc/nginx/conf.d/diagnostics.conf
    ;;
  off)
    multipass exec isucon14 -- sudo sed -i 's|access_log /var/log/nginx/access.log combined buffer=64k flush=1s;|access_log /var/log/nginx/access.log;|' /etc/nginx/nginx.conf
    multipass exec isucon14 -- sudo sed -i 's|access_log /var/log/nginx/isucon-timing.log isucon_timing buffer=64k flush=1s;|access_log /var/log/nginx/isucon-timing.log isucon_timing;|' /etc/nginx/conf.d/diagnostics.conf
    ;;
  *) echo 'usage: set_nginx_log_buffer.sh on|off' >&2; exit 2 ;;
esac
multipass exec isucon14 -- sudo nginx -t
multipass exec isucon14 -- sudo systemctl reload nginx
