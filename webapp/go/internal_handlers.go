package main

import (
	"database/sql"
	"net/http"
	"strings"
)

type matchingChair struct {
	ID        string        `db:"id"`
	Latitude  sql.NullInt64 `db:"latitude"`
	Longitude sql.NullInt64 `db:"longitude"`
	Speed     int           `db:"speed"`
}

// このAPIをインスタンス内から一定間隔で叩かせることで、椅子とライドをマッチングさせる
func internalGetMatching(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	var rides []Ride
	if err := db.SelectContext(ctx, &rides, `SELECT * FROM rides WHERE chair_id IS NULL ORDER BY created_at LIMIT 64`); err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}
	if len(rides) == 0 {
		w.WriteHeader(http.StatusNoContent)
		return
	}

	// Fetch availability and current locations once for the entire matcher tick.
	var chairs []matchingChair
	if err := db.SelectContext(ctx, &chairs, `
SELECT c.id, l.latitude, l.longitude, COALESCE(m.speed, 1) AS speed
FROM chairs c
LEFT JOIN chair_latest_locations l ON l.chair_id = c.id
LEFT JOIN chair_models m ON m.name = c.model
WHERE c.is_active = TRUE
  AND NOT EXISTS (
    SELECT 1 FROM rides r
    JOIN ride_statuses rs ON rs.ride_id = r.id
    WHERE r.chair_id = c.id
    GROUP BY r.id
    HAVING COUNT(rs.chair_sent_at) <> 6
  )`); err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}

	var update strings.Builder
	update.WriteString("UPDATE rides SET chair_id = CASE id")
	args := make([]interface{}, 0, len(rides)*3)
	matchedIDs := make([]string, 0, len(rides))
	for _, ride := range rides {
		if len(chairs) == 0 {
			break
		}
		best := -1
		bestDistance := 0
		bestSpeed := 1
		bestHasLocation := false
		routeDistance := calculateDistance(ride.PickupLatitude, ride.PickupLongitude, ride.DestinationLatitude, ride.DestinationLongitude)
		for i, chair := range chairs {
			hasLocation := chair.Latitude.Valid && chair.Longitude.Valid
			distance := routeDistance
			if hasLocation {
				distance += calculateDistance(ride.PickupLatitude, ride.PickupLongitude, int(chair.Latitude.Int64), int(chair.Longitude.Int64))
			}
			speed := max(chair.Speed, 1)
			if best == -1 || (hasLocation && !bestHasLocation) ||
				(hasLocation == bestHasLocation && (distance*bestSpeed < bestDistance*speed ||
					(distance*bestSpeed == bestDistance*speed && chair.ID < chairs[best].ID))) {
				best = i
				bestDistance = distance
				bestSpeed = speed
				bestHasLocation = hasLocation
			}
		}
		update.WriteString(" WHEN ? THEN ?")
		args = append(args, ride.ID, chairs[best].ID)
		matchedIDs = append(matchedIDs, ride.ID)
		chairs[best] = chairs[len(chairs)-1]
		chairs = chairs[:len(chairs)-1]
	}
	if len(matchedIDs) > 0 {
		update.WriteString(" END WHERE chair_id IS NULL AND id IN (")
		for i, id := range matchedIDs {
			if i > 0 {
				update.WriteByte(',')
			}
			update.WriteByte('?')
			args = append(args, id)
		}
		update.WriteByte(')')
		if _, err := db.ExecContext(ctx, update.String(), args...); err != nil {
			writeError(w, http.StatusInternalServerError, err)
			return
		}
	}

	w.WriteHeader(http.StatusNoContent)
}
