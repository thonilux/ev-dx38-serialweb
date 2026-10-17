"""
Eksperimen Mengganti Topologi Routing / Preset untuk Mengubah Lampu SUB, LO, MID, HI
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

    def read_reply(self):
        time.sleep(0.05)
        buf = ctypes.create_string_buffer(256)
        bytes_read = wintypes.DWORD()
        ctypes.windll.kernel32.ReadFile(
            self.handle,
            buf,
            256,
            ctypes.byref(bytes_read),
            None
        )
        reply = buf.raw[:bytes_read.value].decode('latin1', errors='ignore').strip()
        if reply:
            print(f"[RX]: {reply}")
        return reply

    def close(self):
        if self.handle and self.handle != -1:
            ctypes.windll.kernel32.CloseHandle(self.handle)

def test_change_routing(port="COM2"):
    dx = Dx38Serial(port)
    device_id = "1"

    print("\n" + "="*55)
    print("  UJI GANTI ROUTING AGAR LAMPU SUB, LO, MID, HI BERPINDAH")
    print("="*55 + "\n")

    try:
        # Daftar mode routing standard Dx38
        modes = [
            ("MONO_FOURWAY", "Mode Mono 4-Way (Harusnya SUB, LO, MID, HI menyala di Out 1-4)"),
            ("STEREO_TWOWAY_SS", "Mode Stereo 2-Way Sub/Sat"),
            ("TWO_IN_FOUR", "Mode 2 In 4 Out (Fullrange)"),
            ("MONO_THREEWAY_SS", "Mode Mono 3-Way Sub/Sat")
        ]

        for mode_name, desc in modes:
            print(f"\n[*] Mengirim konfigurasi: {mode_name}")
            print(f"    Deskripsi: {desc}")
            dx.send(f"/ID{device_id}/CONFIGURATION/SETUP {mode_name}")
            dx.read_reply()
            print("    -> Lihat apakah lampu SUB, LO, MID, HI di layar/panel berubah? (Tunggu 3 detik...)")
            time.sleep(3)

        print("\n[*] Sekarang coba switch Preset Memory 1 s.d. 4...")
        for p in range(1, 5):
            print(f"\n[*] Panggil Preset {p}...")
            dx.send(f"/ID{device_id}/CONFIGURATION/USERMEMORY {p}")
            dx.read_reply()
            time.sleep(3)

        print("\n[+] Tes selesai!")

    except KeyboardInterrupt:
        print("\n[!] Dihentikan.")
    finally:
        dx.close()

if __name__ == "__main__":
    port_name = sys.argv[1] if len(sys.argv) > 1 else "COM2"
    test_change_routing(port_name)
