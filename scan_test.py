#!/usr/bin/env python3
"""Quick Bluetooth scan test - run inside container to verify BLE access"""
import asyncio
from bleak import BleakScanner

async def scan():
    print("🔍 Scanning for Bluetooth LE devices (10 seconds)...")
    print("=" * 60)

    devices = await BleakScanner.discover(timeout=10)

    if not devices:
        print("❌ No devices found!")
        print("\nPossible causes:")
        print("  - Container doesn't have Bluetooth access")
        print("  - BlueZ not running on host")
        print("  - No BLE devices nearby")
        print("\nTroubleshooting:")
        print("  1. Check: docker exec raspinukibridge hciconfig")
        print("  2. On host: sudo hciconfig hci0 up")
        print("  3. On host: sudo systemctl restart bluetooth")
        return

    print(f"✅ Found {len(devices)} device(s):\n")

    nuki_found = False
    for d in sorted(devices, key=lambda x: x.rssi or -999, reverse=True):
        name = d.name or "Unknown"
        rssi = d.rssi if d.rssi else "N/A"

        # Highlight Nuki devices
        is_nuki = "nuki" in name.lower() or "54:D2:72" in d.address.upper()
        prefix = "🔐" if is_nuki else "  "

        print(f"{prefix} {d.address}: {name:30s} RSSI: {rssi}")

        if is_nuki:
            nuki_found = True

    print("\n" + "=" * 60)
    if nuki_found:
        print("✅ Nuki device detected!")
    else:
        print("⚠️  No Nuki device found in scan")
        print("\nTroubleshooting:")
        print("  - Verify Nuki MAC address in config matches")
        print("  - Check Nuki battery level (Settings in app)")
        print("  - Ensure Nuki Bluetooth is enabled")
        print("  - Move Raspberry Pi closer to Nuki (< 5m)")
        print("  - If Battery Performance mode: should appear immediately")
        print("  - If Normal mode: press Nuki button to wake")

if __name__ == "__main__":
    asyncio.run(scan())
