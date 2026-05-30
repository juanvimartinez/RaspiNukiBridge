#!/bin/bash
# Uninstallation script for native RaspiNukiBridge deployment

set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  RaspiNukiBridge - Native Uninstallation                 ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Error: Please run with sudo"
    echo "Usage: sudo ./uninstall-native.sh"
    exit 1
fi

echo "Step 1/5: Stopping and disabling service..."
if systemctl is-active --quiet raspinukibridge; then
    systemctl stop raspinukibridge
    echo "   Service stopped"
fi

if systemctl is-enabled --quiet raspinukibridge 2>/dev/null; then
    systemctl disable raspinukibridge
    echo "   Service disabled"
fi
echo "✅ Service stopped and disabled"
echo ""

echo "Step 2/5: Removing systemd service file..."
if [ -f "/etc/systemd/system/raspinukibridge.service" ]; then
    rm -f /etc/systemd/system/raspinukibridge.service
    systemctl daemon-reload
    echo "   Removed /etc/systemd/system/raspinukibridge.service"
fi
echo "✅ Service file removed"
echo ""

echo "Step 3/5: Removing sudoers configuration..."
if [ -f "/etc/sudoers.d/raspinuki-bluetooth" ]; then
    rm -f /etc/sudoers.d/raspinuki-bluetooth
    echo "   Removed /etc/sudoers.d/raspinuki-bluetooth"
fi
echo "✅ Sudoers configuration removed"
echo ""

echo "Step 4/5: Removing installation directory..."
if [ -d "/opt/raspinukibridge" ]; then
    # Backup config if it exists
    if [ -f "/opt/raspinukibridge/config/nuki.yaml" ]; then
        BACKUP_DIR="$HOME/raspinukibridge_backup_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        cp /opt/raspinukibridge/config/nuki.yaml "$BACKUP_DIR/"
        echo "   ℹ️  Backed up config to: $BACKUP_DIR/nuki.yaml"
    fi

    rm -rf /opt/raspinukibridge
    echo "   Removed /opt/raspinukibridge"
fi
echo "✅ Installation directory removed"
echo ""

echo "Step 5/5: Removing raspinuki user..."
if id "raspinuki" &>/dev/null; then
    userdel raspinuki 2>/dev/null || true
    echo "   Removed user 'raspinuki'"
fi
echo "✅ User removed"
echo ""

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Uninstallation Complete! ✅                             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "RaspiNukiBridge native installation has been removed."
echo ""
echo "Note: System packages (Python3, BlueZ, etc.) were not removed"
echo "      as they may be used by other applications."
echo ""
echo "To reinstall: sudo ./install-native.sh"
echo ""
