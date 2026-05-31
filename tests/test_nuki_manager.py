"""Unit tests for NukiManager device management."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call
from bleak import BleakScanner

# Import from source
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nuki import Nuki, NukiManager, NukiClientType, DeviceType


class TestNukiManagerInitialization:
    """Test NukiManager initialization."""

    @patch('nuki.BleakScanner')
    def test_manager_init(self, mock_scanner_class):
        """Test NukiManager initialization with default parameters."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123456)

        assert manager.name == "TestBridge"
        assert manager.app_id == 123456
        assert manager.type_id == NukiClientType.BRIDGE
        assert manager._adapter == "hci0"  # Default
        assert manager._devices == {}
        assert manager._scanner is not None
        assert manager._scanner_running is False
        assert manager._newstate_callback is None
        assert manager._connection_failure_count == 0
        assert manager._health_check_failure_count == 0
        assert manager._health_check_task is None

    @patch('nuki.BleakScanner')
    def test_manager_init_custom_adapter(self, mock_scanner_class):
        """Test NukiManager with custom Bluetooth adapter."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=999, adapter="hci1")

        assert manager._adapter == "hci1"

    @patch('nuki.BleakScanner')
    def test_manager_registers_detection_callback(self, mock_scanner_class):
        """Test that scanner callback is registered during init."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        # Verify register_detection_callback was called
        mock_scanner.register_detection_callback.assert_called_once()
        # Verify it was called with the manager's _detected_ibeacon method
        callback_arg = mock_scanner.register_detection_callback.call_args[0][0]
        assert callback_arg.__name__ == '_detected_ibeacon'


class TestNukiManagerDeviceManagement:
    """Test device registration and lookup."""

    @patch('nuki.BleakScanner')
    def test_add_nuki_device(self, mock_scanner_class):
        """Test adding a Nuki device to manager."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        mock_nuki = Mock(spec=Nuki)
        mock_nuki.address = "aa:bb:cc:dd:ee:ff"

        manager.add_nuki(mock_nuki)

        assert mock_nuki.address in manager._devices
        assert manager._devices[mock_nuki.address] == mock_nuki
        assert mock_nuki.manager == manager

    @patch('nuki.BleakScanner')
    def test_add_multiple_devices(self, mock_scanner_class):
        """Test adding multiple devices."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        nuki1 = Mock(spec=Nuki)
        nuki1.address = "11:22:33:44:55:66"

        nuki2 = Mock(spec=Nuki)
        nuki2.address = "aa:bb:cc:dd:ee:ff"

        manager.add_nuki(nuki1)
        manager.add_nuki(nuki2)

        assert len(manager._devices) == 2
        assert nuki1.address in manager._devices
        assert nuki2.address in manager._devices

    @patch('nuki.BleakScanner')
    def test_nuki_by_id_lookup(self, mock_scanner_class):
        """Test device lookup by Nuki ID."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        nuki1 = Mock(spec=Nuki)
        nuki1.address = "11:22:33:44:55:66"
        nuki1.config = {"id": 111111, "name": "Front Door"}

        nuki2 = Mock(spec=Nuki)
        nuki2.address = "aa:bb:cc:dd:ee:ff"
        nuki2.config = {"id": 222222, "name": "Back Door"}

        manager.add_nuki(nuki1)
        manager.add_nuki(nuki2)

        # Lookup by ID
        found = manager.nuki_by_id(222222)
        assert found == nuki2

    @patch('nuki.BleakScanner')
    def test_nuki_by_id_not_found(self, mock_scanner_class):
        """Test device lookup with non-existent ID raises StopIteration."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        nuki = Mock(spec=Nuki)
        nuki.address = "11:22:33:44:55:66"
        nuki.config = {"id": 111111}
        manager.add_nuki(nuki)

        with pytest.raises(StopIteration):
            manager.nuki_by_id(999999)  # Non-existent ID

    @patch('nuki.BleakScanner')
    def test_device_list_property(self, mock_scanner_class):
        """Test device_list property returns all devices."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        nuki1 = Mock(spec=Nuki)
        nuki1.address = "11:22:33:44:55:66"

        nuki2 = Mock(spec=Nuki)
        nuki2.address = "aa:bb:cc:dd:ee:ff"

        manager.add_nuki(nuki1)
        manager.add_nuki(nuki2)

        device_list = manager.device_list
        assert len(device_list) == 2
        assert nuki1 in device_list
        assert nuki2 in device_list

    @patch('nuki.BleakScanner')
    def test_manager_getitem(self, mock_scanner_class):
        """Test indexing manager like a list."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        nuki1 = Mock(spec=Nuki)
        nuki1.address = "11:22:33:44:55:66"

        nuki2 = Mock(spec=Nuki)
        nuki2.address = "aa:bb:cc:dd:ee:ff"

        manager.add_nuki(nuki1)
        manager.add_nuki(nuki2)

        # Access by index
        first = manager[0]
        second = manager[1]
        assert first in [nuki1, nuki2]
        assert second in [nuki1, nuki2]
        assert first != second


