#!/usr/bin/env bash

set -eux
cd $(dirname $0)

if [ "${ENV:-}" == "local-dev" ]; then
  exit 0
fi

if test -f /home/isucon/env.sh; then
	. /home/isucon/env.sh
fi

ISUCON_DB_HOST=${ISUCON_DB_HOST:-127.0.0.1}
ISUCON_DB_PORT=${ISUCON_DB_PORT:-3306}
ISUCON_DB_USER=${ISUCON_DB_USER:-isucon}
ISUCON_DB_PASSWORD=${ISUCON_DB_PASSWORD:-isucon}
ISUCON_DB_NAME=${ISUCON_DB_NAME:-isuride}

# MySQLを初期化
mysql -u"$ISUCON_DB_USER" \
		-p"$ISUCON_DB_PASSWORD" \
		--host "$ISUCON_DB_HOST" \
		--port "$ISUCON_DB_PORT" \
		"$ISUCON_DB_NAME" < 1-schema.sql

mysql -u"$ISUCON_DB_USER" \
		-p"$ISUCON_DB_PASSWORD" \
		--host "$ISUCON_DB_HOST" \
		--port "$ISUCON_DB_PORT" \
		"$ISUCON_DB_NAME" < 2-master-data.sql

gzip -dkc 3-initial-data.sql.gz | mysql -u"$ISUCON_DB_USER" \
		-p"$ISUCON_DB_PASSWORD" \
		--host "$ISUCON_DB_HOST" \
		--port "$ISUCON_DB_PORT" \
		"$ISUCON_DB_NAME"

mysql -u"$ISUCON_DB_USER" \
		-p"$ISUCON_DB_PASSWORD" \
		--host "$ISUCON_DB_HOST" \
		--port "$ISUCON_DB_PORT" \
		"$ISUCON_DB_NAME" <<'SQL'
INSERT INTO chair_latest_locations (chair_id, latitude, longitude, created_at)
SELECT chair_id, latitude, longitude, created_at
FROM (
  SELECT chair_id, latitude, longitude, created_at,
         ROW_NUMBER() OVER (PARTITION BY chair_id ORDER BY created_at DESC, id DESC) AS rn
  FROM chair_locations
) AS ranked
WHERE rn = 1;

UPDATE chair_latest_locations l
JOIN (
  SELECT chair_id, SUM(step_distance) AS total_distance
  FROM (
    SELECT chair_id,
           COALESCE(ABS(latitude - LAG(latitude) OVER (PARTITION BY chair_id ORDER BY created_at)) +
                    ABS(longitude - LAG(longitude) OVER (PARTITION BY chair_id ORDER BY created_at)), 0) AS step_distance
    FROM chair_locations
  ) AS steps
  GROUP BY chair_id
) AS distances ON distances.chair_id = l.chair_id
SET l.total_distance = distances.total_distance;

INSERT INTO chair_stats (chair_id, total_rides_count, total_evaluation_sum)
SELECT r.chair_id, COUNT(*), SUM(r.evaluation)
FROM rides r
WHERE r.chair_id IS NOT NULL
  AND r.evaluation IS NOT NULL
  AND EXISTS (SELECT 1 FROM ride_statuses s WHERE s.ride_id = r.id AND s.status = 'ARRIVED')
  AND EXISTS (SELECT 1 FROM ride_statuses s WHERE s.ride_id = r.id AND s.status = 'CARRYING')
  AND EXISTS (SELECT 1 FROM ride_statuses s WHERE s.ride_id = r.id AND s.status = 'COMPLETED')
GROUP BY r.chair_id;
INSERT INTO chair_open_rides (chair_id, open_rides)
SELECT r.chair_id, COUNT(*)
FROM rides r
WHERE r.chair_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM ride_statuses s WHERE s.ride_id = r.id AND s.status = 'COMPLETED')
GROUP BY r.chair_id;
SQL
