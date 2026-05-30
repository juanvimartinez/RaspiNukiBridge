import asyncio
import datetime
import hashlib
import logging
import struct
import hmac
import enum
import binascii
import random

import nacl.utils
import nacl.secret
from nacl.bindings.crypto_box import crypto_box_beforenm
from bleak import BleakScanner, BleakClient

BLE_SMARTLOCK_PAIRING_SERVICE = "a92ee100-5501-11e4-916c-0800200c9a66"
BLE_SMARTLOCK_CHAR = "a92ee202-5501-11e4-916c-0800200c9a66"
BLE_SMARTLOCK_PAIRING_CHAR = 'a92ee101-5501-11e4-916c-0800200c9a66'

BLE_OPENER_PAIRING_SERVICE = "a92ae100-5501-11e4-916c-0800200c9a66"
BLE_OPENER_CHAR = "a92ae202-5501-11e4-916c-0800200c9a66"
BLE_OPENER_PAIRING_CHAR = 'a92ae101-5501-11e4-916c-0800200c9a66'


class BridgeType(enum.Enum):
    HW = 1
    SW = 2


class DeviceType(enum.Enum):
    SMARTLOCK_1_2 = 0
    OPENER = 2
    SMARTDOOR = 3
    SMARTLOCK_3 = 4


class DoorsensorState(enum.Enum):
    UNAVAILABLE = 0
    DEACTIVATED = 1
    DOOR_CLOSED = 2
    DOOR_OPENED = 3
    DOOR_STATE_UNKOWN = 4
    CALIBRATING = 5
    UNCALIBRATED = 16
    REMOVED = 240
    UNKOWN = 255


class StatusCode(enum.Enum):
    COMPLETED = 0
    ACCEPTED = 1


class NukiCommand(enum.Enum):
    REQUEST_DATA = 0x0001
    PUBLIC_KEY = 0x0003
    CHALLENGE = 0x0004
    AUTH_AUTHENTICATOR = 0x0005
    AUTH_DATA = 0x0006
    AUTH_ID = 0x0007
    KEYTURNER_STATES = 0x000C
    LOCK_ACTION = 0x000D
    STATUS = 0x000E
    ERROR_REPORT = 0x0012
    REQUEST_CONFIG = 0x0014
    CONFIG = 0x0015
    AUTH_ID_CONFIRM = 0x001E


class NukiState(enum.Enum):
    UNINITIALIZED = 0x00
    PAIRING_MODE = 0x01
    DOOR_MODE = 0x02
    CONTINUOUS_MODE = 0x03
    MAINTENANCE_MODE = 0x04


class LockState(enum.Enum):
    UNCALIBRATED = 0x00
    LOCKED = 0x01
    UNLOCKING = 0x02
    UNLOCKED = 0x03
    LOCKING = 0x04
    UNLATCHED = 0x05
    UNLOCKED_LOCK_N_GO = 0x06
    UNLATCHING = 0x07
    CALIBRATION = 0xFC
    BOOT_RUN = 0xFD
    MOTOR_BLOCKED = 0xFE
    UNDEFINED = 0xFF


class OpenerState(enum.Enum):
    UNCALIBRATED = 0x00
    LOCKED = 0x01
    RTO_ACTIVE = 0x03
    OPEN = 0x05
    OPENING = 0x07
    UNDEFINED = 0xFF


class NukiAction(enum.Enum):
    NONE = 0x00
    UNLOCK = 0x01
    LOCK = 0x02
    UNLATCH = 0x03
    LOCK_N_GO = 0x04
    LOCK_N_GO_UNLATCH = 0x05
    FULL_LOCK = 0x06
    FOB_ACTION_1 = 0x81
    FOB_ACTION_2 = 0x82
    FOB_ACTION_3 = 0x83


class NukiClientType(enum.Enum):
    APP = 0x00
    BRIDGE = 0x01
    FOB = 0x02
    KEYPAD = 0x03


logger = logging.getLogger("raspinukibridge")