class TestNukiManagerScanning:
    """Test BLE scanning lifecycle."""

    @pytest.mark.asyncio
    @patch('nuki.BleakScanner')
    async def test_initialize_does_bluetooth_reset(self, mock_scanner_class):
        """Test initialize() does a full Bluetooth reset and creates fresh scanner."""
        mock_scanner = AsyncMock()
        mock_scanner.stop = AsyncMock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        # Mock subprocess to avoid actual system calls
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr='')
            await manager.initialize()

        # initialize() creates a fresh scanner, resets state
        assert manager._scanner_running is False
        assert manager._connection_failure_count == 0
        assert manager._health_check_failure_count == 0

    @pytest.mark.asyncio
    @patch('nuki.BleakScanner')
    async def test_start_scanning_success(self, mock_scanner_class):
        """Test successful scanner start."""
        mock_scanner = AsyncMock()
        mock_scanner.start = AsyncMock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)
        manager._scanner = mock_scanner

        await manager.start_scanning()

        mock_scanner.start.assert_called_once()
        assert manager._scanner_running is True

    @pytest.mark.asyncio
    @patch('nuki.BleakScanner')
    async def test_start_scanning_already_running(self, mock_scanner_class):
        """Test start_scanning when scanner is already running."""
        mock_scanner = AsyncMock()
        mock_scanner.start = AsyncMock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)
        manager._scanner = mock_scanner
        manager._scanner_running = True

        await manager.start_scanning()

        # Should not call start() again
        mock_scanner.start.assert_not_called()

    @pytest.mark.skip(reason="Recovery mechanism uses subprocess and os imports inside function - too complex to mock")
    @pytest.mark.asyncio
    async def test_start_scanning_recovery_from_stale_state(self):
        """Test scanner recovery when BlueZ has stale scan using kernel module reload."""
        # This test is skipped because the recovery mechanism imports subprocess and os
        # inside the function, making it difficult to mock properly without invasive changes.
        # The recovery mechanism is tested manually on actual hardware.
        pass

    @pytest.mark.asyncio
    @patch('nuki.BleakScanner')
    async def test_stop_scanning_success(self, mock_scanner_class):
        """Test successful scanner stop."""
        mock_scanner = AsyncMock()
        mock_scanner.stop = AsyncMock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)
        manager._scanner = mock_scanner
        manager._scanner_running = True

        await manager.stop_scanning()

        mock_scanner.stop.assert_called_once()
        assert manager._scanner_running is False

    @pytest.mark.asyncio
    @patch('nuki.BleakScanner')
    async def test_stop_scanning_not_running(self, mock_scanner_class):
        """Test stop_scanning when scanner is not running."""
        mock_scanner = AsyncMock()
        mock_scanner.stop = AsyncMock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)
        manager._scanner = mock_scanner
        manager._scanner_running = False

        await manager.stop_scanning()

        # Should not call stop()
        mock_scanner.stop.assert_not_called()

    @pytest.mark.asyncio
    @patch('nuki.BleakScanner')
    async def test_scanning_prevents_concurrent_starts(self, mock_scanner_class):
        """Test that concurrent start_scanning calls are serialized."""
        mock_scanner = AsyncMock()

        async def slow_start():
            await asyncio.sleep(0.2)

        mock_scanner.start = AsyncMock(side_effect=slow_start)
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)
        manager._scanner = mock_scanner

        # Start two scanning operations concurrently
        task1 = asyncio.create_task(manager.start_scanning())
        await asyncio.sleep(0.05)  # Let first acquire lock
        task2 = asyncio.create_task(manager.start_scanning())

        await asyncio.gather(task1, task2)

        # Only one call to start() should have been made (second was skipped)
        assert mock_scanner.start.call_count == 1


