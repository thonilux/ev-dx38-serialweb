"""
Script Uji Perintah Pemicu Dump Parameter Lengkap dari EV Dx38 via COM2.
Menguji beberapa kandidat perintah pemicu:
1. /ID1/DUMP ?
2. /ID1/PROGRAM ?
3. /ID1/PRESET ?
4. /ID1/Recall ?
5. /ID1/ALL ?
6. /ID1/Misc/Progname ?
7. /ID1/Misc/Prognumber ?
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

    def drain_input(self):
        """Kuras sisa buffer input sebelum mulai tes"""
        buf = ctypes.create_string_buffer(4096)
        bytes_read = wintypes.DWORD()
        while True:
            ctypes.windll.kernel32.ReadFile(self.handle, buf, 4096, ctypes.byref(bytes_read), None)
            if bytes_read.value == 0:
                break
            time.sleep(0.02)

    def test_trigger(self, cmd: str, wait_seconds=1.5):
        print(f"\n[TX] Mengirim: {cmd}")
        self.drain_input()
        self.send(cmd)

        start_time = time.time()
        received_lines = []
        buf = ctypes.create_string_buffer(4096)
        bytes_read = wintypes.DWORD()

        while time.time() - start_time < wait_seconds:
            ctypes.windll.kernel32.ReadFile(self.handle, buf, 4096, ctypes.byref(bytes_read), None)
            if bytes_read.value > 0:
                raw_chunk = buf.raw[:bytes_read.value].decode('latin1', errors='ignore')
                for line in raw_chunk.splitlines():
                    cleaned = line.strip()
                    if cleaned:
                        received_lines.append(cleaned)
            time.sleep(0.05)

        print(f"    -> Jumlah baris respon diterima: {len(received_lines)}")
        if received_lines:
            print("    -> Contoh baris respon:")
            for l in received_lines[:8]:
                print(f"       [RX] {l}")
            if len(received_lines) > 8:
                print(f"       ... (+ {len(received_lines) - 8} baris lainnya)")
            
            # Indikator sukses dump lengkap
            if len(received_lines) > 20:
                print(f"    🔥 [SUKSES!] Perintah '{cmd}' berhasil memicu DUMP PARAMETER LENGKAP!")
                return True
        else:
            print("    [-] Tidak ada respon.")
        return False

    def close(self):
        if self.handle and self.handle != -1:
            ctypes.windll.kernel32.CloseHandle(self.handle)

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM2"
    dx = Dx38Serial(port)
    device_id = "1"

    candidates = [
        f"/ID{device_id}/DUMP ?",
        f"/ID{device_id}/PROGRAM ?",
        f"/ID{device_id}/PRESET ?",
        f"/ID{device_id}/Misc/Progname ?",
        f"/ID{device_id}/Misc/Prognumber ?",
        f"/ID{device_id}/Recall ?",
        f"/ID{device_id}/ALL ?",
        f"/ID{device_id}/Dump",
        f"/ID{device_id}/Dump 0",
        f"/ID{device_id}/Misc ?"
    ]

    print("\n" + "="*60)
    print("  MENCARI PERINTAH PEMICU FULL PARAMETER DUMP PADA EV DX38")
    print("="*60)

    found_cmd = None
    for c in candidates:
        success = dx.test_trigger(c, wait_seconds=1.2)
        if success:
            found_cmd = c
            break
        time.sleep(0.3)

    if found_cmd:
        print("\n" + "="*60)
        print(f"  KESIMPULAN: Perintah pemicu dump adalah: {found_cmd}")
        print("="*60 + "\n")
    else:
        print("\n[-] Belum ada kandidat di atas yang memicu > 20 baris.")
        print("[*] Jangan khawatir, kita juga bisa dump via recall preset aktif terakhir!")

    dx.close()

if __name__ == "__main__":
    main()
