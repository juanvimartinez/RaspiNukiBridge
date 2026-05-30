"""Mock BLE response data for Nuki protocol testing."""

# BLE Advertisement data for Nuki devices
NUKI_SMARTLOCK_V2_ADVERTISEMENT = {
    "address": "AA:BB:CC:DD:EE:FF",
    "rssi": -65,
    "manufacturer_data": {
        0x004C: bytes.fromhex("02150000000000000000000000000000000000000000")  # iBeacon format
    }
}

NUKI_OPENER_ADVERTISEMENT = {
    "address": "11:22:33:44:55:66",
    "rssi": -70,
    "manufacturer_data": {
        0x004C: bytes.fromhex("02150000000000000000000000000000000000000000")
    }
}

# Nuki command responses (encrypted payloads)
# These are mock responses - actual protocol uses encrypted data

# Response to REQUEST_DATA command (public key exchange)
PUBLIC_KEY_RESPONSE = bytes.fromhex(
    "03"  # Command: PUBLIC_KEY
    + "20" * 32  # 32-byte public key (mock)
)

# Response to CHALLENGE command (auth_id)
CHALLENGE_RESPONSE = bytes.fromhex(
    "04"  # Command: CHALLENGE_RESPONSE
    + "0001e240"  # Auth ID: 123456 (4 bytes little-endian)
)

# Response to STATUS command (current lock state)
STATUS_RESPONSE_LOCKED = bytes.fromhex(
    "0E"  # Command: STATUS
    + "01"  # Lock state: LOCKED
    + "00"  # State: IDLE
    + "00"  # Trigger: SYSTEM
    + "0000"  # Current time
    + "00"  # Timezone offset
    + "00"  # Critical battery state
    + "00"  # Config update count
    + "00"  # Lock n go timer
)

STATUS_RESPONSE_UNLOCKED = bytes.fromhex(
    "0E"  # Command: STATUS
    + "03"  # Lock state: UNLOCKED
    + "00"  # State: IDLE
    + "00"  # Trigger: SYSTEM
    + "0000"  # Current time
    + "00"  # Timezone offset
    + "00"  # Critical battery state
    + "00"  # Config update count
    + "00"  # Lock n go timer
)

# Response to LOCK_ACTION command (success)
LOCK_ACTION_SUCCESS = bytes.fromhex(
    "0C"  # Command: STATUS
    + "00"  # Status: COMPLETE/SUCCESS
)

# Error response
ERROR_RESPONSE_BAD_CRC = bytes.fromhex(
    "12"  # Command: ERROR_REPORT
    + "FD"  # Error code: BAD_CRC
)

ERROR_RESPONSE_BAD_AUTH_ID = bytes.fromhex(
    "12"  # Command: ERROR_REPORT
    + "10"  # Error code: BAD_AUTHENTICATOR
)

# Config response
CONFIG_RESPONSE = bytes.fromhex(
    "14"  # Command: CONFIG
    + "01020304"  # Nuki ID
    + "4E756B69"  # Name: "Nuki"
    + "00" * 20  # Rest of config data
)

# Battery report
BATTERY_REPORT = bytes.fromhex(
    "11"  # Command: BATTERY_REPORT
    + "64"  # Battery percentage: 100%
)
