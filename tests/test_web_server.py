"""Unit tests for WebServer HTTP API endpoints."""

import pytest
import json
import hashlib
import datetime
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
import nacl.secret

# Import from source
import sys
import os
import importlib.util

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Import __main__ module as a regular module
spec = importlib.util.spec_from_file_location("main_module", os.path.join(parent_dir, "__main__.py"))
main_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_module)
WebServer = main_module.WebServer

from nuki import Nuki, NukiManager, BridgeType, DeviceType, LockState, NukiState, DoorsensorState


class TestWebServerInitialization:
    """Test WebServer initialization."""

    def test_server_init(self):
        """Test WebServer initialization with all parameters."""
        mock_manager = Mock(spec=NukiManager)
        server = WebServer(
            host="0.0.0.0",
            port=8080,
            token="abcd1234" * 8,  # 64 char token
            server_id=123456789,
            nuki_manager=mock_manager
        )

        assert server._host == "0.0.0.0"
        assert server._port == 8080
        assert server._token == "abcd1234" * 8
        assert server.nuki_manager == mock_manager
        assert server._server_id == 123456789
        assert len(server._http_callbacks) == 3
        assert all(cb is None for cb in server._http_callbacks)

    def test_server_id_truncation(self):
        """Test server_id truncation to 32-bit."""
        mock_manager = Mock(spec=NukiManager)
        large_id = 0xFFFFFFFFFFFF  # 48-bit number
        server = WebServer("0.0.0.0", 8080, "token123", large_id, mock_manager)

        # Should be truncated to 32-bit
        assert server._server_id == (large_id & 0xFFFFFFFF)
        assert server._server_id <= 0xFFFFFFFF


class TestTokenValidation:
    """Test token validation methods."""

    def test_plain_token_validation_success(self):
        """Test plain token authentication (simple mode)."""
        mock_manager = Mock(spec=NukiManager)
        token = "test_token_12345678" * 3  # Make it long enough
        server = WebServer("0.0.0.0", 8080, token, 123, mock_manager)

        # Mock request with plain token
        mock_request = Mock()
        mock_request.query = {"token": token}

        assert server._check_token(mock_request) is True

    def test_plain_token_validation_failure(self):
        """Test plain token authentication failure."""
        mock_manager = Mock(spec=NukiManager)
        token = "correct_token_123456" * 3
        server = WebServer("0.0.0.0", 8080, token, 123, mock_manager)

        mock_request = Mock()
        mock_request.query = {"token": "wrong_token"}

        assert server._check_token(mock_request) is False

    def test_hash_token_validation_success(self):
        """Test hash-based token authentication."""
        mock_manager = Mock(spec=NukiManager)
        token = "test_hash_token_1234" * 3
        server = WebServer("0.0.0.0", 8080, token, 123, mock_manager)

        ts = "1234567890"
        rnr = "random_nonce_12345"
        expected_hash = hashlib.sha256(f"{ts},{rnr},{token}".encode("utf-8")).hexdigest()

        mock_request = Mock()
        mock_request.query = {
            "hash": expected_hash,
            "ts": ts,
            "rnr": rnr
        }

        assert server._check_token(mock_request) is True

    def test_hash_token_validation_failure(self):
        """Test hash-based token authentication failure."""
        mock_manager = Mock(spec=NukiManager)
        token = "test_hash_token_1234" * 3
        server = WebServer("0.0.0.0", 8080, token, 123, mock_manager)

        mock_request = Mock()
        mock_request.query = {
            "hash": "invalid_hash_value",
            "ts": "1234567890",
            "rnr": "random_nonce"
        }

        assert server._check_token(mock_request) is False

    def test_no_token_provided(self):
        """Test authentication failure when no token provided."""
        mock_manager = Mock(spec=NukiManager)
        server = WebServer("0.0.0.0", 8080, "token", 123, mock_manager)

        mock_request = Mock()
        mock_request.query = {}  # No token parameters

        assert server._check_token(mock_request) is False