class NukiManager:

    def __init__(self, name, app_id, adapter="hci0"):
        self.name = name
        self.app_id = app_id
        self.type_id = NukiClientType.BRIDGE
        self._newstate_callback = None

        self._adapter = adapter
        self._devices = {}
        self._scanner = BleakScanner(adapter=self._adapter)
        self._scanner.register_detection_callback(self._detected_ibeacon)
        self._scanner_lock = asyncio.Lock()
        self._scanner_running = False

    async def initialize(self):
        """Initialize scanner state - stop any existing scans from previous runs"""
        logger.info("Initializing scanner - cleaning up any stale BlueZ state")

        # Try multiple times to stop any existing scan
        for attempt in range(3):
            try:
                await self._scanner.stop()
                logger.info(f"Stopped existing scanner from previous run (attempt {attempt + 1})")
                # Wait for BlueZ to fully release the scan
                await asyncio.sleep(1.0)
                break
            except Exception as e:
                if attempt < 2:
                    logger.debug(f"Attempt {attempt + 1} to stop scanner: {e}, retrying...")
                    await asyncio.sleep(0.5)
                else:
                    # Last attempt failed - no scan was running (expected on clean start)
                    logger.debug(f"No existing scan to stop (expected on first/clean run): {e}")

        # Ensure our state matches reality
        self._scanner_running = False
        logger.debug("Scanner initialization complete")

    @property
    def newstate_callback(self):
        return self._newstate_callback

    @newstate_callback.setter
    def newstate_callback(self, value):
        self._newstate_callback = value
        for device in self._devices.values():
            asyncio.get_event_loop().create_task(self.newstate_callback(device))

    async def nuki_newstate(self, nuki):
        if self.newstate_callback:
            await self.newstate_callback(nuki)

    def get_client(self, address, timeout=None):
        return BleakClient(address, adapter=self._adapter, timeout=timeout)

    def __getitem__(self, index):
        return list(self._devices.values())[index]

    def nuki_by_id(self, nuki_id):
        return next(nuki for nuki in self._devices.values() if nuki.config.get("id") == nuki_id)

    def add_nuki(self, nuki: 'Nuki'):
        nuki.manager = self
        self._devices[nuki.address] = nuki

    @property
    def device_list(self):
        return list(self._devices.values())

    async def start_scanning(self):
        async with self._scanner_lock:
            if self._scanner_running:
                logger.debug("Scanner already running, skipping start")
                return
            logger.info("Start scanning")
            try:
                await self._scanner.start()
                self._scanner_running = True
                logger.debug("Scanner started successfully")
            except Exception as e:
                # Check if scan is already in progress from previous run
                if "InProgress" in str(e) or "Already" in str(e):
                    logger.warning(f"Scanner already active in BlueZ (from previous run?), attempting aggressive recovery: {e}")

                    # AGGRESSIVE RECOVERY: Multiple attempts with increasing delays
                    for attempt in range(3):
                        try:
                            # Try to stop any existing scan
                            await self._scanner.stop()
                            logger.info(f"Stopped stale scanner (recovery attempt {attempt + 1}/3)")

                            # Wait longer for BlueZ to fully release the scan
                            # Increase delay with each attempt: 1s, 2s, 3s
                            delay = (attempt + 1) * 1.0
                            await asyncio.sleep(delay)

                            # Try starting again
                            await self._scanner.start()
                            self._scanner_running = True
                            logger.info(f"Scanner recovered and restarted successfully (attempt {attempt + 1})")
                            return  # Success!

                        except Exception as recovery_error:
                            logger.warning(f"Recovery attempt {attempt + 1}/3 failed: {recovery_error}")
                            if attempt < 2:
                                # Wait before next attempt
                                await asyncio.sleep(1.0)

                    # All recovery attempts failed - NUCLEAR OPTION: Recreate scanner object
                    logger.error("All recovery attempts failed, recreating scanner object (nuclear option)")
                    try:
                        # Recreate the scanner from scratch
                        old_scanner = self._scanner
                        self._scanner = BleakScanner(adapter=self._adapter)
                        self._scanner.register_detection_callback(self._detected_ibeacon)

                        # Clean up old scanner reference
                        del old_scanner

                        # Give BlueZ time to settle after object recreation
                        await asyncio.sleep(2.0)

                        # Try starting the new scanner
                        await self._scanner.start()
                        self._scanner_running = True
                        logger.info("Scanner recreated and started successfully (nuclear option succeeded)")

                    except Exception as nuclear_error:
                        logger.error(f"Nuclear option failed: {nuclear_error}")
                        # Don't mark as running - it's genuinely broken
                        self._scanner_running = False
                        logger.error("Scanner is in broken state. Manual Bluetooth restart may be required.")
                        raise
                else:
                    logger.error(f"Failed to start scanner: {e}")
                    raise

    async def stop_scanning(self):
        async with self._scanner_lock:
            if not self._scanner_running:
                logger.debug("Scanner not running, skipping stop")
                return
            logger.info("Stop scanning")
            try:
                await self._scanner.stop()
                logger.debug("Scanner stopped successfully")
            except Exception as e:
                logger.warning(f"Scanner stop error (ignored): {e}")
            finally:
                self._scanner_running = False

    async def _detected_ibeacon(self, device, advertisement_data):
        device_address = device.address.lower()
        if device_address in self._devices:
            manufacturer_data = advertisement_data.manufacturer_data[76]
            if manufacturer_data[0] != 0x02:
                # Ignore HomeKit advertisement
                return
            logger.info(f"Nuki: {device_address}, RSSI: {device.rssi} {advertisement_data}")
            tx_p = manufacturer_data[-1]
            nuki = self._devices[device_address]
            nuki.set_ble_device(device)
            nuki.rssi = device.rssi
            if not nuki.device_type:
                try:
                    await nuki.connect()  # this will force the identification of the device type
                except Exception as e:
                    logger.error(f"Connect failed during beacon detection: {e}")
                    # Don't restart scanner here - connect() cleanup will handle it
                    return
            if not nuki.last_state or tx_p & 0x1:
                await nuki.update_state()
            elif not nuki.config:
                await nuki.get_config()


