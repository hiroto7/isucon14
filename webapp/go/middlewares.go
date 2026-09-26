package main

import (
	"context"
	"database/sql"
	"errors"
	"net/http"
	"sync"
)

// Access tokens are immutable after registration. Cache successful lookups so
// frequent notification polls do not query MySQL for the same session.
var userSessions sync.Map
var ownerSessions sync.Map
var chairSessions sync.Map
var chairNotificationUsers sync.Map

func appAuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()
		c, err := r.Cookie("app_session")
		if errors.Is(err, http.ErrNoCookie) || c.Value == "" {
			writeError(w, http.StatusUnauthorized, errors.New("app_session cookie is required"))
			return
		}
		accessToken := c.Value
		cached, ok := userSessions.Load(accessToken)
		if !ok {
			user := &User{}
			err = db.GetContext(ctx, user, "SELECT * FROM users WHERE access_token = ?", accessToken)
			if err != nil {
				if errors.Is(err, sql.ErrNoRows) {
					writeError(w, http.StatusUnauthorized, errors.New("invalid access token"))
					return
				}
				writeError(w, http.StatusInternalServerError, err)
				return
			}
			cached, _ = userSessions.LoadOrStore(accessToken, user)
			chairNotificationUsers.LoadOrStore(user.ID, simpleUser{
				ID: user.ID, Name: user.Firstname + " " + user.Lastname,
			})
		}

		ctx = context.WithValue(ctx, "user", cached.(*User))
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func ownerAuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()
		c, err := r.Cookie("owner_session")
		if errors.Is(err, http.ErrNoCookie) || c.Value == "" {
			writeError(w, http.StatusUnauthorized, errors.New("owner_session cookie is required"))
			return
		}
		accessToken := c.Value
		cached, ok := ownerSessions.Load(accessToken)
		if !ok {
			owner := &Owner{}
			if err := db.GetContext(ctx, owner, "SELECT * FROM owners WHERE access_token = ?", accessToken); err != nil {
				if errors.Is(err, sql.ErrNoRows) {
					writeError(w, http.StatusUnauthorized, errors.New("invalid access token"))
					return
				}
				writeError(w, http.StatusInternalServerError, err)
				return
			}
			cached, _ = ownerSessions.LoadOrStore(accessToken, owner)
		}

		ctx = context.WithValue(ctx, "owner", cached.(*Owner))
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func chairAuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()
		c, err := r.Cookie("chair_session")
		if errors.Is(err, http.ErrNoCookie) || c.Value == "" {
			writeError(w, http.StatusUnauthorized, errors.New("chair_session cookie is required"))
			return
		}
		accessToken := c.Value
		cached, ok := chairSessions.Load(accessToken)
		if !ok {
			chair := &Chair{}
			err = db.GetContext(ctx, chair, "SELECT * FROM chairs WHERE access_token = ?", accessToken)
			if err != nil {
				if errors.Is(err, sql.ErrNoRows) {
					writeError(w, http.StatusUnauthorized, errors.New("invalid access token"))
					return
				}
				writeError(w, http.StatusInternalServerError, err)
				return
			}
			cached, _ = chairSessions.LoadOrStore(accessToken, chair)
		}

		ctx = context.WithValue(ctx, "chair", cached.(*Chair))
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}
