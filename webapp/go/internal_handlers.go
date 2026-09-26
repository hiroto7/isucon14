package main

import (
	"database/sql"
	"errors"
	"net/http"
)

// このAPIをインスタンス内から一定間隔で叩かせることで、椅子とライドをマッチングさせる
func internalGetMatching(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	// A single matcher tick can receive several pending rides. Fill currently
	// available chairs before waiting for the next scheduled tick.
	for i := 0; i < 64; i++ {
		ride := &Ride{}
		if err := db.GetContext(ctx, ride, `SELECT * FROM rides WHERE chair_id IS NULL ORDER BY created_at LIMIT 1`); err != nil {
			if errors.Is(err, sql.ErrNoRows) {
				break
			}
			writeError(w, http.StatusInternalServerError, err)
			return
		}

		matched := &Chair{}
		if err := db.GetContext(ctx, matched, `
SELECT c.* FROM chairs c
WHERE c.is_active = TRUE
  AND NOT EXISTS (
    SELECT 1 FROM rides r
    JOIN ride_statuses rs ON rs.ride_id = r.id
    WHERE r.chair_id = c.id
    GROUP BY r.id
    HAVING COUNT(rs.chair_sent_at) <> 6
  )
ORDER BY RAND() LIMIT 1`); err != nil {
			if errors.Is(err, sql.ErrNoRows) {
				break
			}
			writeError(w, http.StatusInternalServerError, err)
			return
		}

		if _, err := db.ExecContext(ctx, "UPDATE rides SET chair_id = ? WHERE id = ?", matched.ID, ride.ID); err != nil {
			writeError(w, http.StatusInternalServerError, err)
			return
		}
	}

	w.WriteHeader(http.StatusNoContent)
}
