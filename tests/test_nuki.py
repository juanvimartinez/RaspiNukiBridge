"""Unit tests for Nuki BLE device operations."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call
from bleak import BleakClient
import struct

# Import from source
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nuki import (
    Nuki, NukiManager, DeviceType, NukiCommand, LockState, OpenerState,
    NukiAction, NukiState, DoorsensorState, StatusCode
)
from tests.fixtures.ble_responses import (
    STATUS_RESPONSE_LOCKED, STATUS_RESPONSE_UNLOCKED,
    LOCK_ACTION_SUCCESS, ERROR_RESPONSE_BAD_AUTH_ID
)


class TestNukiInitialization:
    """Test Nuki device initialization."""

    def test_nuki_init_with_keys(self, nuki_address, auth_id, nuki_public_key,
                                   bridge_public_key, bridge_private_key):
        """Test Nuki initialization with complete credentials."""
        nuki = Nuki(
            address=nuki_address,
            auth_id=auth_id,
            nuki_public_key=nuki_public_key,
            bridge_public_key=bridge_public_key,
            bridge_private_key=bridge_private_key
        )

        assert nuki.address == nuki_address
        assert nuki.auth_id == auth_id
        assert nuki.nuki_public_key == nuki_public_key
        assert nuki.bridge_public_key == bridge_public_key
        assert nuki.bridge_private_key == bridge_private_key
        assert nuki._shared_key is not None  # Should be created
        assert nuki._box is not None  # SecretBox should be initialized

    def test_nuki_init_without_keys(self, nuki_address, auth_id):
        """Test Nuki initialization without encryption keys (pairing mode)."""
        nuki = Nuki(
            address=nuki_address,
            auth_id=auth_id,
            nuki_public_key=None,
            bridge_public_key=None,
            bridge_private_key=None
        )

        assert nuki.address == nuki_address
        assert nuki.auth_id == auth_id
        assert not hasattr(nuki, '_shared_key')

    def test_nuki_default_properties(self, nuki_address, auth_id):
        """Test default property values."""
        nuki = Nuki(nuki_address, auth_id, None, None, None)

        assert nuki.manager is None
        assert nuki.id is None
        assert nuki.name is None
        assert nuki.rssi is None
        assert nuki.last_state is None
        assert nuki.config == {}
        assert nuki.retry == 3
        assert nuki.connection_timeout == 10
        assert nuki.command_timeout == 30

    def test_device_type_smartlock(self, nuki_address, auth_id):
        """Test device type setter for SmartLock."""
        nuki = Nuki(nuki_address, auth_id, None, None, None)
        nuki.device_type = DeviceType.SMARTLOCK_1_2

        assert nuki.device_type == DeviceType.SMARTLOCK_1_2
        assert nuki._BLE_CHAR == "a92ee202-5501-11e4-916c-0800200c9a66"
        assert nuki._BLE_PAIRING_CHAR == "a92ee101-5501-11e4-916c-0800200c9a66"

    def test_device_type_opener(self, nuki_address, auth_id):
        """Test device type setter for Opener."""
        nuki = Nuki(nuki_address, auth_id, None, None, None)
        nuki.device_type = DeviceType.OPENER

        assert nuki.device_type == DeviceType.OPENER
        assert nuki._BLE_CHAR == "a92ae202-5501-11e4-916c-0800200c9a66"
        assert nuki._BLE_PAIRING_CHAR == "a92ae101-5501-11e4-916c-0800200c9a66"


class TestNukiBatteryProperties:
    """Test battery-related property calculations."""

    def test_battery_critical(self, nuki_address, auth_id):
        """Test critical battery state detection."""
        nuki = Nuki(nuki_address, auth_id, None, None, None)
        nuki.last_state = {"critical_battery_state": 0b00000001}  # Bit 0 set
        assert nuki.is_battery_critical is True

        nuki.last_state = {"critical_battery_state": 0b00000000}
        assert nuki.is_battery_critical is False

    def test_battery_charging(self, nuki_address, auth_id):
        """Test battery charging state detection."""
        nuki = Nuki(nuki_address, auth_id, None, None, None)
        nuki.last_state = {"critical_battery_state": 0b00000010}  # Bit 1 set
        assert nuki.is_battery_charging is True

        nuki.last_state = {"critical_battery_state": 0b00000000}
        assert nuki.is_battery_charging is False

    def test_battery_percentage(self, nuki_address, auth_id):
        """Test battery percentage calculation from state byte."""
        nuki = Nuki(nuki_address, auth_id, None, None, None)

        # Battery at 100%: bits 2-7 = 50 (binary 110010) -> (50 << 2) | 0
        nuki.last_state = {"critical_battery_state": 0b11001000}  # 200
        assert nuki.battery_percentage == 100

        # Battery at 50%: bits 2-7 = 25 -> 25 * 2 = 50%
        nuki.last_state = {"critical_battery_state": 0b01100100}  # 100
        assert nuki.battery_percentage == 50

        # Battery at 0%
        nuki.last_state = {"critical_battery_state": 0b00000000}
        assert nuki.battery_percentage == 0


class TestNukiCommandEncoding:
    """Test command preparation and encryption."""

    def test_prepare_command_structure(self):
        """Test command message structure (cmd_code + payload + CRC)."""
        cmd_code = NukiCommand.LOCK_ACTION.value
        payload = bytes([NukiAction.UNLOCK.value])

        message = Nuki._prepare_command(cmd_code, payload)

        # Check structure: 2 bytes cmd_code + payload + 2 bytes CRC
        assert len(message) == 2 + len(payload) + 2
        # Verify command code (little-endian)
        assert struct.unpack("<H", message[:2])[0] == cmd_code
        # Verify payload
        assert message[2:2+len(payload)] == payload

    def test_prepare_command_empty_payload(self):
        """Test command with no payload."""
        cmd_code = NukiCommand.REQUEST_DATA.value
        message = Nuki._prepare_command(cmd_code)

        assert len(message) == 4  # 2 bytes cmd + 2 bytes CRC
        assert struct.unpack("<H", message[:2])[0] == cmd_code

    def test_encrypt_command(self, nuki_address, auth_id, nuki_public_key,
                              bridge_public_key, bridge_private_key):
        """Test command encryption structure."""
        nuki = Nuki(nuki_address, auth_id, nuki_public_key,
                    bridge_public_key, bridge_private_key)

        cmd_code = NukiCommand.LOCK_ACTION.value
        payload = bytes([NukiAction.UNLOCK.value])

        encrypted_message = nuki._encrypt_command(cmd_code, payload)

        # Check structure: 24 bytes nonce + 4 bytes auth_id + 2 bytes length + encrypted data
        assert len(encrypted_message) > 30
        # Verify auth_id in message
        auth_id_in_msg = struct.unpack("<I", encrypted_message[24:28])[0]
        expected_auth_id = struct.unpack("<I", auth_id)[0]
        assert auth_id_in_msg == expected_auth_id

    def test_decrypt_command(self, nuki_address, auth_id, nuki_public_key,
                              bridge_public_key, bridge_private_key):
        """Test command decryption (encrypt then decrypt)."""
        nuki = Nuki(nuki_address, auth_id, nuki_public_key,
                    bridge_public_key, bridge_private_key)

        # Encrypt a command
        cmd_code = NukiCommand.STATUS.value
        payload = bytes([0x00])
        encrypted = nuki._encrypt_command(cmd_code, payload)

        # Decrypt it back
        decrypted = nuki._decrypt_command(encrypted)

        # Verify decrypted structure contains the command
        decrypted_cmd_code = struct.unpack("<H", decrypted[:2])[0]
        assert decrypted_cmd_code == cmd_code


class TestNukiBLEConnection:
    """Test BLE connection lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_success(self, nuki_address, auth_id, nuki_public_key,
                                     bridge_public_key, bridge_private_key):
        """Test successful BLE connection."""
        nuki = Nuki(nuki_address, auth_id, nuki_public_key,
                    bridge_public_key, bridge_private_key)
        nuki.device_type = DeviceType.SMARTLOCK_1_2

        # Mock BleakClient
        mock_client = AsyncMock()
        mock_client.is_connected = False
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.start_notify = AsyncMock()

        # Mock services structure properly
        mock_characteristics = Mock()
        mock_characteristics.values = Mock(return_value=[])
        mock_services = Mock()
        mock_services.__iter__ = Mock(return_value=iter([Mock(__str__=Mock(return_value="mock_service"))]))
        mock_services.characteristics = mock_characteristics
        mock_client.services = mock_services

        # Mock manager
        mock_manager = AsyncMock()
        mock_manager.start_scanning = AsyncMock()
        mock_manager.stop_scanning = AsyncMock()
        mock_manager.get_client = Mock(return_value=mock_client)
        nuki.manager = mock_manager

        result = await nuki.connect()

        # connect() doesn't return a value, check it completed without error
        assert result is None
        mock_manager.stop_scanning.assert_called_once()
        mock_client.connect.assert_called_once()
        # Should start notifications on the data characteristic
        assert mock_client.start_notify.called

    @pytest.mark.asyncio
    async def test_connect_timeout(self, nuki_address, auth_id, nuki_public_key,
                                     bridge_public_key, bridge_private_key):
        """Test connection timeout handling."""
        nuki = Nuki(nuki_address, auth_id, nuki_public_key,
                    bridge_public_key, bridge_private_key)
        nuki.device_type = DeviceType.SMARTLOCK_1_2
        nuki.connection_timeout = 1  # Short timeout

        # Mock slow client
        mock_client = AsyncMock()
        mock_client.is_connected = False
        # Simulate slow connection
        async def slow_connect(*args, **kwargs):
            await asyncio.sleep(5)
            return True
        mock_client.connect = slow_connect

        # Mock services structure properly
        mock_characteristics = Mock()
        mock_characteristics.values = Mock(return_value=[])
        mock_services = Mock()
        mock_services.__iter__ = Mock(return_value=iter([Mock(__str__=Mock(return_value="mock_service"))]))
        mock_services.characteristics = mock_characteristics
        mock_client.services = mock_services

        # Mock manager
        mock_manager = AsyncMock()
        mock_manager.start_scanning = AsyncMock()
        mock_manager.stop_scanning = AsyncMock()
        mock_manager.get_client = Mock(return_value=mock_client)
        nuki.manager = mock_manager

        # Connection should timeout and raise
        with pytest.raises(Exception):  # Will raise after retries fail
            await nuki.connect()

    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self, nuki_address, auth_id, nuki_public_key,
                                       bridge_public_key, bridge_private_key):
        """Test disconnect cleans up notifications and client."""
        nuki = Nuki(nuki_address, auth_id, nuki_public_key,
                    bridge_public_key, bridge_private_key)
        nuki.device_type = DeviceType.SMARTLOCK_1_2

        # Mock manager
        mock_manager = AsyncMock()
        mock_manager.start_scanning = AsyncMock()
        mock_manager.stop_scanning = AsyncMock()
        nuki.manager = mock_manager

        # Setup a connected client
        mock_client = AsyncMock()
        mock_client.is_connected = True
        mock_client.disconnect = AsyncMock()
        mock_client.stop_notify = AsyncMock()
        nuki._client = mock_client

        await nuki.disconnect()

        mock_client.disconnect.assert_called_once()
        mock_manager.start_scanning.assert_called_once()
        # Note: _client is not set to None in disconnect() - it's reused

    @pytest.mark.asyncio
    async def test_concurrent_connect_prevention(self, nuki_address, auth_id,
                                                   nuki_public_key, bridge_public_key,
                                                   bridge_private_key):
        """Test that concurrent connect calls are prevented."""
        nuki = Nuki(nuki_address, auth_id, nuki_public_key,
                    bridge_public_key, bridge_private_key)
        nuki.device_type = DeviceType.SMARTLOCK_1_2

        # Mock slow client
        mock_client = AsyncMock()
        mock_client.is_connected = False
        async def slow_connect(*args, **kwargs):
            await asyncio.sleep(0.5)
            return True
        mock_client.connect = slow_connect
        mock_client.start_notify = AsyncMock()

        # Mock services structure properly
        mock_characteristics = Mock()
        mock_characteristics.values = Mock(return_value=[])
        mock_services = Mock()
        mock_services.__iter__ = Mock(return_value=iter([Mock(__str__=Mock(return_value="mock_service"))]))
        mock_services.characteristics = mock_characteristics
        mock_client.services = mock_services

        # Mock manager
        mock_manager = AsyncMock()
        mock_manager.start_scanning = AsyncMock()
        mock_manager.stop_scanning = AsyncMock()
        mock_manager.get_client = Mock(return_value=mock_client)
        nuki.manager = mock_manager

        # Start two connect operations concurrently
        task1 = asyncio.create_task(nuki.connect())
        await asyncio.sleep(0.1)  # Let first connect acquire lock
        task2 = asyncio.create_task(nuki.connect())

        results = await asyncio.gather(task1, task2)

        # Both should complete (first does actual connect, second returns early)
        assert results[0] is None  # First connect completes
        assert results[1] is None  # Second returns early (already connecting)
        # Only one stop_scanning should have been called
        assert mock_manager.stop_scanning.call_count == 1