class Nuki:

    def __init__(self, address, auth_id, nuki_public_key, bridge_public_key, bridge_private_key):
        self.address = address
        self.auth_id = auth_id
        self.nuki_public_key = nuki_public_key
        self.bridge_public_key = bridge_public_key
        self.bridge_private_key = bridge_private_key
        self.manager = None
        self.id = None
        self.name = None
        self.rssi = None
        self.last_state = None
        self.config = {}

        self._device_type = None
        self._pairing_handle = None
        self._client = None
        self._challenge_command = None
        self._pairing_callback = None
        self._command_timeout_task = None
        self._reset_opener_state_task = None
        self.retry = 3
        self.connection_timeout = 10
        self.command_timeout = 30

        # Connection state management
        self._connection_lock = asyncio.Lock()
        self._is_connecting = False
        self._is_disconnecting = False

        # Command queue for sequential execution
        self._command_queue = asyncio.Queue()
        self._command_worker_task = None

        self._BLE_CHAR = None
        self._BLE_PAIRING_CHAR = None

        if nuki_public_key and bridge_private_key:
            self._create_shared_key()

    @property
    def device_type(self):
        return self._device_type
    
    @device_type.setter
    def device_type(self, device_type: DeviceType):
        if device_type == DeviceType.OPENER:
            self._BLE_PAIRING_CHAR = BLE_OPENER_PAIRING_CHAR
            self._BLE_CHAR = BLE_OPENER_CHAR
        else:
            self._BLE_PAIRING_CHAR = BLE_SMARTLOCK_PAIRING_CHAR
            self._BLE_CHAR = BLE_SMARTLOCK_CHAR
        self._device_type = device_type
        logger.info(f"Device type: {self.device_type}")

    def _create_shared_key(self):
        self._shared_key = crypto_box_beforenm(self.nuki_public_key, self.bridge_private_key)
        self._box = nacl.secret.SecretBox(self._shared_key)

    @property
    def is_battery_critical(self):
        return bool(self.last_state["critical_battery_state"] & 1)

    @property
    def is_battery_charging(self):
        return bool(self.last_state["critical_battery_state"] & 2)

    @property
    def battery_percentage(self):
        return ((self.last_state["critical_battery_state"] & 252) >> 2) * 2

    @staticmethod
    def _prepare_command(cmd_code: int, payload=bytes()):
        message = cmd_code.to_bytes(2, "little") + payload
        crc = binascii.crc_hqx(message, 0xffff).to_bytes(2, "little")
        message += crc
        return message

    def _encrypt_command(self, cmd_code: int, payload=bytes()):
        unencrypted = self.auth_id + self._prepare_command(cmd_code, payload)[:-2]
        crc = binascii.crc_hqx(unencrypted, 0xffff).to_bytes(2, "little")
        unencrypted += crc
        nonce = nacl.utils.random(24)
        encrypted = self._box.encrypt(unencrypted, nonce)[24:]
        length = len(encrypted).to_bytes(2, "little")
        message = nonce + self.auth_id + length + encrypted
        return message

    def _decrypt_command(self, data):
        nonce = data[:24]
        auth_id, length = struct.unpack("<IH", data[24:30])
        encrypted = nonce + data[30:30 + length]
        decrypted = self._box.decrypt(encrypted)
        return decrypted[4:]

    async def _parse_command(self, data):
        command, = struct.unpack("<H", data[:2])
        command = NukiCommand(command)
        #crc = data[-2:]
        data = data[2:-2]
        logger.debug(f"Parsing command: {command}, data: {data}")

        if command == NukiCommand.CHALLENGE:
            return command, {"nonce": data}

        elif self.device_type != DeviceType.OPENER and command == NukiCommand.KEYTURNER_STATES:
            values = struct.unpack("<BBBHBBBBBHBBBBBBBH", data[:21])
            return command, {"nuki_state": NukiState(values[0]),
                             "lock_state": LockState(values[1]),
                             "trigger": values[2],
                             "current_time": datetime.datetime(values[3], values[4], values[5],
                                                               values[6], values[7], values[8]),
                             "timezone_offset": values[9],
                             "critical_battery_state": values[10],
                             "current_update_count": values[11],
                             "lock_n_go_timer": values[12],
                             "last_lock_action": NukiAction(values[13]),
                             "last_lock_action_trigger": values[14],
                             "last_lock_action_completion_status": values[15],
                             "door_sensor_state": DoorsensorState(values[16]),
                             "nightmode_active": values[17],
                             # "accessory_battery_state": values[18],  # It doesn't exist?
                             }
        elif self.device_type == DeviceType.OPENER and command == NukiCommand.KEYTURNER_STATES:
            values = struct.unpack("<BBBHBBBBBHBBBBBBBH", data[:21])
            return command, {"nuki_state": NukiState(values[0]),
                             "lock_state": OpenerState(values[1]),
                             "trigger": values[2],
                             "current_time": datetime.datetime(values[3], values[4], values[5],
                                                               values[6], values[7], values[8]),
                             "timezone_offset": values[9],
                             "critical_battery_state": values[10],
                             "current_update_count": values[11],
                             "ring_to_open_timer": values[12],
                             "last_lock_action": NukiAction(values[13]),
                             "last_lock_action_trigger": values[14],
                             "last_lock_action_completion_status": values[15],
                             "door_sensor_state": DoorsensorState(values[16]),
                             "nightmode_active": values[17],
                             # "accessory_battery_state": values[18],  # It doesn't exist?
                             }
        elif self.device_type != DeviceType.OPENER and command == NukiCommand.CONFIG and len(data) == 72:
            values = struct.unpack("<I32sffBBBBBHBBBBBhBBBBBBBBBBBBBB", data)
            return command, {"id": values[0],
                             "name": values[1].split(b"\x00")[0].decode(),
                             "latitude": values[2],
                             "longitude": values[3],
                             "auto_unlatch": values[4],
                             "pairing_enabled": values[5],
                             "button_enabled": values[6],
                             "led_enabled": values[7],
                             "led_brightness": values[8],
                             "current_time": datetime.datetime(values[9], values[10], values[11],
                                                               values[12], values[13], values[14]),
                             "timezone_offset": values[15],
                             "dst_mode": values[16],
                             "has_fob": values[17],
                             "fob_action_1": values[18],
                             "fob_action_2": values[19],
                             "fob_action_3": values[20],
                             "single_lock": values[21],
                             "advertising_mode": values[22],
                             "has_keypad": values[23],
                             "firmware_version": f"{values[24]}.{values[25]}.{values[26]}",
                             "hardware_revision": f"{values[27]}.{values[28]}",
                             "homekit_status": values[29],
                             }
        elif self.device_type != DeviceType.OPENER and command == NukiCommand.CONFIG:
            values = struct.unpack("<I32sffBBBBBHBBBBBhBBBBBBBBBBBBBBH", data[:74])
            return command, {"id": values[0],
                             "name": values[1].split(b"\x00")[0].decode(),
                             "latitude": values[2],
                             "longitude": values[3],
                             "auto_unlatch": values[4],
                             "pairing_enabled": values[5],
                             "button_enabled": values[6],
                             "led_enabled": values[7],
                             "led_brightness": values[8],
                             "current_time": datetime.datetime(values[9], values[10], values[11],
                                                               values[12], values[13], values[14]),
                             "timezone_offset": values[15],
                             "dst_mode": values[16],
                             "has_fob": values[17],
                             "fob_action_1": values[18],
                             "fob_action_2": values[19],
                             "fob_action_3": values[20],
                             "single_lock": values[21],
                             "advertising_mode": values[22],
                             "has_keypad": values[23],
                             "firmware_version": f"{values[24]}.{values[25]}.{values[26]}",
                             "hardware_revision": f"{values[27]}.{values[28]}",
                             "homekit_status": values[29],
                             "timezone_id": values[30],
                             }

        elif self.device_type == DeviceType.OPENER and command == NukiCommand.CONFIG:
            values = struct.unpack("<I32sffBBBBHBBBBBhBBBBBBBBBBBBBH", data[:72])
            return command, {"id": values[0],
                             "name": values[1].split(b"\x00")[0].decode(),
                             "latitude": values[2],
                             "longitude": values[3],
                             "auto_unlatch": values[4],
                             "pairing_enabled": values[5],
                             "button_enabled": values[6],
                             "led_enabled": values[7],
                             "current_time": datetime.datetime(values[8], values[9], values[10],
                                                               values[11], values[12], values[13]),
                             "timezone_offset": values[14],
                             "dst_mode": values[15],
                             "has_fob": values[16],
                             "fob_action_1": values[17],
                             "fob_action_2": values[18],
                             "fob_action_3": values[19],
                             "operating_mode": values[20],
                             "advertising_mode": values[21],
                             "has_keypad": values[22],
                             "firmware_version": f"{values[23]}.{values[24]}.{values[25]}",
                             "hardware_revision": f"{values[26]}.{values[27]}",
                             "timezone_id": values[28],
                             }

        elif command == NukiCommand.PUBLIC_KEY:
            return command, {"public_key": data}

        elif command == NukiCommand.AUTH_ID:
            values = struct.unpack("<32s4s16s32s", data[:84])
            return command, {"authenticator": values[0],
                             "auth_id": values[1],
                             "uuuid": values[2],
                             "nonce": values[3]}

        elif command == NukiCommand.STATUS:
            status, = struct.unpack('<B', data[:1])
            return command, {"status": StatusCode(status)}

        elif command == NukiCommand.ERROR_REPORT:
            data, _cmd = struct.unpack('<bH', data[:3])
            return command, data

        return None, None

    async def reset_opener_state(self):
        await asyncio.sleep(30)
        self.last_state["last_lock_action_completion_status"] = 0
        if self.config and self.last_state:
            await self.manager.nuki_newstate(self)

    def set_ble_device(self, ble_device):
        self._client = BleakClient(ble_device)
        return self._client

    async def _notification_handler(self, sender, data):
        logger.debug(f"Notification handler: {sender}, data: {data}")
        if sender == self._client.services[self._BLE_PAIRING_CHAR].handle:
            # The pairing handler is not encrypted
            command, data = await self._parse_command(bytes(data))
        else:
            uncrypted = self._decrypt_command(bytes(data))
            command, data = await self._parse_command(uncrypted)

        if command == NukiCommand.ERROR_REPORT:
            logger.error(f"Error {data}")
            await self.disconnect()

        if command == NukiCommand.KEYTURNER_STATES:
            update_config = not self.config or (self.last_state["current_update_count"] != data["current_update_count"])
            self.last_state = data
            logger.info(f"State: {self.last_state}")
            if self._challenge_command == NukiCommand.KEYTURNER_STATES:
                if update_config:
                    await self.get_config()
                else:
                    await self.disconnect()
            if self.config and self.last_state:
                await self.manager.nuki_newstate(self)
            if self.device_type == DeviceType.OPENER and self.last_state["last_lock_action_completion_status"]:
                self._reset_opener_state_task = asyncio.create_task(self.reset_opener_state())

        elif command == NukiCommand.CONFIG:
            self.config = data
            logger.info(f"Config: {self.config}")
            await self.disconnect()
            if self.config and self.last_state:
                await self.manager.nuki_newstate(self)

        elif command == NukiCommand.PUBLIC_KEY:
            self.nuki_public_key = data["public_key"]
            self._create_shared_key()
            logger.info(f"Nuki {self.address} public key: {self.nuki_public_key.hex()}")
            self._challenge_command = NukiCommand.PUBLIC_KEY
            cmd = self._prepare_command(NukiCommand.PUBLIC_KEY.value, self.bridge_public_key)
            await self._send_data(self._BLE_PAIRING_CHAR, cmd)

        elif command == NukiCommand.AUTH_ID:
            self.auth_id = data["auth_id"]
            value_r = self.auth_id + data["nonce"]
            payload = hmac.new(self._shared_key, msg=value_r, digestmod=hashlib.sha256).digest()
            payload += self.auth_id
            self._challenge_command = NukiCommand.AUTH_ID_CONFIRM
            cmd = self._prepare_command(NukiCommand.AUTH_ID_CONFIRM.value, payload)
            await self._send_data(self._BLE_PAIRING_CHAR, cmd)

        elif command == NukiCommand.STATUS:
            logger.error(f"Last action: {data}")
            if self._challenge_command == NukiCommand.AUTH_ID_CONFIRM:
                if self._pairing_callback:
                    self._pairing_callback(self)
                    self._pairing_callback = None
            if data["status"] == StatusCode.COMPLETED:
                await self.disconnect()

        elif command == NukiCommand.CHALLENGE and self._challenge_command:
            logger.debug(f"Challenge for {self._challenge_command}")
            if self._challenge_command == NukiCommand.REQUEST_CONFIG:
                cmd = self._encrypt_command(NukiCommand.REQUEST_CONFIG.value, data["nonce"])
                await self._send_data(self._BLE_CHAR, cmd)

            elif self._challenge_command in NukiAction:
                lock_action = self._challenge_command.value.to_bytes(1, "little")
                app_id = self.manager.app_id.to_bytes(4, "little")
                flags = 0
                payload = lock_action + app_id + flags.to_bytes(1, "little") + data["nonce"]
                cmd = self._encrypt_command(NukiCommand.LOCK_ACTION.value, payload)
                await self._send_data(self._BLE_CHAR, cmd)

            elif self._challenge_command == NukiCommand.PUBLIC_KEY:
                value_r = self.bridge_public_key + self.nuki_public_key + data["nonce"]
                payload = hmac.new(self._shared_key, msg=value_r, digestmod=hashlib.sha256).digest()
                self._challenge_command = NukiCommand.AUTH_AUTHENTICATOR
                cmd = self._prepare_command(NukiCommand.AUTH_AUTHENTICATOR.value, payload)
                await self._send_data(self._BLE_PAIRING_CHAR, cmd)

            elif self._challenge_command == NukiCommand.AUTH_AUTHENTICATOR:
                app_id = self.manager.app_id.to_bytes(4, "little")
                type_id = self.manager.type_id.value.to_bytes(1, "little")
                name = self.manager.name.encode("utf-8").ljust(32, b"\0")
                nonce = nacl.utils.random(32)
                value_r = type_id + app_id + name + nonce + data["nonce"]
                payload = hmac.new(self._shared_key, msg=value_r, digestmod=hashlib.sha256).digest()
                payload += type_id + app_id + name + nonce
                self._challenge_command = NukiCommand.AUTH_DATA
                cmd = self._prepare_command(NukiCommand.AUTH_DATA.value, payload)
                await self._send_data(self._BLE_PAIRING_CHAR, cmd)

    async def _send_data(self, characteristic, data):
        # Sometimes the connection to the smartlock fails, retry with exponential backoff
        # For sleeping devices, we need to be more patient
        max_retries = max(self.retry, 5)  # At least 5 retries for sleeping devices

        for attempt in range(max_retries):
            try:
                if not self._client or not self._client.is_connected:
                    await self.connect()
                if characteristic is None:
                    characteristic = self._BLE_CHAR
                logger.debug(f"Sending data to {characteristic}: {data}")
                await self._client.write_gatt_char(characteristic, data)
                return  # Success
            except Exception as exc:
                logger.error(f"Send data attempt {attempt+1}/{max_retries} failed: {type(exc).__name__}: {exc}")

                # Check if it's a "device not found" error (sleeping device)
                if "could not be found" in str(exc).lower() or "not found" in str(exc).lower():
                    if attempt < max_retries - 1:
                        # Device is likely in sleep mode - wait longer for it to wake up
                        # The scanner should eventually detect it when it advertises
                        delay = min(5 + (attempt * 3), 20)  # 5s, 8s, 11s, 14s, 17s, 20s
                        logger.info(f"Device appears to be sleeping. Waiting {delay}s for device to wake up and advertise...")

                        # Ensure scanner is running to detect when device wakes up
                        try:
                            await self.manager.start_scanning()
                        except Exception as scanner_error:
                            logger.warning(f"Failed to ensure scanner is running: {scanner_error}")

                        await asyncio.sleep(delay)
                elif attempt < max_retries - 1:
                    # Other errors - use exponential backoff with jitter
                    delay = min(2 ** attempt + random.uniform(0, 1), 10)
                    logger.info(f"Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(f"All {max_retries} send attempts failed, disconnecting")
        await self.disconnect()
        raise Exception(f"Failed to send data after {max_retries} retries - device may be in deep sleep or out of range")

    async def _safe_start_notify(self, *args):
        try:
            await self._client.start_notify(*args)
        # This exception might occur due to Bluez downgrade required for Pi 3B+ and Pi 4. See this comment:
        # https://github.com/dauden1184/RaspiNukiBridge/issues/1#issuecomment-1103969957
        # Haven't researched further the reason and consequences of this exception
        except EOFError:
            logger.info("EOFError during notification")

    async def connect(self):
        logger.debug(f"Connect called, acquiring lock... (connected: {self._client.is_connected if self._client else False})")
        async with self._connection_lock:
            if self._is_connecting:
                logger.debug("Connect already in progress, waiting...")
                return  # Another coroutine is handling this
            if self._client and self._client.is_connected:
                logger.debug("Already connected")
                return

            self._is_connecting = True
            logger.info(f"Nuki connecting to {self.address}")
            try:
                if not self._client:
                    self._client = self.manager.get_client(self.address, timeout=self.connection_timeout)

                await self.manager.stop_scanning()
                await self._client.connect()

                logger.debug(f"Services {[str(s) for s in self._client.services]}")
                logger.debug(f"Characteristics {[str(v) for v in self._client.services.characteristics.values()]}")

                if not self.device_type:
                    services = await self._client.get_services()
                    if services.get_characteristic(BLE_OPENER_PAIRING_CHAR):
                        self.device_type = DeviceType.OPENER
                    else:
                        self.device_type = DeviceType.SMARTLOCK_1_2

                await self._safe_start_notify(self._BLE_PAIRING_CHAR, self._notification_handler)
                await self._safe_start_notify(self._BLE_CHAR, self._notification_handler)

                logger.info("Connected")

                # Cancel any existing timeout task before creating new one
                if self._command_timeout_task:
                    self._command_timeout_task.cancel()
                self._command_timeout_task = asyncio.create_task(self._start_cmd_timeout())

            except Exception as e:
                logger.error(f"Connect failed: {e}")

                # If device not found, it's likely sleeping - ensure scanner is actively looking
                if "could not be found" in str(e).lower() or "not found" in str(e).lower():
                    logger.warning("Device not found - likely in sleep mode. Ensuring scanner is running to detect wake-up...")

                # Ensure scanner restarts on failure to keep looking for the device
                await self.manager.start_scanning()
                raise
            finally:
                self._is_connecting = False
                logger.debug("Connect lock released")

    async def _start_cmd_timeout(self):
        await asyncio.sleep(self.command_timeout)
        logger.info("Connection timeout")
        await self.disconnect()

    async def _command_worker(self):
        """Process commands sequentially from queue"""
        logger.info("Command worker started")
        while True:
            try:
                logger.debug(f"Command queue size: {self._command_queue.qsize()}")
                command_func, args, result_future = await self._command_queue.get()
                logger.debug(f"Processing command: {command_func.__name__}")
                try:
                    result = await command_func(*args)
                    if not result_future.done():
                        result_future.set_result(result)
                    logger.debug(f"Command {command_func.__name__} completed successfully")
                except Exception as e:
                    logger.error(f"Command {command_func.__name__} failed: {e}")
                    if not result_future.done():
                        result_future.set_exception(e)
                finally:
                    self._command_queue.task_done()
            except asyncio.CancelledError:
                logger.info("Command worker cancelled")
                break
            except Exception as e:
                logger.error(f"Command worker error: {e}")

    async def _queue_command(self, command_func, *args):
        """Queue a command for sequential execution"""
        if not self._command_worker_task or self._command_worker_task.done():
            logger.debug("Starting command worker task")
            self._command_worker_task = asyncio.create_task(self._command_worker())

        queue_size = self._command_queue.qsize()
        logger.debug(f"Queueing command {command_func.__name__}, queue size before: {queue_size}")
        result_future = asyncio.get_event_loop().create_future()
        await self._command_queue.put((command_func, args, result_future))
        return await result_future

    async def disconnect(self):
        logger.debug("Disconnect called, acquiring lock...")
        async with self._connection_lock:
            if self._is_disconnecting:
                logger.debug("Disconnect already in progress")
                return
            if not self._client or not self._client.is_connected:
                logger.debug("Already disconnected")
                return

            self._is_disconnecting = True
            logger.info(f"Nuki disconnecting from {self.address}")
            try:
                if self._command_timeout_task:
                    self._command_timeout_task.cancel()
                    self._command_timeout_task = None

                await self._client.disconnect()
                logger.info("Disconnect completed")

            except Exception as e:
                logger.error(f"Disconnect error: {e}")
            finally:
                self._is_disconnecting = False
                logger.debug("Disconnect lock released")
                # Always restart scanning after disconnect (success or failure)
                await self.manager.start_scanning()

    async def cleanup(self):
        """Clean shutdown: cancel tasks and disconnect"""
        logger.info(f"Cleaning up Nuki {self.address}")

        if self._command_worker_task:
            self._command_worker_task.cancel()
            try:
                await self._command_worker_task
            except asyncio.CancelledError:
                pass

        if self._reset_opener_state_task:
            self._reset_opener_state_task.cancel()

        if self._client and self._client.is_connected:
            await self.disconnect()

    async def update_state(self):
        return await self._queue_command(self._update_state_impl)

    async def _update_state_impl(self):
        logger.info("Updating nuki state")
        self._challenge_command = NukiCommand.KEYTURNER_STATES
        payload = NukiCommand.KEYTURNER_STATES.value.to_bytes(2, "little")
        cmd = self._encrypt_command(NukiCommand.REQUEST_DATA.value, payload)
        await self._send_data(self._BLE_CHAR, cmd)

    async def lock(self):
        return await self._queue_command(self._lock_impl)

    async def _lock_impl(self):
        logger.info("Locking nuki")
        self._challenge_command = NukiAction.LOCK
        payload = NukiCommand.CHALLENGE.value.to_bytes(2, "little")
        cmd = self._encrypt_command(NukiCommand.REQUEST_DATA.value, payload)
        await self._send_data(self._BLE_CHAR, cmd)

    async def unlock(self):
        return await self._queue_command(self._unlock_impl)

    async def _unlock_impl(self):
        logger.info("Unlocking")
        self._challenge_command = NukiAction.UNLOCK
        payload = NukiCommand.CHALLENGE.value.to_bytes(2, "little")
        cmd = self._encrypt_command(NukiCommand.REQUEST_DATA.value, payload)
        await self._send_data(self._BLE_CHAR, cmd)

    async def unlatch(self):
        return await self._queue_command(self._unlatch_impl)

    async def _unlatch_impl(self):
        self._challenge_command = NukiAction.UNLATCH
        payload = NukiCommand.CHALLENGE.value.to_bytes(2, "little")
        cmd = self._encrypt_command(NukiCommand.REQUEST_DATA.value, payload)
        await self._send_data(self._BLE_CHAR, cmd)

    async def lock_action(self, action):
        return await self._queue_command(self._lock_action_impl, action)

    async def _lock_action_impl(self, action):
        logger.info(f"Lock action {action}")
        self._challenge_command = NukiAction(action)
        payload = NukiCommand.CHALLENGE.value.to_bytes(2, "little")
        cmd = self._encrypt_command(NukiCommand.REQUEST_DATA.value, payload)
        await self._send_data(self._BLE_CHAR, cmd)

    async def get_config(self):
        return await self._queue_command(self._get_config_impl)

    async def _get_config_impl(self):
        logger.info("Retrieve nuki configuration")
        self._challenge_command = NukiCommand.REQUEST_CONFIG
        payload = NukiCommand.CHALLENGE.value.to_bytes(2, "little")
        cmd = self._encrypt_command(NukiCommand.REQUEST_DATA.value, payload)
        await self._send_data(self._BLE_CHAR, cmd)

    async def pair(self, callback):
        self._pairing_callback = callback
        self._challenge_command = NukiCommand.PUBLIC_KEY
        payload = NukiCommand.PUBLIC_KEY.value.to_bytes(2, "little")
        cmd = self._prepare_command(NukiCommand.REQUEST_DATA.value, payload)
        await self.connect()
        await self._send_data(self._BLE_PAIRING_CHAR, cmd)
