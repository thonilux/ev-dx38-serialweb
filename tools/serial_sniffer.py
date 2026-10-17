"""
Serial Bridge & Sniffer Utility for EV Dx38 / RACE.exe
Membantu monitoring atau bridging komunikasi serial secara langsung dengan output format HEX.
"""

import sys
import time
import serial
import serial.tools.list_ports

def list_ports():
    ports = serial.tools.list_ports.comports()
    print("Daftar Serial COM Port yang terdeteksi:")
    for p in ports:
        print(f"  - {p.device}: {p.description} (VID:PID={p.vid}:{p.pid})")
    if not ports:
        print("  (Tidak ada COM port yang terdeteksi. Hubungkan adapter USB-to-RS232 terlebih dahulu)")

def sniff(port, baudrate=19200):
    print(f"\n[+] Membuka port {port} pada {baudrate} bps (8-N-1)...")
    try:
        ser = serial.Serial(port=port, baudrate=baudrate, timeout=0.1)
    except Exception as e:
        print(f"[-] Gagal membuka port {port}: {e}")
        return

    print(f"[+] Sniffer aktif di {port}. Tekan Ctrl+C untuk berhenti.\n")
    print("Menunggu paket data...")

    last_time = time.time()
    buffer = bytearray()

    try:
        while True:
            data = ser.read(ser.in_waiting or 1)
            if data:
                buffer.extend(data)
                last_time = time.time()
            else:
                if len(buffer) > 0 and (time.time() - last_time) > 0.05:
                    hex_str = " ".join(f"{b:02X}" for b in buffer)
                    ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in buffer)
                    timestamp = time.strftime("%H:%M:%S")
                    print(f"[{timestamp}] (Len={len(buffer):2d}) HEX: {hex_str} | ASCII: {ascii_str}")
                    buffer.clear()
            time.sleep(0.005)
    except KeyboardInterrupt:
        print("\n[+] Sniffer dihentikan.")
    finally:
        ser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Penggunaan:")
        print("  1. Cek port:   python serial_sniffer.py --list")
        print("  2. Monitor:    python serial_sniffer.py COMx [baudrate (default 19200)]")
        print("Contoh:          python serial_sniffer.py COM3 19200\n")
        list_ports()
    elif sys.argv[1] == "--list":
        list_ports()
    else:
        com_port = sys.argv[1].upper()
        baud = int(sys.argv[2]) if len(sys.argv) > 2 else 19200
        sniff(com_port, baud)