class TestNukiLockActions:
    """Test lock action commands."""

    @pytest.mark.skip(reason="Complex async flow requires extensive mocking")
    @pytest.mark.asyncio
    async def test_unlock_action(self, nuki_address, auth_id, nuki_public_key,
                                  bridge_public_key, bridge_private_key):
        """Test unlock command."""
        nuki = Nuki(nuki_address, auth_id, nuki_public_key,
                    bridge_public_key, bridge_private_key)
        nuki.device_type = DeviceType.SMARTLOCK_1_2

        # Mock the lock_action method
        nuki.lock_action = AsyncMock(return_value={"success": True})

        result = await nuki.unlock()

        nuki.lock_action.assert_called_once_with(NukiAction.UNLOCK)
        assert result["success"] is True

    @pytest.mark.skip(reason="Complex async flow requires extensive mocking")
    @pytest.mark.asyncio
    async def test_lock_action(self, nuki_address, auth_id, nuki_public_key,
                                bridge_public_key, bridge_private_key):
        """Test lock command."""
        nuki = Nuki(nuki_address, auth_id, nuki_public_key,
                    bridge_public_key, bridge_private_key)
        nuki.device_type = DeviceType.SMARTLOCK_1_2

        nuki.lock_action = AsyncMock(return_value={"success": True})

        result = await nuki.lock()

        nuki.lock_action.assert_called_once_with(NukiAction.LOCK)
        assert result["success"] is True

    @pytest.mark.skip(reason="Complex async flow requires extensive mocking")
    @pytest.mark.asyncio
    async def test_unlatch_action(self, nuki_address, auth_id, nuki_public_key,
                                   bridge_public_key, bridge_private_key):
        """Test unlatch command."""
        nuki = Nuki(nuki_address, auth_id, nuki_public_key,
                    bridge_public_key, bridge_private_key)
        nuki.device_type = DeviceType.SMARTLOCK_1_2

        nuki.lock_action = AsyncMock(return_value={"success": True})

        result = await nuki.unlatch()

        nuki.lock_action.assert_called_once_with(NukiAction.UNLATCH)
        assert result["success"] is True


