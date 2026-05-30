"""Configuration sample data for tests."""

VALID_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 8080,
        "name": "TestRaspiNukiBridge",
        "app_id": 987654321,
        "token": "abc123" * 10 + "abcd",  # 64 char hex string
        "id": "test-bridge-12345",
        "adapter": "hci0"
    },
    "smartlock": [
        {
            "address": "11:22:33:44:55:66",
            "bridge_public_key": "aa" * 32,
            "bridge_private_key": "bb" * 32,
            "nuki_public_key": "cc" * 32,
            "auth_id": 111111,
            "connection_timeout": 15,
            "retry": 5,
            "command_timeout": 25
        },
        {
            "address": "AA:BB:CC:DD:EE:FF",
            "bridge_public_key": "dd" * 32,
            "bridge_private_key": "ee" * 32,
            "nuki_public_key": "ff" * 32,
            "auth_id": 222222,
        }
    ]
}

MINIMAL_CONFIG = {
    "server": {
        "host": "127.0.0.1",
        "port": 9090,
        "name": "MinimalBridge",
        "app_id": 111111,
        "token": "aabbccdd" * 8,
        "id": "minimal-001"
    },
    "smartlock": [
        {
            "address": "00:11:22:33:44:55",
            "bridge_public_key": "11" * 32,
            "bridge_private_key": "22" * 32,
            "nuki_public_key": "33" * 32,
            "auth_id": 999999,
        }
    ]
}

INVALID_CONFIG_MISSING_SERVER = {
    "smartlock": []
}

INVALID_CONFIG_MISSING_TOKEN = {
    "server": {
        "host": "0.0.0.0",
        "port": 8080,
        "name": "BadBridge",
        "app_id": 123,
        "id": "bad-001"
        # Missing token
    },
    "smartlock": []
}

INVALID_CONFIG_BAD_PORT = {
    "server": {
        "host": "0.0.0.0",
        "port": "not_a_number",  # Invalid type
        "name": "BadBridge",
        "app_id": 123,
        "token": "aa" * 32,
        "id": "bad-002"
    },
    "smartlock": []
}
