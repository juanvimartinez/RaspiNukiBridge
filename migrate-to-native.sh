#!/bin/bash
# Quick migration script - Docker to Native deployment

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  RaspiNukiBridge - Quick Docker → Native Migration       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "❌ Error: Please run with sudo"
    exit 1
fi

echo "This will:"
echo "  1. Stop and remove Docker container"
echo "  2. Uninstall Bluetooth watcher service"
echo "  3. Install native RaspiNukiBridge service"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Migration cancelled."
    exit 0
fi

echo ""
echo "Step 1/3: Stopping Docker container..."
if [ -d "$HOME/raspinukibridge_docker" ]; then
    cd "$HOME/raspinukibridge_docker"
    docker-compose down 2>/dev/null || true
    echo "✅ Docker container stopped"
else
    echo "   (Docker directory not found, skipping)"
fi
echo ""

echo "Step 2/3: Uninstalling Bluetooth watcher..."
if [ -f "/etc/systemd/system/nuki-bluetooth-watcher.service" ]; then
    systemctl stop nuki-bluetooth-watcher 2>/dev/null || true
    systemctl disable nuki-bluetooth-watcher 2>/dev/null || true
    rm -f /etc/systemd/system/nuki-bluetooth-watcher.service
    rm -f /usr/local/bin/nuki-bluetooth-watcher.sh
    systemctl daemon-reload
    echo "✅ Watcher service removed"
else
    echo "   (Watcher not found, skipping)"
fi
echo ""

echo "Step 3/3: Installing native service..."
if [ ! -f "install-native.sh" ]; then
    echo "❌ Error: install-native.sh not found"
    echo "Please run this script from the RaspiNukiBridge directory"
    exit 1
fi

./install-native.sh

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Migration Complete! 🎉                                  ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "RaspiNukiBridge is now running natively!"
echo ""
echo "View logs: sudo journalctl -u raspinukibridge -f"
echo ""
