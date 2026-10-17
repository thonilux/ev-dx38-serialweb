import ctypes
from ctypes import wintypes
import time

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80

class WinSerial:
    def __init__(self, port="COM2"):
        self.handle = ctypes.windll.kernel32.CreateFileW(
            r"\\.\\" + port,
            GENERIC_READ | GENERIC_WRITE,
            0,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None
        )
        if self.handle == -1 or self.handle == 0xFFFFFFFF:
            raise Exception(f"Gagal buka {port}, err: {ctypes.windll.kernel32.GetLastError()}")

    def write(self, data: bytes):
        written = wintypes.DWORD()
        res = ctypes.windll.kernel32.WriteFile(
            self.handle,
            data,
            len(data),
            ctypes.byref(written),
            None
        )
        return written.value

    def read(self, max_bytes=256):
        buf = ctypes.create_string_buffer(max_bytes)
        bytes_read = wintypes.DWORD()
        ctypes.windll.kernel32.ReadFile(
            self.handle,
            buf,
            max_bytes,
            ctypes.byref(bytes_read),
            None
        )
        return buf.raw[:bytes_read.value]

    def close(self):
        if self.handle and self.handle != -1:
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None

s = WinSerial("COM2")
print("WinSerial COM2 opened successfully!")
written = s.write(b"/ID1/Out1/Mute 1\r")
print("Written bytes:", written)
s.close()