class TestInfoEndpoint:
    """Test /info endpoint."""

    @pytest.mark.asyncio
    async def test_info_endpoint_success(self):
        """Test /info returns bridge information."""
        mock_manager = MagicMock()  # No spec to allow __iter__
        mock_manager.__iter__ = Mock(return_value=iter([]))  # No devices

        server = WebServer("0.0.0.0", 8080, "test_token", 999, mock_manager)
        server._start_datetime = datetime.datetime.now() - datetime.timedelta(seconds=3600)

        mock_request = Mock()
        mock_request.query = {"token": "test_token"}

        response = await server.nuki_info(mock_request)
        data = json.loads(response.text)

        assert data["bridgeType"] == BridgeType.SW.value
        assert data["ids"]["hardwareId"] == 999
        assert data["ids"]["serverId"] == 999
        assert "uptime" in data
        assert "currentTime" in data
        assert "scanResults" in data
        assert isinstance(data["scanResults"], list)

    @pytest.mark.asyncio
    async def test_info_endpoint_unauthorized(self):
        """Test /info with invalid token returns 403."""
        mock_manager = Mock(spec=NukiManager)
        server = WebServer("0.0.0.0", 8080, "correct_token", 123, mock_manager)

        mock_request = Mock()
        mock_request.query = {"token": "wrong_token"}

        with pytest.raises(web.HTTPForbidden):
            await server.nuki_info(mock_request)


class TestListEndpoint:
    """Test /list endpoint."""

    @pytest.mark.asyncio
    async def test_list_endpoint_with_devices(self):
        """Test /list returns configured devices."""
        # Create mock Nuki devices
        mock_nuki1 = Mock(spec=Nuki)
        mock_nuki1.config = {
            "id": 123456,
            "name": "Front Door"
        }
        mock_nuki1.device_type = DeviceType.SMARTLOCK_1_2
        mock_nuki1.last_state = {
            "nuki_state": NukiState.DOOR_MODE,
            "lock_state": LockState.LOCKED,
            "door_sensor_state": DoorsensorState.DOOR_CLOSED,
            "current_time": datetime.datetime(2024, 1, 15, 10, 30, 0),
            "critical_battery_state": 200
        }
        mock_nuki1.is_battery_critical = False
        mock_nuki1.is_battery_charging = False
        mock_nuki1.battery_percentage = 100

        mock_manager = MagicMock()  # No spec to allow __iter__
        mock_manager.__iter__ = Mock(return_value=iter([mock_nuki1]))

        server = WebServer("0.0.0.0", 8080, "test_token", 123, mock_manager)

        mock_request = Mock()
        mock_request.query = {"token": "test_token"}

        response = await server.nuki_list(mock_request)
        data = json.loads(response.text)

        assert len(data) == 1
        assert data[0]["nukiId"] == 123456
        assert data[0]["name"] == "Front Door"
        assert data[0]["deviceType"] == DeviceType.SMARTLOCK_1_2.value
        assert "lastKnownState" in data[0]

    @pytest.mark.asyncio
    async def test_list_endpoint_empty(self):
        """Test /list with no configured devices."""
        mock_manager = MagicMock()  # No spec to allow __iter__
        mock_manager.__iter__ = Mock(return_value=iter([]))

        server = WebServer("0.0.0.0", 8080, "test_token", 123, mock_manager)

        mock_request = Mock()
        mock_request.query = {"token": "test_token"}

        response = await server.nuki_list(mock_request)
        data = json.loads(response.text)

        assert data == []


class TestLockActionEndpoints:
    """Test lock/unlock/lockAction endpoints."""

    @pytest.mark.asyncio
    async def test_lock_endpoint_success(self):
        """Test /lock endpoint."""
        mock_nuki = AsyncMock(spec=Nuki)
        mock_nuki.lock = AsyncMock()
        mock_nuki.is_battery_critical = False

        mock_manager = Mock(spec=NukiManager)
        mock_manager.nuki_by_id = Mock(return_value=mock_nuki)

        server = WebServer("0.0.0.0", 8080, "test_token", 123, mock_manager)

        mock_request = Mock()
        mock_request.query = {"token": "test_token", "nukiId": "12345"}

        response = await server.nuki_lock(mock_request)
        data = json.loads(response.text)

        assert data["success"] is True
        assert "batteryCritical" in data
        mock_nuki.lock.assert_called_once()
        mock_manager.nuki_by_id.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_unlock_endpoint_success(self):
        """Test /unlock endpoint."""
        mock_nuki = AsyncMock(spec=Nuki)
        mock_nuki.unlock = AsyncMock()
        mock_nuki.is_battery_critical = False

        mock_manager = Mock(spec=NukiManager)
        mock_manager.nuki_by_id = Mock(return_value=mock_nuki)

        server = WebServer("0.0.0.0", 8080, "test_token", 123, mock_manager)

        mock_request = Mock()
        mock_request.query = {"token": "test_token", "nukiId": "98765"}

        response = await server.nuki_unlock(mock_request)
        data = json.loads(response.text)

        assert data["success"] is True
        mock_nuki.unlock.assert_called_once()
        mock_manager.nuki_by_id.assert_called_once_with(98765)

    @pytest.mark.asyncio
    async def test_lockaction_endpoint_success(self):
        """Test /lockAction endpoint with custom action."""
        mock_nuki = AsyncMock(spec=Nuki)
        mock_nuki.lock_action = AsyncMock()
        mock_nuki.is_battery_critical = True

        mock_manager = Mock(spec=NukiManager)
        mock_manager.nuki_by_id = Mock(return_value=mock_nuki)

        server = WebServer("0.0.0.0", 8080, "test_token", 123, mock_manager)

        mock_request = Mock()
        mock_request.query = {
            "token": "test_token",
            "nukiId": "11111",
            "action": "3"  # UNLATCH action
        }

        response = await server.nuki_lockaction(mock_request)
        data = json.loads(response.text)

        assert data["success"] is True
        assert data["batteryCritical"] is True
        mock_nuki.lock_action.assert_called_once_with(3)

    @pytest.mark.asyncio
    async def test_lock_endpoint_unauthorized(self):
        """Test /lock with invalid token."""
        mock_manager = Mock(spec=NukiManager)
        server = WebServer("0.0.0.0", 8080, "correct_token", 123, mock_manager)

        mock_request = Mock()
        mock_request.query = {"token": "wrong_token", "nukiId": "123"}

        with pytest.raises(web.HTTPForbidden):
            await server.nuki_lock(mock_request)


