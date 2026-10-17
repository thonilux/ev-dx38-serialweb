import os
import re

race_path = os.path.join(os.path.dirname(__file__), "..", "vendor", "RACE.exe")
if not os.path.exists(race_path):
    race_path = "RACE.exe"

with open(race_path, "rb") as f:
    data = f.read()

# Cari semua string yang diawali /DEVICE
commands = re.findall(rb"/DEVICE[^\x00\r\n]+", data)
print(f"Total commands found: {len(commands)}")
unique_cmds = sorted(list(set([c.decode('latin1', errors='ignore') for c in commands])))
for c in unique_cmds:
    print(c)