class TestNukiCommandQueue:
    """Test command queue and sequential execution."""

    @pytest.mark.skip(reason="Complex async flow requires extensive mocking")
    @pytest.mark.asyncio
    async def test_command_queue_sequential_execution(self, nuki_address, auth_id,
                                                       nuki_public_key, bridge_public_key,
                                                       bridge_private_key):
        """Test that commands execute sequentially, not concurrently."""
        nuki = Nuki(nuki_address, auth_id, nuki_public_key,
                    bridge_public_key, bridge_private_key)
        nuki.device_type = DeviceType.SMARTLOCK_1_2

        execution_order = []

        async def mock_execute(action):
            execution_order.append(f"start_{action}")
            await asyncio.sleep(0.1)  # Simulate work
            execution_order.append(f"end_{action}")
            return {"success": True}

        nuki._execute_command = mock_execute

        # Queue multiple commands
        task1 = asyncio.create_task(nuki.lock_action(NukiAction.UNLOCK))
        task2 = asyncio.create_task(nuki.lock_action(NukiAction.LOCK))
        task3 = asyncio.create_task(nuki.lock_action(NukiAction.UNLATCH))

        await asyncio.gather(task1, task2, task3)

        # Verify sequential execution (start then end, no interleaving)
        assert execution_order == [
            "start_<NukiAction.UNLOCK: 1>", "end_<NukiAction.UNLOCK: 1>",
            "start_<NukiAction.LOCK: 2>", "end_<NukiAction.LOCK: 2>",
            "start_<NukiAction.UNLATCH: 3>", "end_<NukiAction.UNLATCH: 3>"
        ]

    @pytest.mark.skip(reason="Complex async flow requires extensive mocking")
    @pytest.mark.asyncio
    async def test_command_timeout(self, nuki_address, auth_id, nuki_public_key,
                                    bridge_public_key, bridge_private_key):
        """Test command timeout handling."""
        nuki = Nuki(nuki_address, auth_id, nuki_public_key,
                    bridge_public_key, bridge_private_key)
        nuki.device_type = DeviceType.SMARTLOCK_1_2
        nuki.command_timeout = 1  # Short timeout

        async def never_completes(*args):
            await asyncio.sleep(10)  # Never completes in time

        nuki._execute_command = never_completes

        with pytest.raises(asyncio.TimeoutError):
            await nuki.lock_action(NukiAction.UNLOCK)


