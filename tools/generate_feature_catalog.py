import os
import re

race_path = os.path.join(os.path.dirname(__file__), "..", "vendor", "RACE.exe")
if not os.path.exists(race_path):
    race_path = "RACE.exe"

with open(race_path, "rb") as f:
    data = f.read()

# Ambil semua string unik
strings = sorted(list(set(re.findall(rb"/[A-Za-z0-9_%/ -]+", data))))

categories = {
    "CONTROL (Volume, Mute, Limiter, Compressor)": [],
    "XOVER (Crossover, Hipass, Lopass, Polarity)": [],
    "INEQ & OUTEQ (Parametric EQ, High/Low Shelf, Hi/Lo Cut)": [],
    "DELAY (Input Delay, Output Delay, Alignment)": [],
    "CONFIGURATION (Preset, Setup Routing, Name)": [],
    "METERING & STATUS": []
}

for s in strings:
    text = s.decode('latin1', errors='ignore')
    if text.startswith("/DEVICE") or text.startswith("/ID"):
        if "CONTROL" in text or "MUTE" in text or "LEVEL" in text or "COMPRESSOR" in text or "LIMITER" in text:
            categories["CONTROL (Volume, Mute, Limiter, Compressor)"].append(text)
        elif "XOVER" in text or "HIPASS" in text or "LOPASS" in text or "POLARITY" in text:
            categories["XOVER (Crossover, Hipass, Lopass, Polarity)"].append(text)
        elif "EQ" in text or "FILTER" in text:
            categories["INEQ & OUTEQ (Parametric EQ, High/Low Shelf, Hi/Lo Cut)"].append(text)
        elif "DELAY" in text:
            categories["DELAY (Input Delay, Output Delay, Alignment)"].append(text)
        elif "CONFIGURATION" in text or "SETUP" in text or "USERMEMORY" in text or "PRESET" in text:
            categories["CONFIGURATION (Preset, Setup Routing, Name)"].append(text)
        else:
            categories["METERING & STATUS"].append(text)

out_path = os.path.join(os.path.dirname(__file__), "..", "docs", "dx38_full_features.md")
with open(out_path, "w") as out:
    out.write("# Katalog Lengkap Perintah Serial Electro-Voice Dx38 / RACE.exe\n\n")
    out.write("Dokumentasi hasil ekstraksi seluruh perintah kontrol DSP EV Dx38.\n\n")
    for cat, cmds in categories.items():
        out.write(f"## {cat} ({len(cmds)} perintah)\n")
        out.write("```text\n")
        for c in cmds:
            out.write(f"{c}\n")
        out.write("```\n\n")

print("Selesai membuat docs/dx38_full_features.md!")
