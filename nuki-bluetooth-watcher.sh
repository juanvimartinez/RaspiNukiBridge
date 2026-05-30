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
        log "Restart trigger detected, restarting Bluetooth..."

        # Remove trigger file
        rm -f "$TRIGGER_FILE"

        # Restart Bluetooth
        systemctl restart bluetooth

        if [ $? -eq 0 ]; then
            log "✅ Bluetooth restarted successfully"
        else
            log "❌ Bluetooth restart failed"
        fi

        # Wait a bit before checking again
        sleep 5
    fi

    # Check every 2 seconds
    sleep 2
done
