package main

import (
	"context"
	"strings"
	"time"
)

type coordinateWrite struct {
	id, chairID         string
	latitude, longitude int
	recordedAt          time.Time
	done                chan error
}

// Coordinate writes are durable before the request succeeds. Grouping writes
// from different chairs reduces commit pressure without changing API timing.
var coordinateWrites = make(chan coordinateWrite, 1024)

func startCoordinateWriter() {
	go func() {
		for first := range coordinateWrites {
			batch := []coordinateWrite{first}
			timer := time.NewTimer(10 * time.Millisecond)
		collect:
			for len(batch) < 64 {
				select {
				case next := <-coordinateWrites:
					batch = append(batch, next)
				case <-timer.C:
					break collect
				}
			}
			if !timer.Stop() {
				select {
				case <-timer.C:
				default:
				}
			}
			err := flushCoordinates(batch)
			for _, write := range batch {
				write.done <- err
			}
		}
	}()
}

func flushCoordinates(batch []coordinateWrite) error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	var history, latest strings.Builder
	history.WriteString("INSERT INTO chair_locations (id, chair_id, latitude, longitude, created_at) VALUES ")
	latest.WriteString("INSERT INTO chair_latest_locations (chair_id, latitude, longitude, created_at) VALUES ")
	historyArgs := make([]any, 0, len(batch)*5)
	latestArgs := make([]any, 0, len(batch)*4)
	for i, write := range batch {
		if i > 0 {
			history.WriteByte(',')
			latest.WriteByte(',')
		}
		history.WriteString("(?, ?, ?, ?, ?)")
		latest.WriteString("(?, ?, ?, ?)")
		historyArgs = append(historyArgs, write.id, write.chairID, write.latitude, write.longitude, write.recordedAt)
		latestArgs = append(latestArgs, write.chairID, write.latitude, write.longitude, write.recordedAt)
	}
	latest.WriteString(` ON DUPLICATE KEY UPDATE
  latitude = IF(VALUES(created_at) >= created_at, VALUES(latitude), latitude),
  longitude = IF(VALUES(created_at) >= created_at, VALUES(longitude), longitude),
  created_at = GREATEST(created_at, VALUES(created_at))`)
	if _, err := tx.ExecContext(ctx, history.String(), historyArgs...); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, latest.String(), latestArgs...); err != nil {
		return err
	}
	return tx.Commit()
}
