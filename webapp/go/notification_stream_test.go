package main

import (
	"bufio"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestNotificationStreamDrainsTransitionsWakesAndReconnects(t *testing.T) {
	var mu sync.Mutex
	states := []string{"MATCHING", "ENROUTE"}
	next := 0
	load := func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		state := states[next]
		if next < len(states)-1 {
			next++
		}
		mu.Unlock()
		writeJSON(w, http.StatusOK, map[string]any{"data": map[string]string{"ride_id": "ride", "status": state}})
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		streamNotifications(w, r, "test:ordered", load)
	}))
	defer server.Close()
	connect := func() (*http.Response, context.CancelFunc) {
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		req, _ := http.NewRequestWithContext(ctx, http.MethodGet, server.URL, nil)
		res, err := server.Client().Do(req)
		if err != nil {
			cancel()
			t.Fatal(err)
		}
		if res.Header.Get("Content-Type") != "text/event-stream" {
			t.Fatal("wrong content type")
		}
		return res, cancel
	}
	read := func(scanner *bufio.Scanner, want string) {
		t.Helper()
		for scanner.Scan() {
			if !strings.HasPrefix(scanner.Text(), "data: ") {
				continue
			}
			var data struct {
				Status string `json:"status"`
			}
			if err := json.Unmarshal([]byte(strings.TrimPrefix(scanner.Text(), "data: ")), &data); err != nil {
				t.Fatal(err)
			}
			if data.Status != want {
				t.Fatalf("got %s, want %s", data.Status, want)
			}
			return
		}
		t.Fatalf("stream closed before %s: %v", want, scanner.Err())
	}
	res, cancel := connect()
	scanner := bufio.NewScanner(res.Body)
	read(scanner, "MATCHING")
	read(scanner, "ENROUTE")
	mu.Lock()
	states = append(states, "PICKUP")
	next = len(states) - 1
	mu.Unlock()
	wakeNotification("test:ordered")
	read(scanner, "PICKUP")
	cancel()
	res.Body.Close()
	// A new connection must send current state immediately even without a wake.
	res, cancel = connect()
	read(bufio.NewScanner(res.Body), "PICKUP")
	cancel()
	res.Body.Close()
}
