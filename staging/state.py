"""Thread-safe in-memory state container for the staging application."""

from copy import deepcopy
from threading import RLock
from typing import Any


class StateStore:
    def __init__(self, initial_state: dict[str, Any]) -> None:
        self._lock = RLock()
        self._state = deepcopy(initial_state)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._state)

    def update_channel(self, channel: int, **values: Any) -> bool:
        with self._lock:
            channels = self._state.get("channels", {})
            if channel not in channels:
                return False
            channels[channel].update(values)
            return True

    def set_value(self, key: str, value: Any) -> None:
        with self._lock:
            self._state[key] = value
