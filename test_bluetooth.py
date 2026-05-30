#!/usr/bin/env python3
"""Diagnostic script to check BlueZ scanner state"""

import asyncio
from bleak import BleakScanner

async def test_scanner():
    print("Creating scanner...")
    scanner = BleakScanner()

    print("Attempting to start scanner...")
    try:
        await scanner.start()
        print("✅ Scanner started successfully!")
        await asyncio.sleep(2)
        print("Stopping scanner...")
        await scanner.stop()
        print("✅ Scanner stopped successfully!")
    except Exception as e:
        print(f"❌ Scanner failed: {e}")
        print(f"   Error type: {type(e).__name__}")

        print("\nAttempting to stop potentially stuck scanner...")
        try:
            await scanner.stop()
            print("✅ Stop succeeded (scanner was running)")
        except Exception as stop_err:
            print(f"❌ Stop failed: {stop_err}")

if __name__ == "__main__":
    asyncio.run(test_scanner())
