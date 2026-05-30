"""Shared pytest fixtures for RaspiNukiBridge tests."""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from bleak import BleakClient, BleakScanner
import asyncio


@pytest.fixture
def mock_bleak_client():
    """Mocked BleakClient for BLE operations."""
    client = AsyncMock(spec=BleakClient)
    client.is_connected = False
    client.address = "AA:BB:CC:DD:EE:FF"
    client.connect = AsyncMock(return_value=True)
    client.disconnect = AsyncMock(return_value=True)
    client.start_notify = AsyncMock(return_value=None)
    client.stop_notify = AsyncMock(return_value=None)
    client.write_gatt_char = AsyncMock(return_value=None)
    client.read_gatt_char = AsyncMock(return_value=b'\x00' * 32)
    return client


@pytest.fixture
def mock_bleak_scanner():
    """Mocked BleakScanner for device discovery."""
    scanner = AsyncMock(spec=BleakScanner)
    scanner.start = AsyncMock(return_value=None)
    scanner.stop = AsyncMock(return_value=None)
    scanner.register_detection_callback = Mock(return_value=None)
    return scanner


@pytest.fixture
def test_config():
    """Sample configuration for testing."""
    return {
        "server": {
            "host": "0.0.0.0",
            "port": 8080,
            "name": "TestBridge",
            "app_id": 12345678,
            "token": "a" * 64,
            "id": "test-bridge-001",
            "adapter": "hci0"
        },
        "smartlock": [
            {
                "address": "AA:BB:CC:DD:EE:FF",
                "bridge_public_key": "b" * 64,
                "bridge_private_key": "c" * 64,
                "nuki_public_key": "d" * 64,
                "auth_id": 123456,
                "connection_timeout": 10,
                "retry": 3,
                "command_timeout": 30
            }
        ]
    }


@pytest.fixture
def mock_encryption():
    """Mocked NaCl encryption operations."""
    mock_box = Mock()
    mock_box.encrypt = Mock(return_value=Mock(ciphertext=b'\x00' * 48))
    mock_box.decrypt = Mock(return_value=b'\x00' * 32)
    return mock_box


@pytest.fixture
def nuki_public_key():
    """Test Nuki public key (32 bytes)."""
    return bytes.fromhex("d" * 64)


@pytest.fixture
def bridge_public_key():
    """Test bridge public key (32 bytes)."""
    return bytes.fromhex("b" * 64)


@pytest.fixture
def bridge_private_key():
    """Test bridge private key (32 bytes)."""
    return bytes.fromhex("c" * 64)


@pytest.fixture
def auth_id():
    """Test auth ID."""
    return 123456


@pytest.fixture
def nuki_address():
    """Test Nuki device BLE address."""
    return "AA:BB:CC:DD:EE:FF"


@pytest.fixture
async def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
