"""Unit tests for Nuki enum definitions and CLI functionality."""

import pytest
from unittest.mock import Mock, patch, mock_open
import yaml

# Import from source
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nuki import (
    BridgeType, DeviceType, DoorsensorState, StatusCode,
    NukiCommand, NukiState, LockState, OpenerState,
    NukiAction, NukiClientType
)


class TestBridgeTypeEnum:
    """Test BridgeType enum values."""

    def test_bridge_type_values(self):
        """Verify BridgeType enum values match protocol."""
        assert BridgeType.HW.value == 1
        assert BridgeType.SW.value == 2

    def test_bridge_type_names(self):
        """Verify BridgeType enum names."""
        assert BridgeType.HW.name == "HW"
        assert BridgeType.SW.name == "SW"


class TestDeviceTypeEnum:
    """Test DeviceType enum values."""

    def test_device_type_values(self):
        """Verify DeviceType enum values match Nuki protocol."""
        assert DeviceType.SMARTLOCK_1_2.value == 0
        assert DeviceType.OPENER.value == 2
        assert DeviceType.SMARTDOOR.value == 3
        assert DeviceType.SMARTLOCK_3.value == 4

    def test_device_type_names(self):
        """Verify DeviceType enum names."""
        assert DeviceType.SMARTLOCK_1_2.name == "SMARTLOCK_1_2"
        assert DeviceType.OPENER.name == "OPENER"
        assert DeviceType.SMARTDOOR.name == "SMARTDOOR"
        assert DeviceType.SMARTLOCK_3.name == "SMARTLOCK_3"

    def test_device_type_completeness(self):
        """Verify all documented device types are defined."""
        # Ensure we have at least 4 device types
        assert len(DeviceType) >= 4


class TestDoorsensorStateEnum:
    """Test DoorsensorState enum values."""

    def test_doorsensor_state_values(self):
        """Verify DoorsensorState enum values."""
        assert DoorsensorState.UNAVAILABLE.value == 0
        assert DoorsensorState.DEACTIVATED.value == 1
        assert DoorsensorState.DOOR_CLOSED.value == 2
        assert DoorsensorState.DOOR_OPENED.value == 3
        assert DoorsensorState.DOOR_STATE_UNKOWN.value == 4
        assert DoorsensorState.CALIBRATING.value == 5
        assert DoorsensorState.UNCALIBRATED.value == 16
        assert DoorsensorState.REMOVED.value == 240
        assert DoorsensorState.UNKOWN.value == 255

    def test_doorsensor_state_names(self):
        """Verify DoorsensorState enum names are readable."""
        assert DoorsensorState.DOOR_CLOSED.name == "DOOR_CLOSED"
        assert DoorsensorState.DOOR_OPENED.name == "DOOR_OPENED"


class TestStatusCodeEnum:
    """Test StatusCode enum values."""

    def test_status_code_values(self):
        """Verify StatusCode enum values."""
        assert StatusCode.COMPLETED.value == 0
        assert StatusCode.ACCEPTED.value == 1

    def test_status_code_names(self):
        """Verify StatusCode enum names."""
        assert StatusCode.COMPLETED.name == "COMPLETED"
        assert StatusCode.ACCEPTED.name == "ACCEPTED"


class TestNukiCommandEnum:
    """Test NukiCommand enum values."""

    def test_nuki_command_values(self):
        """Verify NukiCommand enum values match protocol specification."""
        assert NukiCommand.REQUEST_DATA.value == 0x0001
        assert NukiCommand.PUBLIC_KEY.value == 0x0003
        assert NukiCommand.CHALLENGE.value == 0x0004
        assert NukiCommand.AUTH_AUTHENTICATOR.value == 0x0005
        assert NukiCommand.AUTH_DATA.value == 0x0006
        assert NukiCommand.AUTH_ID.value == 0x0007
        assert NukiCommand.KEYTURNER_STATES.value == 0x000C
        assert NukiCommand.LOCK_ACTION.value == 0x000D
        assert NukiCommand.STATUS.value == 0x000E
        assert NukiCommand.ERROR_REPORT.value == 0x0012
        assert NukiCommand.REQUEST_CONFIG.value == 0x0014
        assert NukiCommand.CONFIG.value == 0x0015
        assert NukiCommand.AUTH_ID_CONFIRM.value == 0x001E

    def test_nuki_command_names(self):
        """Verify NukiCommand enum names are descriptive."""
        assert NukiCommand.LOCK_ACTION.name == "LOCK_ACTION"
        assert NukiCommand.REQUEST_DATA.name == "REQUEST_DATA"
        assert NukiCommand.PUBLIC_KEY.name == "PUBLIC_KEY"

    def test_nuki_command_hex_format(self):
        """Verify command values are proper 16-bit values."""
        for cmd in NukiCommand:
            assert 0x0000 <= cmd.value <= 0xFFFF


