"""API for Alpicool fridges based on modern BLE protocol."""

import asyncio
import logging

from bleak import BleakClient
from bleak.exc import BleakError

from .const import FRIDGE_NOTIFY_UUID, FRIDGE_RW_CHARACTERISTIC_UUID, Request

_LOGGER = logging.getLogger(__name__)


def _to_signed_byte(b: int) -> int:
    """Convert an unsigned byte (0-255) to a signed byte (-128-127)."""
    return b - 256 if b > 127 else b


class FridgeApi:
    """A class to interact with the fridge."""

    def __init__(self, address: str) -> None:
        """Initialize the API."""
        self._lock = asyncio.Lock()
        
        # Initialisation avec des valeurs par défaut pour éviter le mode "Indisponible" dans HA
        self.status = {
            "locked": False,
            "powered_on": True,
            "run_mode": 0,
            "bat_saver": 0,
            "left_target": 0,
            "right_target": 0,
            "left_current": 0,
            "right_current": 0,
            "temp_max": 20,
            "temp_min": -20,
        }
        
        self._status_updated_event = asyncio.Event()
        self._bind_event = asyncio.Event()
        self._poll_task = None
        self._address = address
        self._client = BleakClient(self._address, timeout=30.0)
        self._write_requires_response = False
        # Buffer for reassembling fragmented packets
        self._notification_buffer = bytearray()
        self.is_available: bool = True
        self._last_successful_update_time: float = 0.0

    def set_initial_timestamp(self) -> None:
        """Set the initial timestamp after a successful setup."""
        self._last_successful_update_time = asyncio.get_running_loop().time()

    def _checksum(self, data: bytes) -> int:
        """Calculate 2-byte big endian checksum."""
        return sum(data) & 0xFFFF

    def _build_set_other_payload(self, new_values: dict) -> bytes:
        """Build the complete payload for the setOther command."""
        current_status = self.status.copy()
        current_status.update(new_values)

        def to_unsigned_byte(x: int) -> int:
            return x & 0xFF

        data = bytearray(
            [
                int(current_status.get("locked", 0)),
                int(current_status.get("powered_on", 1)),
                int(current_status.get("run_mode", 0)),
                int(current_status.get("bat_saver", 0)),
                to_unsigned_byte(current_status.get("left_target", 0)),
                to_unsigned_byte(current_status.get("temp_max", 20)),
                to_unsigned_byte(current_status.get("temp_min", -20)),
                to_unsigned_byte(current_status.get("left_ret_diff", 1)),
                int(current_status.get("start_delay", 0)),
                int(current_status.get("unit", 0)),
                to_unsigned_byte(current_status.get("left_tc_hot", 0)),
                to_unsigned_byte(current_status.get("left_tc_mid", 0)),
                to_unsigned_byte(current_status.get("left_tc_cold", 0)),
                to_unsigned_byte(current_status.get("left_tc_halt", 0)),
            ]
        )

        # Forcer l'envoi des octets Dual Zone si la clé ou l'appareil est double compartiment
        if "right_current" in current_status or "right_target" in current_status:
            right_zone_data = bytearray(
                [
                    to_unsigned_byte(current_status.get("right_target", 0)),
                    0,
                    0,
                    to_unsigned_byte(current_status.get("right_ret_diff", 1)),
                    to_unsigned_byte(current_status.get("right_tc_hot", 0)),
                    to_unsigned_byte(current_status.get("right_tc_mid", 0)),
                    to_unsigned_byte(current_status.get("right_tc_cold", 0)),
                    to_unsigned_byte(current_status.get("right_tc_halt", 0)),
                    0,
                    0,
                    0,
                ]
            )
            data.extend(right_zone_data)

        return data

    async def async_set_values(self, new_values: dict) -> None:
        """Public method to set configuration values."""
        if not self.status:
            _LOGGER.debug("Cannot set values, status is not available")
            return

        payload = self._build_set_other_payload(new_values)
        packet = self._build_packet(Request.SET, payload)
        await self._send_raw(packet)

    def _build_packet(self, cmd: int, data: bytes = b"") -> bytes:
        """Build a BLE command packet based on known working examples and protocol quirks."""
        if cmd == Request.BIND:
            return b"\xfe\xfe\x03\x00\x01\xff"
        if cmd == Request.QUERY:
            return b"\xfe\xfe\x03\x01\x02\x00"

        _LOGGER.debug("Using dynamic builder for cmd %s", cmd)

        header = b"\xfe\xfe"
        payload = bytearray([cmd])
        payload.extend(data)

        length = len(payload) + 2

        packet = bytearray(header)
        packet.append(length)
        packet.extend(payload)

        checksum = self._checksum(packet)
        packet.extend(checksum.to_bytes(2, "big"))

        _LOGGER.debug("Dynamically built packet for cmd %s: %s", cmd, packet.hex())
        return bytes(packet)

    async def async_set_temperature(self, zone: str, temp: int) -> None:
        """Public method to set the target temperature for a specific zone."""
        cmd = Request.SET_LEFT if zone == "left" else Request.SET_RIGHT
        payload = bytes([temp & 0xFF])

        packet = self._build_packet(cmd, payload)
        await self._send_raw(packet)

    def _decode_status(self, payload: bytes):
        """Decode query response payload for single or dual zone fridges."""
        try:
            base_status = {
                "locked": bool(payload[0]),
                "powered_on": bool(payload[1]),
                "run_mode": payload[2],
                "