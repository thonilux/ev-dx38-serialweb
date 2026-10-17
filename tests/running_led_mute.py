"""
Running LED Mute Test untuk EV Dx38 via COM2
Menyalakan dan mematikan LED Mute Output 1, 2, 3, 4 secara berurutan (Running LED).
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
            err = ctypes.windll.kernel32.GetLastError()
            raise Exception(f"Gagal membuka port {port}. Kode error: {err}")
        print(f"[+] Berhasil terhubung langsung ke {port} (Win32 Native Handle: {self.handle})")

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

    def close(self):
        if self.handle and self.handle != -1:
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None

def run_led_sequence(port="COM2", cycles=5, delay=0.3):
    dx = Dx38Serial(port)
    device_id = "1"

    print("\n" + "="*50)
    print("  MEMULAI RUNNING LED MUTE TEST PADA EV DX38")
    print(f"  Target: Out 1 -> Out 2 -> Out 3 -> Out 4 ({cycles} putaran)")
    print("="*50 + "\n")

    try:
        # 1. Unmute semua channel dulu di awal
        print("[*] Mereset semua channel ke UNMUTE...")
        for ch in range(1, 5):
            dx.send(f"/ID{device_id}/Out{ch}/Mute 0")
        time.sleep(0.5)

        # 2. Loop running led
        for cycle in range(1, cycles + 1):
            print(f"\n--- Putaran ke-{cycle} dari {cycles} ---")
            for ch in range(1, 5):
                # Matikan channel sebelumnya
                prev_ch = 4 if ch == 1 else ch - 1
                dx.send(f"/ID{device_id}/Out{prev_ch}/Mute 0")

                # Nyalakan channel saat ini
                print(f"  >>> LED MUTE [ OUTPUT {ch} ] MENYALA (RED)")
                dx.send(f"/ID{device_id}/Out{ch}/Mute 1")
                time.sleep(delay)

        # Matikan channel terakhir
        dx.send(f"/ID{device_id}/Out4/Mute 0")
        time.sleep(0.3)

        # 3. Efek Blink Semua Bersamaan (All Blink)
        print("\n[*] Efek Kedip Semua LED Mute (All Channels Blink)...")
        for _ in range(3):
            for ch in range(1, 5):
                dx.send(f"/ID{device_id}/Out{ch}/Mute 1")
            time.sleep(0.25)
            for ch in range(1, 5):
                dx.send(f"/ID{device_id}/Out{ch}/Mute 0")
            time.sleep(0.25)

        print("\n[+] Selesai! Semua channel telah di-unmute kembali.")

    except KeyboardInterrupt:
        print("\n[!] Dihentikan oleh user.")
    finally:
        # Pastikan tidak ada yang tertinggal dalam kondisi mute
        for ch in range(1, 5):
            dx.send(f"/ID{device_id}/Out{ch}/Mute 0")
        dx.close()
        print("[+] Port serial ditutup aman.")

if __name__ == "__main__":
    port_name = sys.argv[1] if len(sys.argv) > 1 else "COM2"
    run_led_sequence(port_name)
