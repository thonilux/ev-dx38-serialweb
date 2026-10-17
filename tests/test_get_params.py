"""
Query All Parameters Test untuk EV Dx38 via COM2
Mencoba berbagai sintaks query (?):
- /ID1/DEVICE ?
- /ID1/Out1/Level ?
- /ID1/Out1/Mute ?
- /ID1/PROGRAM ? atau /ID1/PRESET ?
- /ID1/ALL ? atau /ID1/?
"""

import sys
import time
import ctypes
from ctypes import wintypes

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80

class Dx38Serial:
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
            raise Exception(f"Gagal buka port {port}")
        print(f"[+] Terhubung ke {port}")

    def send(self, cmd: str):
        full_cmd = (cmd + "\r").encode("ascii")
        written = wintypes.DWORD()
        ctypes.windll.kernel32.WriteFile(
            self.handle,
            full_cmd,
            len(full_cmd),
            ctypes.byref(written),
            None
        )
        return written.value

    def query(self, cmd: str, wait=0.1):
        self.send(cmd)
        time.sleep(wait)
        buf = ctypes.create_string_buffer(512)
        bytes_read = wintypes.DWORD()
        ctypes.windll.kernel32.ReadFile(
            self.handle,
            buf,
            512,
            ctypes.byref(bytes_read),
            None
        )
        raw = buf.raw[:bytes_read.value].decode('latin1', errors='ignore').strip()
        return raw

    def close(self):
        if self.handle and self.handle != -1:
            ctypes.windll.kernel32.CloseHandle(self.handle)

def test_queries(port="COM2"):
    dx = Dx38Serial(port)
    device_id = "1"

    candidates = [
        f"/ID{device_id}/DEVICE ?",
        f"/ID{device_id}/Out1/Level ?",
        f"/ID{device_id}/Out1/Mute ?",
        f"/ID{device_id}/Out2/Level ?",
        f"/ID{device_id}/Out2/Mute ?",
        f"/ID{device_id}/Out3/Level ?",
        f"/ID{device_id}/Out3/Mute ?",
        f"/ID{device_id}/Out4/Level ?",
        f"/ID{device_id}/Out4/Mute ?",
        f"/ID{device_id}/PRESET ?",
        f"/ID{device_id}/PROGRAM ?",
        f"/ID{device_id}/NAME ?",
        f"/ID{device_id}/SETUP ?",
        f"/ID{device_id}/ROUTING ?",
        f"/ID{device_id} ?",
        f"/ID{device_id}/STATUS ?"
    ]

    print("\n" + "="*50)
    print("  TEST GET PARAMETERS DARI EV DX38")
    print("="*50 + "\n")

    for c in candidates:
        reply = dx.query(c)
        status = "OK" if reply and "; ?" not in reply else "ERROR/UNSUPPORTED"
        print(f"[TX] {c:25} -> [RX] {reply}  ({status})")

    dx.close()

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "COM2"
    test_queries(p)