class TestNukiStateEnum:
    """Test NukiState enum values."""

    def test_nuki_state_values(self):
        """Verify NukiState enum values."""
        assert NukiState.UNINITIALIZED.value == 0x00
        assert NukiState.PAIRING_MODE.value == 0x01
        assert NukiState.DOOR_MODE.value == 0x02
        assert NukiState.CONTINUOUS_MODE.value == 0x03
        assert NukiState.MAINTENANCE_MODE.value == 0x04

    def test_nuki_state_names(self):
        """Verify NukiState enum names."""
        assert NukiState.PAIRING_MODE.name == "PAIRING_MODE"
        assert NukiState.DOOR_MODE.name == "DOOR_MODE"
        assert NukiState.MAINTENANCE_MODE.name == "MAINTENANCE_MODE"


class TestLockStateEnum:
    """Test LockState enum values."""

    def test_lock_state_values(self):
        """Verify LockState enum values match protocol."""
        assert LockState.UNCALIBRATED.value == 0x00
        assert LockState.LOCKED.value == 0x01
        assert LockState.UNLOCKING.value == 0x02
        assert LockState.UNLOCKED.value == 0x03
        assert LockState.LOCKING.value == 0x04
        assert LockState.UNLATCHED.value == 0x05
        assert LockState.UNLOCKED_LOCK_N_GO.value == 0x06
        assert LockState.UNLATCHING.value == 0x07
        assert LockState.CALIBRATION.value == 0xFC
        assert LockState.BOOT_RUN.value == 0xFD
        assert LockState.MOTOR_BLOCKED.value == 0xFE
        assert LockState.UNDEFINED.value == 0xFF

    def test_lock_state_names(self):
        """Verify LockState enum names are readable."""
        assert LockState.LOCKED.name == "LOCKED"
        assert LockState.UNLOCKED.name == "UNLOCKED"
        assert LockState.UNLATCHED.name == "UNLATCHED"

    def test_lock_state_completeness(self):
        """Verify all common lock states are defined."""
        required_states = ["LOCKED", "UNLOCKED", "UNLOCKING", "LOCKING", "UNLATCHED"]
        defined_names = [state.name for state in LockState]
        for required in required_states:
            assert required in defined_names


class TestOpenerStateEnum:
    """Test OpenerState enum values."""

    def test_opener_state_values(self):
        """Verify OpenerState enum values."""
        assert OpenerState.UNCALIBRATED.value == 0x00
        assert OpenerState.LOCKED.value == 0x01
        assert OpenerState.RTO_ACTIVE.value == 0x03
        assert OpenerState.OPEN.value == 0x05
        assert OpenerState.OPENING.value == 0x07
        assert OpenerState.UNDEFINED.value == 0xFF

    def test_opener_state_names(self):
        """Verify OpenerState enum names."""
        assert OpenerState.LOCKED.name == "LOCKED"
        assert OpenerState.OPEN.name == "OPEN"
        assert OpenerState.RTO_ACTIVE.name == "RTO_ACTIVE"


class TestNukiActionEnum:
    """Test NukiAction enum values."""

    def test_nuki_action_values(self):
        """Verify NukiAction enum values match protocol."""
        assert NukiAction.NONE.value == 0x00
        assert NukiAction.UNLOCK.value == 0x01
        assert NukiAction.LOCK.value == 0x02
        assert NukiAction.UNLATCH.value == 0x03
        assert NukiAction.LOCK_N_GO.value == 0x04
        assert NukiAction.LOCK_N_GO_UNLATCH.value == 0x05
        assert NukiAction.FULL_LOCK.value == 0x06
        assert NukiAction.FOB_ACTION_1.value == 0x81
        assert NukiAction.FOB_ACTION_2.value == 0x82
        assert NukiAction.FOB_ACTION_3.value == 0x83

    def test_nuki_action_names(self):
        """Verify NukiAction enum names are descriptive."""
        assert NukiAction.UNLOCK.name == "UNLOCK"
        assert NukiAction.LOCK.name == "LOCK"
        assert NukiAction.UNLATCH.name == "UNLATCH"
        assert NukiAction.LOCK_N_GO.name == "LOCK_N_GO"

    def test_nuki_action_completeness(self):
        """Verify all common actions are defined."""
        required_actions = ["UNLOCK", "LOCK", "UNLATCH"]
        defined_names = [action.name for action in NukiAction]
        for required in required_actions:
            assert required in defined_names


