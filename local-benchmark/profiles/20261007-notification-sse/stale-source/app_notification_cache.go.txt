package main

import "sync"

type appNotificationStamp struct {
	epoch   uint64
	version uint64
}

type appNotificationEntry struct {
	stamp    appNotificationStamp
	response *appGetNotificationResponse
}

var appNotifications = struct {
	sync.RWMutex
	epoch     uint64
	versions  map[string]uint64
	responses map[string]appNotificationEntry
}{
	versions:  make(map[string]uint64),
	responses: make(map[string]appNotificationEntry),
}

func cachedAppNotification(userID string) (*appGetNotificationResponse, appNotificationStamp) {
	appNotifications.RLock()
	defer appNotifications.RUnlock()
	stamp := appNotificationStamp{appNotifications.epoch, appNotifications.versions[userID]}
	if entry, ok := appNotifications.responses[userID]; ok && entry.stamp == stamp {
		return entry.response, stamp
	}
	return nil, stamp
}

func storeAppNotification(userID string, stamp appNotificationStamp, response *appGetNotificationResponse) {
	appNotifications.Lock()
	defer appNotifications.Unlock()
	if stamp == (appNotificationStamp{appNotifications.epoch, appNotifications.versions[userID]}) {
		appNotifications.responses[userID] = appNotificationEntry{stamp, response}
	}
}

func invalidateAppNotification(userID string) {
	appNotifications.Lock()
	defer appNotifications.Unlock()
	appNotifications.versions[userID]++
	delete(appNotifications.responses, userID)
}

// A new evaluation changes the chair statistics included in responses for
// users other than the one who submitted it.
func clearAppNotifications() {
	appNotifications.Lock()
	defer appNotifications.Unlock()
	appNotifications.epoch++
	appNotifications.versions = make(map[string]uint64)
	appNotifications.responses = make(map[string]appNotificationEntry)
}
