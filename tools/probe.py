"""
Virtual Serial Bridge (Proxy / Interceptor) untuk Sniffing RACE.exe <-> EV Dx38
Menggunakan socket TCP internal / loopback agar sniffing data TX (PC -> Dx38)
dan RX (Dx38 -> PC) dapat dipantau tanpa bentrok COM port.
"""

import sys
import time
import serial

def probe_baudrate(port="COM15"):
    bauds = [19200, 38400, 9600, 115200]
    print(f"[*] Mengetes koneksi ke {port}...")
    for b in bauds:
        try:
            s = serial.Serial(port, b, timeout=0.2)
            print(f"    - Berhasil membuka {port} pada {b} baud.")
            s.close()
        except Exception as e:
            print(f"    - Gagal di {b}: {e}")

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "COM15"
    probe_baudrate(port)
