"""Serial transport boundary. Hardware transport is intentionally not connected yet."""

from typing import Protocol


class SerialTransport(Protocol):
    @property
    def connected(self) -> bool: ...

    def send_cmd(self, command: str) -> None: ...

    def query(self, command: str, max_bytes: int = 512) -> str: ...

    def close(self) -> None: ...


class OfflineTransport:
    """Explicit no-hardware transport used by the isolated staging app."""

    @property
    def connected(self) -> bool:
        return False

    def send_cmd(self, command: str) -> None:
        raise ConnectionError("No serial device is connected")

    def query(self, command: str, max_bytes: int = 512) -> str:
        raise ConnectionError("No serial device is connected")

    def close(self) -> None:
        return None
