"""
Test Running LED untuk Indikator Frekuensi Output (SUB, LO, MID, HI) pada EV Dx38
Format perintah dari RACE.exe:
  /ID1/CONFIGURATION/OUT<ch>/LED<led_index> <0|1>
  atau
  /ID1/CONFIGURATION/OUT<ch>/DESTINATION <SUB|LO|MID|HI>
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
        print(f"[TX]: {cmd}")
        return written.value

    def close(self):
        if self.handle and self.handle != -1:
            ctypes.windll.kernel32.CloseHandle(self.handle)

def test_running_led_freq(port="COM2"):
    dx = Dx38Serial(port)
    device_id = "1"

    print("\n" + "="*55)
    print("  MEMULAI RUNNING LED INDIKATOR (SUB, LO, MID, HI)")
    print("="*55 + "\n")

    try:
        # Metodologi 1: Menggunakan command LED index:
        # /ID1/CONFIGURATION/OUT<ch>/LED<1-4> <0|1>
        # Biasanya: LED 1=SUB, 2=LO, 3=MID, 4=HI
        print("[*] Tes Metode A: /ID1/CONFIGURATION/OUT<ch>/LED<idx> <0|1>...")
        for ch in range(1, 5):
            print(f"\n--- Output Channel {ch} ---")
            for led_idx, led_name in [(1, "SUB"), (2, "LO"), (3, "MID"), (4, "HI")]:
                print(f"  -> Out {ch} menyalakan LED: {led_name} (LED{led_idx})")
                dx.send(f"/ID{device_id}/CONFIGURATION/OUT{ch}/LED{led_idx} 1")
                time.sleep(0.4)
                dx.send(f"/ID{device_id}/CONFIGURATION/OUT{ch}/LED{led_idx} 0")
                time.sleep(0.1)

        print("\n[*] Tes Metode B: /ID1/CONFIGURATION/OUT<ch>/DESTINATION <name>...")
        # Metodologi 2: Menggunakan label DESTINATION
        labels = ["SUB", "LO", "MID", "HI"]
        for cycle in range(2):
            for ch in range(1, 5):
                lbl = labels[ch - 1]
                print(f"  -> Setting Out {ch} DESTINATION ke {lbl}")
                dx.send(f"/ID{device_id}/CONFIGURATION/OUT{ch}/DESTINATION {lbl}")
                time.sleep(0.5)

        print("\n[+] Tes selesai!")

    except KeyboardInterrupt:
        print("\n[!] Dihentikan.")
    finally:
        dx.close()

if __name__ == "__main__":
    port_name = sys.argv[1] if len(sys.argv) > 1 else "COM2"
    test_running_led_freq(port_name)
