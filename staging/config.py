"""Application configuration for the staging package."""

import os


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


class Config:
    HOST = os.getenv("RERACE_HOST", "127.0.0.1")
    PORT = _env_int("RERACE_PORT", 5001)
    DEBUG = os.getenv("RERACE_DEBUG", "0").lower() in {"1", "true", "yes"}
    COM_PORT = os.getenv("RERACE_COM_PORT", "COM2")
    DEVICE_ID = os.getenv("RERACE_DEVICE_ID", "1")
    SERIAL_BAUDRATE = _env_int("RERACE_SERIAL_BAUDRATE", 19200)
    DEMO_MODE = os.getenv("RERACE_DEMO_MODE", "1").lower() in {"1", "true", "yes"}
