#!/bin/bash
# Bluetooth cleanup script - forces BlueZ to restart cleanly

echo "Cleaning up Bluetooth state..."

# Check if running as root (needed for systemctl)
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root or with sudo"
    exit 1
fi

# Stop the bridge if running
docker-compose -f /home/pi/raspinukibridge_docker/docker-compose.yml down 2>/dev/null || true

# Force kill any Bluetooth processes
systemctl stop bluetooth
killall -9 bluetoothd 2>/dev/null || true
sleep 2

# Clear BlueZ cache
rm -rf /var/lib/bluetooth/*/cache/* 2>/dev/null || true

# Restart Bluetooth cleanly
systemctl start bluetooth
sleep 3

# Verify Bluetooth is running
if systemctl is-active --quiet bluetooth; then
    echo "✅ Bluetooth cleaned and restarted successfully"

    # Start the bridge
    cd /home/pi/raspinukibridge_docker
    docker-compose up -d
    echo "✅ Bridge started"
    exit 0
else
    echo "❌ Bluetooth failed to start"
    exit 1
fi