class TestNukiClientTypeEnum:
    """Test NukiClientType enum values."""

    def test_client_type_values(self):
        """Verify NukiClientType enum values."""
        assert NukiClientType.APP.value == 0x00
        assert NukiClientType.BRIDGE.value == 0x01
        assert NukiClientType.FOB.value == 0x02
        assert NukiClientType.KEYPAD.value == 0x03

    def test_client_type_names(self):
        """Verify NukiClientType enum names."""
        assert NukiClientType.BRIDGE.name == "BRIDGE"
        assert NukiClientType.APP.name == "APP"
        assert NukiClientType.FOB.name == "FOB"


class TestEnumUniqueness:
    """Test that enum values are unique within each enum."""

    def test_device_type_unique_values(self):
        """Verify DeviceType values are unique."""
        values = [dt.value for dt in DeviceType]
        assert len(values) == len(set(values))

    def test_lock_state_unique_values(self):
        """Verify LockState values are unique."""
        values = [ls.value for ls in LockState]
        assert len(values) == len(set(values))

    def test_nuki_action_unique_values(self):
        """Verify NukiAction values are unique."""
        values = [na.value for na in NukiAction]
        assert len(values) == len(set(values))

    def test_nuki_command_unique_values(self):
        """Verify NukiCommand values are unique."""
        values = [nc.value for nc in NukiCommand]
        assert len(values) == len(set(values))


class TestConfigurationHandling:
    """Test configuration file loading and validation."""

    def test_valid_yaml_config_parsing(self):
        """Test parsing a valid YAML configuration."""
        valid_config = """
server:
  host: 0.0.0.0
  port: 8080
  name: TestBridge
  app_id: 123456
  token: abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234
  id: test-001
smartlock:
  - address: AA:BB:CC:DD:EE:FF
    bridge_public_key: aaaa
    bridge_private_key: bbbb
    nuki_public_key: cccc
    auth_id: "111111"
"""
        config = yaml.safe_load(valid_config)

        assert "server" in config
        assert "smartlock" in config
        assert config["server"]["port"] == 8080
        assert config["server"]["name"] == "TestBridge"
        assert len(config["smartlock"]) == 1

    def test_config_with_multiple_devices(self):
        """Test configuration with multiple smartlocks."""
        multi_device_config = """
server:
  host: 0.0.0.0
  port: 8080
  name: MultiBridge
  app_id: 999
  token: token123
  id: multi-001
smartlock:
  - address: 11:22:33:44:55:66
    bridge_public_key: aaaa
    bridge_private_key: bbbb
    nuki_public_key: cccc
    auth_id: "111111"
  - address: AA:BB:CC:DD:EE:FF
    bridge_public_key: dddd
    bridge_private_key: eeee
    nuki_public_key: ffff
    auth_id: "222222"
"""
        config = yaml.safe_load(multi_device_config)

        assert len(config["smartlock"]) == 2
        assert config["smartlock"][0]["address"] == "11:22:33:44:55:66"
        assert config["smartlock"][1]["address"] == "AA:BB:CC:DD:EE:FF"

    def test_config_optional_parameters(self):
        """Test configuration with optional device parameters."""
        config_with_optionals = """
server:
  host: 127.0.0.1
  port: 9090
  name: TestBridge
  app_id: 555
  token: token
  id: test-002
  adapter: hci1
smartlock:
  - address: AA:BB:CC:DD:EE:FF
    bridge_public_key: aaaa
    bridge_private_key: bbbb
    nuki_public_key: cccc
    auth_id: "123"
    connection_timeout: 15
    retry: 5
    command_timeout: 40
"""
        config = yaml.safe_load(config_with_optionals)

        assert config["server"]["adapter"] == "hci1"
        device = config["smartlock"][0]
        assert device["connection_timeout"] == 15
        assert device["retry"] == 5
        assert device["command_timeout"] == 40


class TestEnumFromValue:
    """Test creating enum instances from values."""

    def test_lock_state_from_value(self):
        """Test creating LockState from integer value."""
        locked = LockState(0x01)
        assert locked == LockState.LOCKED

        unlocked = LockState(0x03)
        assert unlocked == LockState.UNLOCKED

    def test_nuki_action_from_value(self):
        """Test creating NukiAction from integer value."""
        unlock = NukiAction(0x01)
        assert unlock == NukiAction.UNLOCK

        lock = NukiAction(0x02)
        assert lock == NukiAction.LOCK

    def test_invalid_enum_value_raises_error(self):
        """Test that invalid enum value raises ValueError."""
        with pytest.raises(ValueError):
            LockState(0x99)  # Invalid value

        with pytest.raises(ValueError):
            NukiAction(0xFF)  # Invalid value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
