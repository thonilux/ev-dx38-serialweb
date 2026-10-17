import os
import re

race_path = os.path.join(os.path.dirname(__file__), "..", "vendor", "RACE.exe")
if not os.path.exists(race_path):
    race_path = "RACE.exe"

with open(race_path, "rb") as f:
    data = f.read()

# Cari pola teks ASCII dengan panjang >= 4
ascii_strings = re.findall(b"[ -~]{4,}", data)

keywords = [b"RS232", b"RS-232", b"RS485", b"RS-485", b"Mute", b"Gain", b"Preset", b"Volume", b"F0", b"F7", b"Dx38", b"DSP244"]

matches = []
for s in ascii_strings:
    for kw in keywords:
        if kw.lower() in s.lower():
            try:
                decoded = s.decode("latin1")
                if len(decoded) < 80 and decoded not in matches:
                    matches.append(decoded)
            except:
                pass

print(f"Total matching strings found: {len(matches)}")
for m in matches[:40]:
    print("  ", m)
