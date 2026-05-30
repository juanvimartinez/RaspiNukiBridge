#!/bin/bash
# This script is called by the container via docker exec when BlueZ is stuck
# It must be run on the HOST, not inside the container

echo "$(date +'%Y-%m-%d %H:%M:%S') - BlueZ stuck detected, forcing restart..." >> /tmp/bluez-restart.log

# Force restart Bluetooth
systemctl restart bluetooth

echo "$(date +'%Y-%m-%d %H:%M:%S') - Bluetooth restarted" >> /tmp/bluez-restart.log
