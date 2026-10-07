package main

import (
	"context"
	"log/slog"
	"strings"
	"time"
)

type coordinateWrite struct {
	id, chairID         string
	latitude, longitude int
	recordedAt          time.Time
}

// Coordinate positions and owner travel distance may lag by up to three seconds.
// Flush in much smaller windows and retry failed writes before accepting more.
var coordinateWrites = make(chan coordinateWrite, 1024)

func startCoordinateWriter() {
	go func() {
		for first := range coordinateWrites {
			batch := []coordinateWrite{first}
			timer := time.NewTimer(50 * time.Millisecond)
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
			for {
				if err := flushCoordinates(batch); err != nil {
					slog.Error("coordinate batch failed; retrying", "error", err)
					time.Sleep(100 * time.Millisecond)
					continue
				}
				break
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
