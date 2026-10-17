"""Application service layer for validated staging controls."""

import math
from typing import Any

from .serial import SerialTransport
from .state import StateStore


class ControlService:
    def __init__(self, state: StateStore, serial: SerialTransport, device_id: str = "1") -> None:
        self.state = state
        self.serial = serial
        self.device_id = device_id

    def set_level(self, channel: int, level: float) -> None:
        if channel not in range(1, 5):
            raise ValueError("channel must be between 1 and 4")
        if not math.isfinite(level) or not -80.0 <= level <= 12.0:
            raise ValueError("level must be between -80 and 12 dB")
        if self.serial.connected:
            self.serial.send_cmd(f"/ID{self.device_id}/Out{channel}/Level {level:.1f}")
        self.state.update_channel(channel, level=level)

    def set_mute(self, channel: int, muted: bool) -> None:
        if channel not in range(1, 5):
            raise ValueError("channel must be between 1 and 4")
        if self.serial.connected:
            self.serial.send_cmd(f"/ID{self.device_id}/Out{channel}/Mute {int(muted)}")
        self.state.update_channel(channel, muted=muted)

    @staticmethod
    def validate_channel_payload(payload: dict[str, Any]) -> int:
        try:
            channel = int(payload["channel"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("channel must be an integer from 1 to 4") from exc
        if channel not in range(1, 5):
            raise ValueError("channel must be between 1 and 4")
        return channel
