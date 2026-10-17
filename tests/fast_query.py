"""
Fast Non-Blocking Dump Probe dengan Timeout COMMTIMEOUTS
"""

import sys
import time
import ctypes
from ctypes import wintypes

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80

class COMMTIMEOUTS(ctypes.Structure):
    _fields_ = [
        ("ReadIntervalTimeout", wintypes.DWORD),
        ("ReadTotalTimeoutMultiplier", wintypes.DWORD),
        ("ReadTotalTimeoutConstant", wintypes.DWORD),
        ("WriteTotalTimeoutMultiplier", wintypes.DWORD),
        ("WriteTotalTimeoutConstant", wintypes.DWORD),
    ]

class FastSerial:
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
        
        # Set non-blocking timeout (kembali langsung jika tidak ada byte)
        timeouts = COMMTIMEOUTS()
        timeouts.ReadIntervalTimeout = 50          # 50ms antar byte
        timeouts.ReadTotalTimeoutConstant = 300    # total 300ms max per ReadFile
        timeouts.ReadTotalTimeoutMultiplier = 0
        timeouts.WriteTotalTimeoutConstant = 100
        timeouts.WriteTotalTimeoutMultiplier = 0
        ctypes.windll.kernel32.SetCommTimeouts(self.handle, ctypes.byref(timeouts))
        print(f"[+] Terhubung ke {port} (Timeouts configured, no-stuck guarantee)")

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

    def query(self, cmd: str):
        print(f"\n[TX] -> {cmd}")
        self.send(cmd)
        
        # Baca semua respon sampai tidak ada lagi data yang datang
        full_resp = []
        buf = ctypes.create_string_buffer(4096)
        bytes_read = wintypes.DWORD()
        
        start_wait = time.time()
        while time.time() - start_wait < 1.0:
            ctypes.windll.kernel32.ReadFile(self.handle, buf, 4096, ctypes.byref(bytes_read), None)
            if bytes_read.value > 0:
                text = buf.raw[:bytes_read.value].decode('latin1', errors='ignore')
                full_resp.append(text)
                start_wait = time.time() # Reset timer jika masih mengalir data
            else:
                break
        
        all_text = "".join(full_resp).strip()
        lines = [l.strip() for l in all_text.splitlines() if l.strip()]
        print(f"    Respon diterima ({len(lines)} baris):")
        for l in lines[:6]:
            print(f"      [RX] {l}")
        if len(lines) > 6:
            print(f"      ... (+ {len(lines)-6} baris lagi)")
        return len(lines)

    def close(self):
        if self.handle and self.handle != -1:
            ctypes.windll.kernel32.CloseHandle(self.handle)

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM2"
    fs = FastSerial(port)
    device_id = "1"

    candidates = [
        f"/ID{device_id}/PROGRAM ?",
        f"/ID{device_id}/PRESET ?",
        f"/ID{device_id}/Misc/Progname ?",
        f"/ID{device_id}/Misc/Prognumber ?",
        f"/ID{device_id}/Recall 28", # Nomor preset yang tadi aktif di alatmu
        f"/ID{device_id}/DEVICE ?",
        f"/ID{device_id}/STATUS ?"
    ]

    for c in candidates:
        count = fs.query(c)
        if count > 20:
            print(f"\n🔥 DITEMUKAN! Perintah '{c}' menghasilkan {count} baris dump!")
            break
        time.sleep(0.3)

    fs.close()

if __name__ == "__main__":
    main()