class TestNukiManagerCallbacks:
    """Test newstate callback mechanism."""

    @patch('nuki.BleakScanner')
    def test_newstate_callback_property(self, mock_scanner_class):
        """Test newstate_callback getter/setter."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        assert manager.newstate_callback is None

        callback = Mock()
        manager.newstate_callback = callback

        assert manager.newstate_callback == callback

    @pytest.mark.asyncio
    @patch('nuki.BleakScanner')
    async def test_nuki_newstate_invokes_callback(self, mock_scanner_class):
        """Test that nuki_newstate invokes registered callback."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        callback = AsyncMock()
        manager._newstate_callback = callback

        mock_nuki = Mock(spec=Nuki)
        await manager.nuki_newstate(mock_nuki)

        callback.assert_called_once_with(mock_nuki)

    @pytest.mark.asyncio
    @patch('nuki.BleakScanner')
    async def test_nuki_newstate_no_callback(self, mock_scanner_class):
        """Test nuki_newstate when no callback is registered."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)
        manager._newstate_callback = None

        mock_nuki = Mock(spec=Nuki)
        # Should not raise exception
        await manager.nuki_newstate(mock_nuki)


class TestNukiManagerIterator:
    """Test manager iteration over devices."""

    @patch('nuki.BleakScanner')
    def test_manager_iteration(self, mock_scanner_class):
        """Test iterating over manager yields devices."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        nuki1 = Mock(spec=Nuki)
        nuki1.address = "11:22:33:44:55:66"

        nuki2 = Mock(spec=Nuki)
        nuki2.address = "aa:bb:cc:dd:ee:ff"

        manager.add_nuki(nuki1)
        manager.add_nuki(nuki2)

        # Iterate using device_list (manager doesn't implement __iter__)
        devices = list(manager.device_list)
        assert len(devices) == 2
        assert nuki1 in devices
        assert nuki2 in devices

    @patch('nuki.BleakScanner')
    def test_manager_empty_iteration(self, mock_scanner_class):
        """Test iterating over manager with no devices."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        devices = list(manager.device_list)
        assert devices == []


class TestNukiManagerClientCreation:
    """Test BleakClient creation."""

    @patch('nuki.BleakScanner')
    @patch('nuki.BleakClient')
    def test_get_client_default(self, mock_client_class, mock_scanner_class):
        """Test get_client creates BleakClient with correct parameters."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123, adapter="hci0")

        address = "aa:bb:cc:dd:ee:ff"
        client = manager.get_client(address)

        mock_client_class.assert_called_once_with(
            address,
            adapter="hci0",
            timeout=None
        )

    @patch('nuki.BleakScanner')
    @patch('nuki.BleakClient')
    def test_get_client_with_timeout(self, mock_client_class, mock_scanner_class):
        """Test get_client with custom timeout."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123, adapter="hci1")

        address = "11:22:33:44:55:66"
        client = manager.get_client(address, timeout=15)

        mock_client_class.assert_called_once_with(
            address,
            adapter="hci1",
            timeout=15
        )


class TestDetectedIBeaconCallback:
    """Test iBeacon detection callback."""

    @pytest.mark.asyncio
    async def test_detected_ibeacon_known_device(self):
        """Test iBeacon callback for registered device."""
        manager = NukiManager(name="TestBridge", app_id=123)

        mock_nuki = AsyncMock(spec=Nuki)
        mock_nuki.address = "aa:bb:cc:dd:ee:ff"
        mock_nuki.device_type = DeviceType.SMARTLOCK_1_2
        mock_nuki.last_state = {"lock_state": "LOCKED"}
        mock_nuki.config = {"id": 12345}
        mock_nuki.set_ble_device = Mock()
        mock_nuki.update_state = AsyncMock()
        mock_nuki.get_config = AsyncMock()
        mock_nuki._user_command_in_progress = False  # Required for iBeacon callback

        manager.add_nuki(mock_nuki)

        # Mock BLE device and advertisement data
        mock_device = Mock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"  # Uppercase (will be lowercased)
        mock_device.rssi = -65

        mock_adv_data = Mock()
        mock_adv_data.manufacturer_data = {
            76: bytes([0x02] + [0x00] * 23)  # iBeacon format, not HomeKit
        }

        await manager._detected_ibeacon(mock_device, mock_adv_data)

        # Verify device was updated
        mock_nuki.set_ble_device.assert_called_once_with(mock_device)
        assert mock_nuki.rssi == -65

    @pytest.mark.asyncio
    async def test_detected_ibeacon_unknown_device(self):
        """Test iBeacon callback for unregistered device."""
        manager = NukiManager(name="TestBridge", app_id=123)

        mock_device = Mock()
        mock_device.address = "99:88:77:66:55:44"  # Not registered
        mock_device.rssi = -70

        mock_adv_data = Mock()
        mock_adv_data.manufacturer_data = {
            76: bytes([0x02] + [0x00] * 23)
        }

        # Should not raise exception, just ignore
        await manager._detected_ibeacon(mock_device, mock_adv_data)

    @pytest.mark.asyncio
    async def test_detected_ibeacon_homekit_ignored(self):
        """Test that HomeKit advertisements are ignored."""
        manager = NukiManager(name="TestBridge", app_id=123)

        mock_nuki = AsyncMock(spec=Nuki)
        mock_nuki.address = "aa:bb:cc:dd:ee:ff"
        mock_nuki.set_ble_device = Mock()

        manager.add_nuki(mock_nuki)

        mock_device = Mock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"
        mock_device.rssi = -65

        # HomeKit advertisement (first byte != 0x02)
        mock_adv_data = Mock()
        mock_adv_data.manufacturer_data = {
            76: bytes([0x06] + [0x00] * 23)  # HomeKit
        }

        await manager._detected_ibeacon(mock_device, mock_adv_data)

        # Should not call set_ble_device (ignored)
        mock_nuki.set_ble_device.assert_not_called()

    @pytest.mark.asyncio
    async def test_detected_ibeacon_skips_update_when_user_command_in_progress(self):
        """Test that iBeacon callback skips update_state when user command is in progress."""
        manager = NukiManager(name="TestBridge", app_id=123)

        mock_nuki = AsyncMock(spec=Nuki)
        mock_nuki.address = "aa:bb:cc:dd:ee:ff"
        mock_nuki.device_type = DeviceType.SMARTLOCK_1_2
        mock_nuki.last_state = None  # Would normally trigger update_state
        mock_nuki.config = {"id": 12345}
        mock_nuki.set_ble_device = Mock()
        mock_nuki.update_state = AsyncMock()
        mock_nuki._user_command_in_progress = True  # User command in progress

        manager.add_nuki(mock_nuki)

        mock_device = Mock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"
        mock_device.rssi = -65

        mock_adv_data = Mock()
        mock_adv_data.manufacturer_data = {
            76: bytes([0x02] + [0x00] * 23)
        }

        await manager._detected_ibeacon(mock_device, mock_adv_data)

        # Device should be updated but update_state should NOT be called
        mock_nuki.set_ble_device.assert_called_once()
        mock_nuki.update_state.assert_not_called()


class TestNukiManagerHealthMonitor:
    """Test health monitoring functionality."""

    @pytest.mark.asyncio
    @patch('nuki.BleakScanner')
    async def test_start_health_monitor(self, mock_scanner_class):
        """Test starting the health monitor."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        assert manager._health_check_task is None

        manager.start_health_monitor()

        assert manager._health_check_task is not None
        assert not manager._health_check_task.done()

        # Cleanup
        manager._health_check_task.cancel()
        try:
            await manager._health_check_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    @patch('nuki.BleakScanner')
    async def test_start_health_monitor_already_running(self, mock_scanner_class):
        """Test that starting health monitor twice doesn't create duplicate tasks."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        manager.start_health_monitor()
        first_task = manager._health_check_task

        manager.start_health_monitor()
        second_task = manager._health_check_task

        # Should be the same task
        assert first_task is second_task

        # Cleanup
        manager._health_check_task.cancel()
        try:
            await manager._health_check_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    @patch('nuki.BleakScanner')
    async def test_stop_health_monitor(self, mock_scanner_class):
        """Test stopping the health monitor."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        manager.start_health_monitor()
        assert manager._health_check_task is not None

        await manager.stop_health_monitor()

        assert manager._health_check_task is None

    @pytest.mark.asyncio
    @patch('nuki.BleakScanner')
    async def test_stop_health_monitor_when_not_running(self, mock_scanner_class):
        """Test stopping health monitor when it's not running."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        # Should not raise exception
        await manager.stop_health_monitor()

        assert manager._health_check_task is None


class TestNukiManagerScannerTracking:
    """Test scanner creation time tracking."""

    @patch('nuki.BleakScanner')
    def test_scanner_created_time_initialized(self, mock_scanner_class):
        """Test that scanner creation time is set on init."""
        import datetime
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        before = datetime.datetime.now()
        manager = NukiManager(name="TestBridge", app_id=123)
        after = datetime.datetime.now()

        assert manager._scanner_created_time is not None
        assert before <= manager._scanner_created_time <= after

    @patch('nuki.BleakScanner')
    def test_last_device_seen_time_initially_none(self, mock_scanner_class):
        """Test that last device seen time is None initially."""
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)

        assert manager._last_device_seen_time is None

    @pytest.mark.asyncio
    async def test_detected_ibeacon_updates_last_seen_time(self):
        """Test that detecting a device updates last_device_seen_time."""
        import datetime
        manager = NukiManager(name="TestBridge", app_id=123)

        mock_nuki = AsyncMock(spec=Nuki)
        mock_nuki.address = "aa:bb:cc:dd:ee:ff"
        mock_nuki.device_type = DeviceType.SMARTLOCK_1_2
        mock_nuki.last_state = {"lock_state": "LOCKED"}
        mock_nuki.config = {"id": 12345}
        mock_nuki.set_ble_device = Mock()
        mock_nuki._user_command_in_progress = False

        manager.add_nuki(mock_nuki)

        assert manager._last_device_seen_time is None

        mock_device = Mock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"
        mock_device.rssi = -65

        mock_adv_data = Mock()
        mock_adv_data.manufacturer_data = {
            76: bytes([0x02] + [0x00] * 23)
        }

        before = datetime.datetime.now()
        await manager._detected_ibeacon(mock_device, mock_adv_data)
        after = datetime.datetime.now()

        assert manager._last_device_seen_time is not None
        assert before <= manager._last_device_seen_time <= after

    @pytest.mark.asyncio
    async def test_detected_ibeacon_resets_stale_count(self):
        """Test that detecting a device resets the stale counter."""
        manager = NukiManager(name="TestBridge", app_id=123)

        mock_nuki = AsyncMock(spec=Nuki)
        mock_nuki.address = "aa:bb:cc:dd:ee:ff"
        mock_nuki.device_type = DeviceType.SMARTLOCK_1_2
        mock_nuki.last_state = {"lock_state": "LOCKED"}
        mock_nuki.config = {"id": 12345}
        mock_nuki.set_ble_device = Mock()
        mock_nuki._user_command_in_progress = False

        manager.add_nuki(mock_nuki)

        # Set stale count to non-zero
        manager._scanner_stale_count = 2

        mock_device = Mock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"
        mock_device.rssi = -65

        mock_adv_data = Mock()
        mock_adv_data.manufacturer_data = {
            76: bytes([0x02] + [0x00] * 23)
        }

        await manager._detected_ibeacon(mock_device, mock_adv_data)

        # Stale count should be reset
        assert manager._scanner_stale_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
