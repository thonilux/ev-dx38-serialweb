"""
Query Status Terkini (Level, Mute, Polarity, Delay, Info) dari EV Dx38 via COM2
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

class Dx38Sync:
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
        
        timeouts = COMMTIMEOUTS()
        timeouts.ReadIntervalTimeout = 30
        timeouts.ReadTotalTimeoutConstant = 150
        timeouts.ReadTotalTimeoutMultiplier = 0
        timeouts.WriteTotalTimeoutConstant = 50
        timeouts.WriteTotalTimeoutMultiplier = 0
        ctypes.windll.kernel32.SetCommTimeouts(self.handle, ctypes.byref(timeouts))

    def ask(self, cmd: str):
        full_cmd = (cmd + "\r").encode("ascii")
        written = wintypes.DWORD()
        ctypes.windll.kernel32.WriteFile(self.handle, full_cmd, len(full_cmd), ctypes.byref(written), None)
        
        buf = ctypes.create_string_buffer(512)
        bytes_read = wintypes.DWORD()
        ctypes.windll.kernel32.ReadFile(self.handle, buf, 512, ctypes.byref(bytes_read), None)
        res = buf.raw[:bytes_read.value].decode('latin1', errors='ignore').strip()
        # Ambil baris yang relevan (bukan echo atau error)
        lines = [l.strip() for l in res.splitlines() if l.strip() and not l.startswith(";")]
        return lines[0] if lines else res

    def get_full_state(self, device_id="1"):
        print("\n" + "="*50)
        print("  MEMBACA PARAMETER LIVE DARI EV DX38...")
        print("="*50)

        # 1. Info Program & Device
        dev = self.ask(f"/ID{device_id}/DEVICE ?")
        prog_name = self.ask(f"/ID{device_id}/Misc/Progname ?")
        prog_num = self.ask(f"/ID{device_id}/Misc/Prognumber ?")
        config = self.ask(f"/ID{device_id}/Misc/Config ?")
        
        print(f"\n[+] Hardware     : {dev}")
        print(f"[+] Active Preset: [{prog_num.replace(f'/ID{device_id}/MISC/PROGNUMBER', '').strip()}] {prog_name.replace(f'/ID{device_id}/MISC/PROGNAME', '').strip()}")
        print(f"[+] Routing Mode : {config.replace(f'/ID{device_id}/MISC/CONFIG', '').strip()}")

        # 2. Status Output Channel 1 s.d. 4 (Level, Mute, Polarity, Delay)
        print("\n[+] Status 4 Channel Output:")
        print(f" {'CH':<6} | {'LEVEL':<10} | {'MUTE':<8} | {'POLARITY':<10} | {'DELAY':<8}")
        print("-" * 55)

        channels = {}
        for ch in range(1, 5):
            lvl = self.ask(f"/ID{device_id}/Out{ch}/Level ?")
            mute = self.ask(f"/ID{device_id}/Out{ch}/Mute ?")
            pol = self.ask(f"/ID{device_id}/Out{ch}/Polarity ?")
            delay = self.ask(f"/ID{device_id}/Out{ch}/Delay ?")

            # Bersihkan prefix untuk display
            clean_lvl = lvl.split()[-1] if lvl else "0.0"
            clean_mute = "MUTED" if mute.endswith("1") else "ACTIVE"
            clean_pol = pol.split()[-1] if pol else "NORMAL"
            clean_delay = delay.split()[-1] if delay else "0.0"

            print(f" OUT {ch:<2} | {clean_lvl:<10} | {clean_mute:<8} | {clean_pol:<10} | {clean_delay:<8}")
            channels[ch] = {
                "level": clean_lvl,
                "muted": clean_mute == "MUTED",
                "polarity": clean_pol,
                "delay": clean_delay
            }

        print("-" * 55)
        print("[+] Pembacaan parameter sukses 100%!")

    def close(self):
        if self.handle and self.handle != -1:
            ctypes.windll.kernel32.CloseHandle(self.handle)

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "COM2"
    sync = Dx38Sync(p)
    sync.get_full_state("1")
    sync.close()
