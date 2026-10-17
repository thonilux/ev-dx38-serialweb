import os
import re

race_path = os.path.join(os.path.dirname(__file__), "..", "vendor", "RACE.exe")
if not os.path.exists(race_path):
    race_path = "RACE.exe"

with open(race_path, "rb") as f:
    data = f.read()

# Pola byte umum serial: F0 00 ... F7 (MIDI SysEx)
# Atau 02 ... 03 (STX ... ETX)
print("Scanning for byte constants...")

# Cari referensi RS232Lib
idx = 0
while True:
    idx = data.find(b"Rs232Lib", idx)
    if idx == -1:
        break
    print(f"Found Rs232Lib at offset 0x{idx:X}")
    # print surrounding 100 bytes
    start = max(0, idx - 40)
    end = min(len(data), idx + 80)
    print("Surrounding:", data[start:end])
    idx += 8