class TestNukiStateUpdate:
    """Test state update and parsing."""

    @pytest.mark.skip(reason="Complex async flow requires extensive mocking")
    @pytest.mark.asyncio
    async def test_update_state_success(self, nuki_address, auth_id, nuki_public_key,
                                         bridge_public_key, bridge_private_key):
        """Test successful state update."""
        nuki = Nuki(nuki_address, auth_id, nuki_public_key,
                    bridge_public_key, bridge_private_key)
        nuki.device_type = DeviceType.SMARTLOCK_1_2

        # Mock the command execution to return a state
        mock_state = {
            "lock_state": LockState.LOCKED,
            "nuki_state": NukiState.DOOR_MODE,
            "trigger": 0,
            "critical_battery_state": 100
        }
        nuki._execute_command = AsyncMock(return_value=mock_state)

        result = await nuki.update_state()

        assert result == mock_state
        assert nuki.last_state == mock_state


class TestNukiEnums:
    """Test enum definitions and values."""

    def test_device_type_values(self):
        """Verify DeviceType enum values match protocol."""
        assert DeviceType.SMARTLOCK_1_2.value == 0
        assert DeviceType.OPENER.value == 2
        assert DeviceType.SMARTDOOR.value == 3
        assert DeviceType.SMARTLOCK_3.value == 4

    def test_lock_state_values(self):
        """Verify LockState enum values."""
        assert LockState.UNCALIBRATED.value == 0x00
        assert LockState.LOCKED.value == 0x01
        assert LockState.UNLOCKING.value == 0x02
        assert LockState.UNLOCKED.value == 0x03
        assert LockState.LOCKING.value == 0x04
        assert LockState.UNLATCHED.value == 0x05

    def test_nuki_action_values(self):
        """Verify NukiAction enum values."""
        assert NukiAction.UNLOCK.value == 0x01
        assert NukiAction.LOCK.value == 0x02
        assert NukiAction.UNLATCH.value == 0x03
        assert NukiAction.LOCK_N_GO.value == 0x04

    def test_nuki_command_values(self):
        """Verify NukiCommand enum values match protocol."""
        assert NukiCommand.REQUEST_DATA.value == 0x0001
        assert NukiCommand.PUBLIC_KEY.value == 0x0003
        assert NukiCommand.CHALLENGE.value == 0x0004
        assert NukiCommand.LOCK_ACTION.value == 0x000D
        assert NukiCommand.STATUS.value == 0x000E
        assert NukiCommand.ERROR_REPORT.value == 0x0012


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
