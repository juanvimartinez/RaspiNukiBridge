#!/bin/bash
# Installation script for Nuki Bluetooth Auto-Restart

echo "Installing Nuki Bluetooth Auto-Restart Service..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo"
    exit 1
fi

# Copy watcher script
echo "Installing watcher script..."
cp nuki-bluetooth-watcher.sh /usr/local/bin/
chmod +x /usr/local/bin/nuki-bluetooth-watcher.sh

# Copy systemd service
echo "Installing systemd service..."
cp nuki-bluetooth-watcher.service /etc/systemd/system/

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

# Enable and start service
echo "Enabling and starting service..."
systemctl enable nuki-bluetooth-watcher.service
systemctl start nuki-bluetooth-watcher.service

# Check status
echo ""
echo "Installation complete! Checking status..."
systemctl status nuki-bluetooth-watcher.service --no-pager

echo ""
echo "✅ Bluetooth auto-restart is now active"
echo ""
echo "The container can now automatically restart Bluetooth when BlueZ gets stuck."
echo "Logs: /tmp/nuki-bluetooth-restart.log"
echo ""
echo "To view watcher logs: sudo journalctl -u nuki-bluetooth-watcher -f"
