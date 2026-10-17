import re

with open(r"d:\son\re-race\Rs232Lib.dll", "rb") as f:
    data = f.read()

ascii_strings = re.findall(b"[ -~]{4,}", data)
print(f"Total strings in Rs232Lib.dll: {len(ascii_strings)}")
for s in ascii_strings:
    try:
        t = s.decode('latin1')
        if any(w in t.lower() for w in ['open', 'write', 'read', 'config', 'baud', 'port', 'send', 'sysex', 'error', 'f0', 'f7']):
            print("  ", t)
    except:
        pass
