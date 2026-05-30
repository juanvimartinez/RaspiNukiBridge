#!/bin/bash
# Native installation script for RaspiNukiBridge
# Installs the bridge as a system service running directly on Raspberry Pi

set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  RaspiNukiBridge - Native Installation                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Error: Please run with sudo"
    echo "Usage: sudo ./install-native.sh"
    exit 1
fi

# Check if we're in the RaspiNukiBridge directory
if [ ! -f "nuki.py" ]; then
    echo "❌ Error: Please run this script from the RaspiNukiBridge directory"
    exit 1
fi

echo "Step 1/8: Installing system dependencies..."
apt-get update
apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    dbus \
    bluez \
    bluetooth \
    libglib2.0-0 \
    libglib2.0-dev \
    build-essential \
    libffi-dev \
    libsodium-dev \
    git
echo "✅ System dependencies installed"
echo ""

echo "Step 2/8: Creating raspinuki user..."
if id "raspinuki" &>/dev/null; then
    echo "   User 'raspinuki' already exists"
else
    useradd -r -s /bin/bash -d /opt/raspinukibridge -m raspinuki
    echo "   Created user 'raspinuki'"
fi

# Add user to bluetooth group
usermod -aG bluetooth raspinuki
usermod -aG dialout raspinuki
echo "✅ User configured with Bluetooth permissions"
echo ""

echo "Step 3/8: Creating installation directory..."
mkdir -p /opt/raspinukibridge
mkdir -p /opt/raspinukibridge/config

# Copy source files
cp -r ./* /opt/raspinukibridge/
chown -R raspinuki:raspinuki /opt/raspinukibridge
echo "✅ Files copied to /opt/raspinukibridge"
echo ""

echo "Step 4/8: Creating Python virtual environment..."
cd /opt/raspinukibridge
sudo -u raspinuki python3 -m venv venv
echo "✅ Virtual environment created"
echo ""

echo "Step 5/8: Installing Python dependencies..."
sudo -u raspinuki venv/bin/pip install --upgrade pip setuptools wheel
sudo -u raspinuki venv/bin/pip install -r requirements.txt
echo "✅ Python dependencies installed"
echo ""

echo "Step 6/8: Migrating configuration..."
if [ -f "/opt/raspinukibridge/config/nuki.yaml" ]; then
    echo "   Configuration already exists at /opt/raspinukibridge/config/nuki.yaml"
elif [ -f "$PWD/../raspinukibridge_docker/config/nuki.yaml" ]; then
    cp "$PWD/../raspinukibridge_docker/config/nuki.yaml" /opt/raspinukibridge/config/
    chown raspinuki:raspinuki /opt/raspinukibridge/config/nuki.yaml
    echo "   Migrated config from Docker deployment"
else
    echo "   ⚠️  No existing config found - will generate on first run"
fi
echo "✅ Configuration ready"
echo ""

echo "Step 7/8: Configuring Bluetooth reset service..."
# Install Bluetooth reset script
cp bluetooth-reset.sh /usr/local/bin/bluetooth-reset.sh
chmod +x /usr/local/bin/bluetooth-reset.sh

# Create systemd service for Bluetooth reset
cat > /etc/systemd/system/bluetooth-reset.service << 'EOF'
[Unit]
Description=Bluetooth Module Reset
After=local-fs.target
Before=bluetooth.service

[Service]
Type=oneshot
ExecStart=/bin/bash /usr/local/bin/bluetooth-reset.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl enable bluetooth-reset.service
echo "✅ Bluetooth reset service configured"
echo ""

echo "Step 8/9: Configuring sudo permissions for Bluetooth restart..."
cat > /etc/sudoers.d/raspinuki-bluetooth << 'EOF'
# Allow raspinuki user to restart Bluetooth without password
raspinuki ALL=(ALL) NOPASSWD: /bin/systemctl restart bluetooth
raspinuki ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart bluetooth
EOF
chmod 0440 /etc/sudoers.d/raspinuki-bluetooth
echo "✅ Sudo permissions configured"
echo ""

echo "Step 9/9: Creating and enabling systemd service..."
cat > /etc/systemd/system/raspinukibridge.service << 'EOF'
[Unit]
Description=RaspiNukiBridge - Nuki Smart Lock Bridge
After=network.target bluetooth.service bluetooth-reset.service
Wants=bluetooth.service
Requires=bluetooth-reset.service

[Service]
Type=simple
User=raspinuki
Group=raspinuki
WorkingDirectory=/opt/raspinukibridge
Environment="PATH=/opt/raspinukibridge/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStartPre=/bin/sleep 15
ExecStart=/opt/raspinukibridge/venv/bin/python3 /opt/raspinukibridge/__main__.py --config /opt/raspinukibridge/config/nuki.yaml
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=false
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/raspinukibridge/config /tmp
SupplementaryGroups=bluetooth dialout

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable raspinukibridge
systemctl start raspinukibridge
echo "✅ Service created and started"
echo ""

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Installation Complete! 🎉                               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "RaspiNukiBridge is now running as a native service!"
echo ""
echo "📊 Check status:"
echo "   sudo systemctl status raspinukibridge"
echo ""
echo "📝 View logs:"
echo "   sudo journalctl -u raspinukibridge -f"
echo ""
echo "🔧 Manage service:"
echo "   sudo systemctl start|stop|restart raspinukibridge"
echo ""
echo "⚙️  Configuration:"
echo "   sudo nano /opt/raspinukibridge/config/nuki.yaml"
echo "   sudo systemctl restart raspinukibridge"
echo ""
echo "To uninstall: sudo ./uninstall-native.sh"
echo ""

# Wait a moment for service to start
sleep 3

# Show initial status
echo "Current service status:"
systemctl status raspinukibridge --no-pager || true
echo ""
