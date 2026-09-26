package main

import (
	"database/sql"
	"net/http"
)

type matchingChair struct {
	ID        string        `db:"id"`
	Latitude  sql.NullInt64 `db:"latitude"`
	Longitude sql.NullInt64 `db:"longitude"`
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
SELECT c.id, l.latitude, l.longitude
FROM chairs c
LEFT JOIN chair_locations l ON l.id = (
  SELECT l2.id FROM chair_locations l2
  WHERE l2.chair_id = c.id
  ORDER BY l2.created_at DESC LIMIT 1
)
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

	for _, ride := range rides {
		if len(chairs) == 0 {
			break
		}
		best := -1
		bestDistance := 0
		bestHasLocation := false
		for i, chair := range chairs {
			hasLocation := chair.Latitude.Valid && chair.Longitude.Valid
			distance := 0
			if hasLocation {
				distance = calculateDistance(ride.PickupLatitude, ride.PickupLongitude, int(chair.Latitude.Int64), int(chair.Longitude.Int64))
			}
			if best == -1 || (hasLocation && !bestHasLocation) ||
				(hasLocation == bestHasLocation && (distance < bestDistance ||
					(distance == bestDistance && chair.ID < chairs[best].ID))) {
				best = i
				bestDistance = distance
				bestHasLocation = hasLocation
			}
		}
		if _, err := db.ExecContext(ctx, "UPDATE rides SET chair_id = ? WHERE id = ?", chairs[best].ID, ride.ID); err != nil {
			writeError(w, http.StatusInternalServerError, err)
			return
		}
		chairs[best] = chairs[len(chairs)-1]
		chairs = chairs[:len(chairs)-1]
	}

	w.WriteHeader(http.StatusNoContent)
}