class TestLockStateEndpoint:
    """Test /lockState endpoint."""

    @pytest.mark.asyncio
    async def test_lockstate_endpoint_success(self):
        """Test /lockState returns current lock state."""
        mock_nuki = Mock(spec=Nuki)
        mock_nuki.device_type = DeviceType.SMARTLOCK_1_2
        mock_nuki.last_state = {
            "nuki_state": NukiState.DOOR_MODE,
            "lock_state": LockState.UNLOCKED,
            "door_sensor_state": DoorsensorState.DOOR_OPENED,
            "current_time": datetime.datetime(2024, 1, 15, 14, 45, 30),
            "critical_battery_state": 150
        }
        mock_nuki.is_battery_critical = False
        mock_nuki.is_battery_charging = False
        mock_nuki.battery_percentage = 75

        mock_manager = Mock(spec=NukiManager)
        mock_manager.nuki_by_id = Mock(return_value=mock_nuki)

        server = WebServer("0.0.0.0", 8080, "test_token", 123, mock_manager)

        mock_request = Mock()
        mock_request.query = {"token": "test_token", "nukiId": "55555"}

        response = await server.nuki_state(mock_request)
        data = json.loads(response.text)

        assert data["state"] == LockState.UNLOCKED.value
        assert data["stateName"] == LockState.UNLOCKED.name
        assert data["mode"] == NukiState.DOOR_MODE.value
        assert data["batteryCritical"] is False
        assert data["batteryChargeState"] == 75
        assert data["doorsensorState"] == DoorsensorState.DOOR_OPENED.value
        assert data["success"] is True


