#!/bin/bash
# One-command installer for complete Nuki Auto-Recovery System

set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Nuki Auto-Recovery System - Complete Installer          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if running from correct directory
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: Please run this script from the raspinukibridge_docker directory"
    exit 1
fi

# Check if running as root (needed for systemd)
if [ "$EUID" -ne 0 ]; then
    echo "This script needs sudo privileges for systemd installation."
    echo "Please run: sudo $0"
    exit 1
fi

echo "Step 1/4: Making scripts executable..."
chmod +x install-bluetooth-watcher.sh
chmod +x uninstall-bluetooth-watcher.sh
chmod +x nuki-bluetooth-watcher.sh
echo "✅ Scripts are executable"
echo ""

echo "Step 2/4: Installing watcher service..."
./install-bluetooth-watcher.sh
echo ""

echo "Step 3/4: Stopping current container..."
docker-compose down
echo "✅ Container stopped"
echo ""

echo "Step 4/4: Rebuilding and starting container..."
docker-compose build --no-cache
docker-compose up -d
echo "✅ Container rebuilt and started"
echo ""

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Installation Complete! 🎉                               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Your Nuki bridge is now fully autonomous!"
echo ""
echo "📊 Check status:"
echo "   docker-compose logs -f"
echo ""
echo "🔍 Verify watcher:"
echo "   sudo systemctl status nuki-bluetooth-watcher"
echo ""
echo "📝 View restart log:"
echo "   tail -f /tmp/nuki-bluetooth-restart.log"
echo ""
echo "To uninstall: sudo ./uninstall-bluetooth-watcher.sh"
echo ""
