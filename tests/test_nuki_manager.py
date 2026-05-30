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

    def test_manager_init(self):
        """Test NukiManager initialization with default parameters."""
        manager = NukiManager(name="TestBridge", app_id=123456)

        assert manager.name == "TestBridge"
        assert manager.app_id == 123456
        assert manager.type_id == NukiClientType.BRIDGE
        assert manager._adapter == "hci0"  # Default
        assert manager._devices == {}
        assert manager._scanner is not None
        assert manager._scanner_running is False
        assert manager._newstate_callback is None

    def test_manager_init_custom_adapter(self):
        """Test NukiManager with custom Bluetooth adapter."""
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

    def test_add_nuki_device(self):
        """Test adding a Nuki device to manager."""
        manager = NukiManager(name="TestBridge", app_id=123)

        mock_nuki = Mock(spec=Nuki)
        mock_nuki.address = "aa:bb:cc:dd:ee:ff"

        manager.add_nuki(mock_nuki)

        assert mock_nuki.address in manager._devices
        assert manager._devices[mock_nuki.address] == mock_nuki
        assert mock_nuki.manager == manager

    def test_add_multiple_devices(self):
        """Test adding multiple devices."""
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

    def test_nuki_by_id_lookup(self):
        """Test device lookup by Nuki ID."""
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

    def test_nuki_by_id_not_found(self):
        """Test device lookup with non-existent ID raises StopIteration."""
        manager = NukiManager(name="TestBridge", app_id=123)

        nuki = Mock(spec=Nuki)
        nuki.address = "11:22:33:44:55:66"
        nuki.config = {"id": 111111}
        manager.add_nuki(nuki)

        with pytest.raises(StopIteration):
            manager.nuki_by_id(999999)  # Non-existent ID

    def test_device_list_property(self):
        """Test device_list property returns all devices."""
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

    def test_manager_getitem(self):
        """Test indexing manager like a list."""
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
    async def test_initialize_cleans_stale_state(self, mock_scanner_class):
        """Test initialize() stops existing scans."""
        mock_scanner = AsyncMock()
        mock_scanner.stop = AsyncMock()
        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)
        manager._scanner = mock_scanner

        await manager.initialize()

        # Should attempt to stop scanner
        assert mock_scanner.stop.called
        assert manager._scanner_running is False

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

    @pytest.mark.asyncio
    @patch('nuki.BleakScanner')
    async def test_start_scanning_recovery_from_stale_state(self, mock_scanner_class):
        """Test scanner recovery when BlueZ has stale scan."""
        mock_scanner = AsyncMock()

        # First start attempt fails with "InProgress" error
        error_sequence = [Exception("org.bluez.Error.InProgress"), None]
        mock_scanner.start = AsyncMock(side_effect=error_sequence)
        mock_scanner.stop = AsyncMock()

        mock_scanner_class.return_value = mock_scanner

        manager = NukiManager(name="TestBridge", app_id=123)
        manager._scanner = mock_scanner

        await manager.start_scanning()

        # Should have attempted stop and restart
        assert mock_scanner.stop.called
        assert mock_scanner.start.call_count == 2
        assert manager._scanner_running is True

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

    def test_newstate_callback_property(self):
        """Test newstate_callback getter/setter."""
        manager = NukiManager(name="TestBridge", app_id=123)

        assert manager.newstate_callback is None

        callback = Mock()
        manager.newstate_callback = callback

        assert manager.newstate_callback == callback

    @pytest.mark.asyncio
    async def test_nuki_newstate_invokes_callback(self):
        """Test that nuki_newstate invokes registered callback."""
        manager = NukiManager(name="TestBridge", app_id=123)

        callback = AsyncMock()
        manager._newstate_callback = callback

        mock_nuki = Mock(spec=Nuki)
        await manager.nuki_newstate(mock_nuki)

        callback.assert_called_once_with(mock_nuki)

    @pytest.mark.asyncio
    async def test_nuki_newstate_no_callback(self):
        """Test nuki_newstate when no callback is registered."""
        manager = NukiManager(name="TestBridge", app_id=123)
        manager._newstate_callback = None

        mock_nuki = Mock(spec=Nuki)
        # Should not raise exception
        await manager.nuki_newstate(mock_nuki)


class TestNukiManagerIterator:
    """Test manager iteration over devices."""

    def test_manager_iteration(self):
        """Test iterating over manager yields devices."""
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

    def test_manager_empty_iteration(self):
        """Test iterating over manager with no devices."""
        manager = NukiManager(name="TestBridge", app_id=123)

        devices = list(manager.device_list)
        assert devices == []


class TestNukiManagerClientCreation:
    """Test BleakClient creation."""

    @patch('nuki.BleakClient')
    def test_get_client_default(self, mock_client_class):
        """Test get_client creates BleakClient with correct parameters."""
        manager = NukiManager(name="TestBridge", app_id=123, adapter="hci0")

        address = "aa:bb:cc:dd:ee:ff"
        client = manager.get_client(address)

        mock_client_class.assert_called_once_with(
            address,
            adapter="hci0",
            timeout=None
        )

    @patch('nuki.BleakClient')
    def test_get_client_with_timeout(self, mock_client_class):
        """Test get_client with custom timeout."""
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