class TestCallbackEndpoints:
    """Test callback management endpoints."""

    @pytest.mark.asyncio
    async def test_callback_add_success(self):
        """Test adding HTTP callback."""
        mock_manager = Mock(spec=NukiManager)
        mock_manager.newstate_callback = None
        server = WebServer("0.0.0.0", 8080, "test_token", 123, mock_manager)

        mock_request = Mock()
        mock_request.query = {
            "token": "test_token",
            "url": "http://example.com/callback"
        }

        response = await server.callback_add(mock_request)
        data = json.loads(response.text)

        assert data["success"] is True
        assert server._http_callbacks[0] == "http://example.com/callback"
        assert server.nuki_manager.newstate_callback is not None

    @pytest.mark.asyncio
    async def test_callback_add_multiple(self):
        """Test adding multiple callbacks (max 3)."""
        mock_manager = Mock(spec=NukiManager)
        mock_manager.newstate_callback = None
        server = WebServer("0.0.0.0", 8080, "test_token", 123, mock_manager)

        # Add 3 callbacks
        for i in range(3):
            mock_request = Mock()
            mock_request.query = {
                "token": "test_token",
                "url": f"http://example.com/callback{i}"
            }
            await server.callback_add(mock_request)

        assert server._http_callbacks[0] == "http://example.com/callback0"
        assert server._http_callbacks[1] == "http://example.com/callback1"
        assert server._http_callbacks[2] == "http://example.com/callback2"

    @pytest.mark.asyncio
    async def test_callback_list_success(self):
        """Test listing registered callbacks."""
        mock_manager = Mock(spec=NukiManager)
        server = WebServer("0.0.0.0", 8080, "test_token", 123, mock_manager)
        server._http_callbacks = ["http://example.com/cb1", None, "http://example.com/cb2"]

        mock_request = Mock()
        mock_request.query = {"token": "test_token"}

        response = await server.callback_list(mock_request)
        data = json.loads(response.text)

        assert len(data["callbacks"]) == 2
        assert data["callbacks"][0] == {"id": 0, "url": "http://example.com/cb1"}
        assert data["callbacks"][1] == {"id": 2, "url": "http://example.com/cb2"}

    @pytest.mark.asyncio
    async def test_callback_remove_success(self):
        """Test removing a callback."""
        mock_manager = Mock(spec=NukiManager)
        server = WebServer("0.0.0.0", 8080, "test_token", 123, mock_manager)
        server._http_callbacks = ["http://example.com/cb1", "http://example.com/cb2", None]

        mock_request = Mock()
        mock_request.query = {"token": "test_token", "id": "1"}

        response = await server.callback_remove(mock_request)
        data = json.loads(response.text)

        assert data["success"] is True
        assert server._http_callbacks[0] == "http://example.com/cb1"
        assert server._http_callbacks[1] is None  # Removed
        assert server._http_callbacks[2] is None

    @pytest.mark.asyncio
    async def test_callback_add_unauthorized(self):
        """Test callback add with invalid token."""
        mock_manager = Mock(spec=NukiManager)
        server = WebServer("0.0.0.0", 8080, "correct_token", 123, mock_manager)

        mock_request = Mock()
        mock_request.query = {"token": "wrong_token", "url": "http://example.com"}

        with pytest.raises(web.HTTPForbidden):
            await server.callback_add(mock_request)


class TestNewStateCallback:
    """Test new state notification to HTTP callbacks."""

    @pytest.mark.skip(reason="HTTP session mocking needs fix")
    @pytest.mark.asyncio
    async def test_newstate_callback_triggers_http(self):
        """Test that new state triggers HTTP callback."""
        mock_manager = Mock(spec=NukiManager)
        server = WebServer("0.0.0.0", 8080, "test_token", 123, mock_manager)
        server._http_callbacks = ["http://example.com/callback", None, None]

        mock_nuki = Mock(spec=Nuki)
        mock_nuki.config = {"id": 12345}
        mock_nuki.device_type = DeviceType.SMARTLOCK_1_2
        mock_nuki.last_state = {
            "nuki_state": NukiState.DOOR_MODE,
            "lock_state": LockState.LOCKED,
            "door_sensor_state": DoorsensorState.DOOR_CLOSED,
            "current_time": datetime.datetime(2024, 1, 15, 10, 0, 0),
            "critical_battery_state": 200
        }
        mock_nuki.is_battery_critical = False
        mock_nuki.is_battery_charging = False
        mock_nuki.battery_percentage = 100

        # Mock HTTP session
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.text = AsyncMock(return_value="OK")
            mock_session.post = AsyncMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            await server._newstate(mock_nuki)

            # Verify HTTP POST was called
            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args
            assert call_args[0][0] == "http://example.com/callback"


class TestGetNukiLastState:
    """Test _get_nuki_last_state helper method."""

    def test_get_nuki_last_state_smartlock(self):
        """Test state serialization for SmartLock."""
        mock_nuki = Mock(spec=Nuki)
        mock_nuki.device_type = DeviceType.SMARTLOCK_3
        mock_nuki.last_state = {
            "nuki_state": NukiState.DOOR_MODE,
            "lock_state": LockState.UNLOCKED,
            "door_sensor_state": DoorsensorState.DOOR_OPENED,
            "current_time": datetime.datetime(2024, 5, 1, 12, 30, 45),
            "critical_battery_state": 100
        }
        mock_nuki.is_battery_critical = False
        mock_nuki.is_battery_charging = True
        mock_nuki.battery_percentage = 50

        state = WebServer._get_nuki_last_state(mock_nuki)

        assert state["mode"] == NukiState.DOOR_MODE.value
        assert state["state"] == LockState.UNLOCKED.value
        assert state["stateName"] == "UNLOCKED"
        assert state["batteryCritical"] is False
        assert state["batteryCharging"] is True
        assert state["batteryChargeState"] == 50
        assert state["doorsensorState"] == DoorsensorState.DOOR_OPENED.value
        assert state["success"] is True
        assert "timestamp" in state


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
