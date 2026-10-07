package main

import "sync"

type chairNotificationStamp struct {
	epoch   uint64
	version uint64
}

type chairNotificationEntry struct {
	stamp    chairNotificationStamp
	response *chairGetNotificationResponse
}

var chairNotifications = struct {
	sync.RWMutex
	epoch     uint64
	versions  map[string]uint64
	responses map[string]chairNotificationEntry
}{
	versions:  make(map[string]uint64),
	responses: make(map[string]chairNotificationEntry),
}

func cachedChairNotification(chairID string) (*chairGetNotificationResponse, chairNotificationStamp) {
	chairNotifications.RLock()
	defer chairNotifications.RUnlock()
	stamp := chairNotificationStamp{chairNotifications.epoch, chairNotifications.versions[chairID]}
	if entry, ok := chairNotifications.responses[chairID]; ok && entry.stamp == stamp {
		return entry.response, stamp
	}
	return nil, stamp
}

func storeChairNotification(chairID string, stamp chairNotificationStamp, response *chairGetNotificationResponse) {
	chairNotifications.Lock()
	defer chairNotifications.Unlock()
	if stamp == (chairNotificationStamp{chairNotifications.epoch, chairNotifications.versions[chairID]}) {
		chairNotifications.responses[chairID] = chairNotificationEntry{stamp, response}
	}
}

func invalidateChairNotification(chairID string) {
	chairNotifications.Lock()
	chairNotifications.versions[chairID]++
	delete(chairNotifications.responses, chairID)
	chairNotifications.Unlock()
	wakeNotification("chair:" + chairID)
}

func clearChairNotifications() {
	chairNotifications.Lock()
	defer chairNotifications.Unlock()
	chairNotifications.epoch++
	chairNotifications.versions = make(map[string]uint64)
	chairNotifications.responses = make(map[string]chairNotificationEntry)
}
