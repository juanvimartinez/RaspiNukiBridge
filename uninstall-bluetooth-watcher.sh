#!/bin/bash
# Uninstallation script for Nuki Bluetooth Auto-Restart

echo "Uninstalling Nuki Bluetooth Auto-Restart Service..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo"
    exit 1
fi

# Stop and disable service
echo "Stopping and disabling service..."
systemctl stop nuki-bluetooth-watcher.service 2>/dev/null
systemctl disable nuki-bluetooth-watcher.service 2>/dev/null

# Remove systemd service file
echo "Removing systemd service..."
rm -f /etc/systemd/system/nuki-bluetooth-watcher.service

# Remove watcher script
echo "Removing watcher script..."
rm -f /usr/local/bin/nuki-bluetooth-watcher.sh

# Remove trigger file if exists
echo "Removing trigger file..."
rm -f /tmp/nuki-bluetooth-restart-trigger

# Remove log file
echo "Removing log file..."
rm -f /tmp/nuki-bluetooth-restart.log

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload
systemctl reset-failed 2>/dev/null

echo ""
echo "✅ Uninstallation complete!"
echo ""
echo "The following have been removed:"
echo "  - /etc/systemd/system/nuki-bluetooth-watcher.service"
echo "  - /usr/local/bin/nuki-bluetooth-watcher.sh"
echo "  - /tmp/nuki-bluetooth-restart-trigger"
echo "  - /tmp/nuki-bluetooth-restart.log"
echo ""
echo "You may also want to:"
echo "  1. Revert docker-compose.yml changes (remove /tmp mount)"
echo "  2. Revert nuki.py changes (remove auto-restart code)"
echo "  3. Rebuild the Docker container: docker-compose build --no-cache"
echo ""
