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

echo "Step 1/6: Stopping and disabling services..."
if systemctl is-active --quiet raspinukibridge; then
    systemctl stop raspinukibridge
    echo "   raspinukibridge service stopped"
fi

if systemctl is-enabled --quiet raspinukibridge 2>/dev/null; then
    systemctl disable raspinukibridge
    echo "   raspinukibridge service disabled"
fi

if systemctl is-active --quiet bluetooth-reset; then
    systemctl stop bluetooth-reset
    echo "   bluetooth-reset service stopped"
fi

if systemctl is-enabled --quiet bluetooth-reset 2>/dev/null; then
    systemctl disable bluetooth-reset
    echo "   bluetooth-reset service disabled"
fi

# Also remove any old bluez-cleanup service (obsolete)
if systemctl is-active --quiet bluez-cleanup 2>/dev/null; then
    systemctl stop bluez-cleanup
    echo "   bluez-cleanup service stopped (obsolete)"
fi

if systemctl is-enabled --quiet bluez-cleanup 2>/dev/null; then
    systemctl disable bluez-cleanup
    echo "   bluez-cleanup service disabled (obsolete)"
fi
echo "✅ Services stopped and disabled"
echo ""

echo "Step 2/6: Removing systemd service files..."
if [ -f "/etc/systemd/system/raspinukibridge.service" ]; then
    rm -f /etc/systemd/system/raspinukibridge.service
    echo "   Removed /etc/systemd/system/raspinukibridge.service"
fi

if [ -f "/etc/systemd/system/bluetooth-reset.service" ]; then
    rm -f /etc/systemd/system/bluetooth-reset.service
    echo "   Removed /etc/systemd/system/bluetooth-reset.service"
fi

# Remove obsolete bluez-cleanup service if it exists
if [ -f "/etc/systemd/system/bluez-cleanup.service" ]; then
    rm -f /etc/systemd/system/bluez-cleanup.service
    echo "   Removed /etc/systemd/system/bluez-cleanup.service (obsolete)"
fi

systemctl daemon-reload
echo "✅ Service files removed"
echo ""

echo "Step 3/6: Removing Bluetooth reset script..."
if [ -f "/usr/local/bin/bluetooth-reset.sh" ]; then
    rm -f /usr/local/bin/bluetooth-reset.sh
    echo "   Removed /usr/local/bin/bluetooth-reset.sh"
fi

# Remove obsolete bluez-cleanup script if it exists
if [ -f "/usr/local/bin/bluez-cleanup.sh" ]; then
    rm -f /usr/local/bin/bluez-cleanup.sh
    echo "   Removed /usr/local/bin/bluez-cleanup.sh (obsolete)"
fi
echo "✅ Bluetooth reset script removed"
echo ""

echo "Step 4/6: Removing sudoers configuration..."
if [ -f "/etc/sudoers.d/raspinuki-bluetooth" ]; then
    rm -f /etc/sudoers.d/raspinuki-bluetooth
    echo "   Removed /etc/sudoers.d/raspinuki-bluetooth"
fi
echo "✅ Sudoers configuration removed"
echo ""

echo "Step 5/6: Removing installation directory..."
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

echo "Step 6/6: Removing raspinuki user..."
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
