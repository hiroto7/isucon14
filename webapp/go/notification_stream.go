package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"
)

// A buffered wakeup coalesces writes, while the DB remains the ordered durable
// queue. Subscribe before reading so a concurrent commit cannot be missed.
var notificationSubscribers = struct {
	sync.Mutex
	byKey map[string]map[chan struct{}]struct{}
}{byKey: make(map[string]map[chan struct{}]struct{})}

func subscribeNotification(key string) (<-chan struct{}, func()) {
	ch := make(chan struct{}, 1)
	notificationSubscribers.Lock()
	if notificationSubscribers.byKey[key] == nil {
		notificationSubscribers.byKey[key] = make(map[chan struct{}]struct{})
	}
	notificationSubscribers.byKey[key][ch] = struct{}{}
	notificationSubscribers.Unlock()
	return ch, func() {
		notificationSubscribers.Lock()
		defer notificationSubscribers.Unlock()
		delete(notificationSubscribers.byKey[key], ch)
		if len(notificationSubscribers.byKey[key]) == 0 {
			delete(notificationSubscribers.byKey, key)
		}
	}
}

func wakeNotification(key string) {
	notificationSubscribers.Lock()
	defer notificationSubscribers.Unlock()
	for ch := range notificationSubscribers.byKey[key] {
		select {
		case ch <- struct{}{}:
		default:
		}
	}
}

// Reuse the existing transactional response builders, including sent markers,
// rather than assembling related tables at different instants.
type notificationResponse struct {
	header http.Header
	body   bytes.Buffer
	status int
}

func (w *notificationResponse) Header() http.Header    { return w.header }
func (w *notificationResponse) WriteHeader(status int) { w.status = status }
func (w *notificationResponse) Write(p []byte) (int, error) {
	if w.status == 0 {
		w.status = http.StatusOK
	}
	return w.body.Write(p)
}

func appGetNotification(w http.ResponseWriter, r *http.Request) {
	user := r.Context().Value("user").(*User)
	streamNotifications(w, r, "app:"+user.ID, appGetNotificationJSON)
}
func chairGetNotification(w http.ResponseWriter, r *http.Request) {
	chair := r.Context().Value("chair").(*Chair)
	streamNotifications(w, r, "chair:"+chair.ID, chairGetNotificationJSON)
}

func streamNotifications(w http.ResponseWriter, r *http.Request, key string, load http.HandlerFunc) {
	wake, unsubscribe := subscribeNotification(key)
	defer unsubscribe()
	controller := http.NewResponseController(w)
	// A slow recovery check catches missed wakeups; it is not the normal delivery
	// path. Heartbeats preserve idle connections without touching the database.
	recovery := time.NewTicker(2 * time.Second)
	heartbeat := time.NewTicker(15 * time.Second)
	defer recovery.Stop()
	defer heartbeat.Stop()
	var previous []byte
	started := false
	for {
		if r.Context().Err() != nil {
			return
		}
		response := &notificationResponse{header: make(http.Header)}
		load(response, r)
		if response.status != http.StatusOK {
			if !started {
				for k, v := range response.header {
					w.Header()[k] = v
				}
				w.WriteHeader(response.status)
				_, _ = w.Write(response.body.Bytes())
			}
			return
		}
		var envelope struct {
			Data json.RawMessage `json:"data"`
		}
		if err := json.Unmarshal(response.body.Bytes(), &envelope); err != nil {
			return
		}
		data := envelope.Data
		if len(data) == 0 {
			data = json.RawMessage("null")
		}
		if !started {
			w.Header().Set("Content-Type", "text/event-stream")
			w.Header().Set("Cache-Control", "no-cache")
			w.Header().Set("X-Accel-Buffering", "no")
			started = true
		}
		if !bytes.Equal(previous, data) {
			if _, err := fmt.Fprintf(w, "data: %s\n\n", data); err != nil {
				return
			}
			if err := controller.Flush(); err != nil {
				return
			}
			previous = append(previous[:0], data...)
			// Drain every unsent transition before waiting. The next read returns either
			// the next pending state or the same latest state, which ends the drain.
			continue
		}
		select {
		case <-r.Context().Done():
			return
		case <-wake:
		case <-recovery.C:
		case <-heartbeat.C:
			if _, err := fmt.Fprint(w, ": heartbeat\n\n"); err != nil {
				return
			}
			if err := controller.Flush(); err != nil {
				return
			}
		}
	}
}
