#!/bin/bash
# This script allows the container to restart Bluetooth via a watched file
# Place at: /usr/local/bin/nuki-bluetooth-watcher.sh

TRIGGER_FILE="/tmp/nuki-bluetooth-restart-trigger"
LOG_FILE="/tmp/nuki-bluetooth-restart.log"

log() {
    echo "$(date +'%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "Bluetooth watcher started"

while true; do
    if [ -f "$TRIGGER_FILE" ]; then
        log "Restart trigger detected, performing aggressive Bluetooth restart..."

        # Remove trigger file immediately
        rm -f "$TRIGGER_FILE"

        # AGGRESSIVE RESTART: Kill everything Bluetooth-related
        systemctl stop bluetooth
        sleep 1

        # Kill any remaining bluetoothd processes
        killall -9 bluetoothd 2>/dev/null || true
        sleep 1

        # Clear any D-Bus state
        rm -rf /var/run/bluez/* 2>/dev/null || true

        # Restart Bluetooth service
        systemctl start bluetooth

        if [ $? -eq 0 ]; then
            log "✅ Bluetooth restarted successfully (aggressive mode)"
            # Wait for BlueZ to fully initialize
            sleep 3
            log "BlueZ settling period complete"
        else
            log "❌ Bluetooth restart failed"
        fi

        # Wait a bit before checking again
        sleep 5
    fi

    # Check every 2 seconds
    sleep 2
done
