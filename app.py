"""
Flask Web Controller — Electro-Voice Dx38 Pro Web Console
Adaptive Professional DSP Dashboard
High-Density Audio Engineering Interface with Full Hardware Sync & Control
"""

import sys
import time
import threading
import ctypes
from ctypes import wintypes
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

COM_PORT = "COM2"
DEVICE_ID = "1"

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80

class COMMTIMEOUTS(ctypes.Structure):
    _fields_ = [
        ("ReadIntervalTimeout", wintypes.DWORD),
        ("ReadTotalTimeoutMultiplier", wintypes.DWORD),
        ("ReadTotalTimeoutConstant", wintypes.DWORD),
        ("WriteTotalTimeoutMultiplier", wintypes.DWORD),
        ("WriteTotalTimeoutConstant", wintypes.DWORD),
    ]

class WinSerial:
    def __init__(self, port="COM2"):
        self.lock = threading.Lock()
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
            raise Exception(f"Gagal buka port {port}. Error code: {err}")

        timeouts = COMMTIMEOUTS()
        timeouts.ReadIntervalTimeout = 20
        timeouts.ReadTotalTimeoutConstant = 120
        timeouts.ReadTotalTimeoutMultiplier = 0
        timeouts.WriteTotalTimeoutConstant = 40
        timeouts.WriteTotalTimeoutMultiplier = 0
        ctypes.windll.kernel32.SetCommTimeouts(self.handle, ctypes.byref(timeouts))
        print(f"[+] WinSerial terhubung ke {port}")

    def query(self, cmd: str, max_bytes=512) -> str:
        """Atomic write + read with lock to prevent thread collision."""
        full_cmd = (cmd + "\r").encode("ascii")
        with self.lock:
            written = wintypes.DWORD()
            ctypes.windll.kernel32.WriteFile(self.handle, full_cmd, len(full_cmd), ctypes.byref(written), None)
            buf = ctypes.create_string_buffer(max_bytes)
            bytes_read = wintypes.DWORD()
            ctypes.windll.kernel32.ReadFile(self.handle, buf, max_bytes, ctypes.byref(bytes_read), None)
            raw = buf.raw[:bytes_read.value].decode('latin1', errors='ignore').strip()
            lines = [l.strip() for l in raw.splitlines() if l.strip() and not l.startswith(";")]
            return lines[0] if lines else raw

    def send_cmd(self, cmd: str):
        full_cmd = (cmd + "\r").encode("ascii")
        with self.lock:
            written = wintypes.DWORD()
            ctypes.windll.kernel32.WriteFile(self.handle, full_cmd, len(full_cmd), ctypes.byref(written), None)

    def query_vu(self) -> dict:
        full_cmd = f"/ID{DEVICE_ID}/VU ?\r".encode("ascii")
        with self.lock:
            written = wintypes.DWORD()
            ctypes.windll.kernel32.WriteFile(self.handle, full_cmd, len(full_cmd), ctypes.byref(written), None)
            buf = ctypes.create_string_buffer(128)
            bytes_read = wintypes.DWORD()
            ctypes.windll.kernel32.ReadFile(self.handle, buf, 128, ctypes.byref(bytes_read), None)
            raw = buf.raw[:bytes_read.value].decode('latin1', errors='ignore')
            if "VU" in raw:
                idx = raw.find("VU")
                vc = raw[idx+2 : idx+8]
                flags = raw[idx+8 : idx+10] if len(raw) >= idx+10 else ""
                if len(vc) == 6:
                    # ASCII character 64 '@' is below -30 dB (silence/noise floor)
                    # Values > 64 represent steps starting at -30 dB up to 0 dB / CLIP
                    steps = [max(0, ord(c) - 64) for c in vc]
                    pcts = [min(100, int((s / 30.0) * 100)) for s in steps]
                    # Hardware Compressor active flag (f2 in Dx38 VU response e.g. 'pp' vs 'pt')
                    f_comp = (ord(flags[1]) - ord('p')) if (len(flags) >= 2 and flags[1] >= 'p') else 0
                    comp_active = [bool((f_comp & (1 << (i-1))) or (f_comp & (1 << (4-i)))) for i in range(1, 5)]
                    return {"steps": steps, "pcts": pcts, "flags": flags, "comp": comp_active}
        return {}

    def close(self):
        with self.lock:
            if self.handle and self.handle != -1 and self.handle != 0xFFFFFFFF:
                try:
                    ctypes.windll.kernel32.CloseHandle(self.handle)
                except Exception:
                    pass
                self.handle = -1

ser = None

device_state = {
    "connected": True,
    "device_name": "EV DX38 V3.21",
    "preset_num": "28",
    "preset_name": "CAF+b3",
    "routing_mode": "TWOWAY",
    "master_mute": False,
    "vu": [0, 0, 0, 0, 0, 0],
    "vu_steps": [0, 0, 0, 0, 0, 0],
    "comp": [False, False, False, False],
    "selected_channel": 1,
    "inputs": {
        1: {"name": "IN 1", "level": 0.0, "delay": 0.0, "muted": False},
        2: {"name": "IN 2", "level": 0.0, "delay": 0.0, "muted": False}
    },
    "channels": {
        1: {
            "name": "OUT 1", "desc": "Low-Left", "color": "#ff6b2b",
            "source": "IN 1",
            "level": 0.0, "muted": False, "polarity": "NORMAL", "delay": "0.000",
            "lowcut_freq": 35.0, "lowcut_slope": "24dB Linkwitz", "lowcut_bypass": False,
            "highcut_freq": 120.0, "highcut_slope": "24dB Linkwitz", "highcut_bypass": False,
            "comp": {"thresh": -18.0, "ratio": 4.0, "attack": 5.0, "release": 50.0, "bypass": False},
            "limiter": {"thresh": -6.0, "release": 100.0, "bypass": False},
            "eq": {
                1: {"name": "Low",   "mode": "PEQ", "gain": 4.5,  "freq": 60.0,    "q": 1.7, "bypass": False, "color": "#22d3ee"},
                2: {"name": "LoMid", "mode": "PEQ", "gain": -8.0, "freq": 200.0,   "q": 3.0, "bypass": False, "color": "#2dd4bf"},
                3: {"name": "HiMid", "mode": "PEQ", "gain": -6.0, "freq": 800.0,   "q": 2.0, "bypass": False, "color": "#f43f5e"},
                4: {"name": "High",  "mode": "PEQ", "gain": 3.0,  "freq": 2500.0,  "q": 1.5, "bypass": False, "color": "#fb923c"}
            }
        },
        2: {
            "name": "OUT 2", "desc": "Low-Right", "color": "#00b4d8",
            "source": "IN 2",
            "level": 0.0, "muted": False, "polarity": "NORMAL", "delay": "0.000",
            "lowcut_freq": 35.0, "lowcut_slope": "24dB Linkwitz", "lowcut_bypass": False,
            "highcut_freq": 120.0, "highcut_slope": "24dB Linkwitz", "highcut_bypass": False,
            "comp": {"thresh": -18.0, "ratio": 4.0, "attack": 5.0, "release": 50.0, "bypass": False},
            "limiter": {"thresh": -6.0, "release": 100.0, "bypass": False},
            "eq": {
                1: {"name": "Low",   "mode": "PEQ", "gain": 4.5,  "freq": 60.0,    "q": 1.7, "bypass": False, "color": "#22d3ee"},
                2: {"name": "LoMid", "mode": "PEQ", "gain": -8.0, "freq": 200.0,   "q": 3.0, "bypass": False, "color": "#2dd4bf"},
                3: {"name": "HiMid", "mode": "PEQ", "gain": -6.0, "freq": 800.0,   "q": 2.0, "bypass": False, "color": "#f43f5e"},
                4: {"name": "High",  "mode": "PEQ", "gain": 3.0,  "freq": 2500.0,  "q": 1.5, "bypass": False, "color": "#fb923c"}
            }
        },
        3: {
            "name": "OUT 3", "desc": "High-Left", "color": "#d946ef",
            "source": "IN 1",
            "level": 0.0, "muted": False, "polarity": "NORMAL", "delay": "0.000",
            "lowcut_freq": 120.0, "lowcut_slope": "24dB Linkwitz", "lowcut_bypass": False,
            "highcut_freq": 18000.0, "highcut_slope": "12dB Butter", "highcut_bypass": False,
            "comp": {"thresh": -15.0, "ratio": 3.0, "attack": 2.0, "release": 40.0, "bypass": False},
            "limiter": {"thresh": -3.0, "release": 80.0, "bypass": False},
            "eq": {
                1: {"name": "Low",   "mode": "PEQ", "gain": -2.0, "freq": 400.0,   "q": 1.2, "bypass": False, "color": "#22d3ee"},
                2: {"name": "LoMid", "mode": "PEQ", "gain": 1.5,  "freq": 1800.0,  "q": 2.0, "bypass": False, "color": "#2dd4bf"},
                3: {"name": "HiMid", "mode": "PEQ", "gain": -1.0, "freq": 6000.0,  "q": 1.8, "bypass": False, "color": "#f43f5e"},
                4: {"name": "High",  "mode": "PEQ", "gain": 2.5,  "freq": 12500.0, "q": 1.0, "bypass": False, "color": "#fb923c"}
            }
        },
        4: {
            "name": "OUT 4", "desc": "High-Right", "color": "#10b981",
            "source": "IN 2",
            "level": 0.0, "muted": False, "polarity": "NORMAL", "delay": "0.000",
            "lowcut_freq": 120.0, "lowcut_slope": "24dB Linkwitz", "lowcut_bypass": False,
            "highcut_freq": 18000.0, "highcut_slope": "12dB Butter", "highcut_bypass": False,
            "comp": {"thresh": -15.0, "ratio": 3.0, "attack": 2.0, "release": 40.0, "bypass": False},
            "limiter": {"thresh": -3.0, "release": 80.0, "bypass": False},
            "eq": {
                1: {"name": "Low",   "mode": "PEQ", "gain": -2.0, "freq": 400.0,   "q": 1.2, "bypass": False, "color": "#22d3ee"},
                2: {"name": "LoMid", "mode": "PEQ", "gain": 1.5,  "freq": 1800.0,  "q": 2.0, "bypass": False, "color": "#2dd4bf"},
                3: {"name": "HiMid", "mode": "PEQ", "gain": -1.0, "freq": 6000.0,  "q": 1.8, "bypass": False, "color": "#f43f5e"},
                4: {"name": "High",  "mode": "PEQ", "gain": 2.5,  "freq": 12500.0, "q": 1.0, "bypass": False, "color": "#fb923c"}
            }
        }
    }
}

def sync_hardware():
    global ser, device_state
    if not ser: return
    try:
        pname = ser.query(f"/ID{DEVICE_ID}/Misc/Progname ?")
        pnum  = ser.query(f"/ID{DEVICE_ID}/Misc/Prognumber ?")
        cfg   = ser.query(f"/ID{DEVICE_ID}/Misc/Config ?")
        dev   = ser.query(f"/ID{DEVICE_ID}/DEVICE ?")

        if dev and "EV" in dev:
            device_state["device_name"] = dev.replace(f"/ID{DEVICE_ID}/DEVICE", "").strip()
        if pname:
            device_state["preset_name"] = pname.replace(f"/ID{DEVICE_ID}/MISC/PROGNAME", "").strip()
        if pnum:
            device_state["preset_num"]  = pnum.replace(f"/ID{DEVICE_ID}/MISC/PROGNUMBER", "").strip()
        if cfg:
            device_state["routing_mode"] = cfg.replace(f"/ID{DEVICE_ID}/MISC/CONFIG", "").strip()

        for ch in range(1, 5):
            lvl  = ser.query(f"/ID{DEVICE_ID}/Out{ch}/Level ?")
            mute = ser.query(f"/ID{DEVICE_ID}/Out{ch}/Mute ?")
            pol  = ser.query(f"/ID{DEVICE_ID}/Out{ch}/Polarity ?")
            dly  = ser.query(f"/ID{DEVICE_ID}/Out{ch}/Delay ?")

            try:
                device_state["channels"][ch]["level"] = float(lvl.split()[-1])
            except:
                pass
            device_state["channels"][ch]["muted"] = mute.endswith("1") or "MUTE 1" in mute.upper()
            device_state["channels"][ch]["polarity"] = "INVERTED" if "INVERTED" in pol.upper() else "NORMAL"
            if dly:
                device_state["channels"][ch]["delay"] = dly.split()[-1]

        print(f"[+] Sync OK — Preset [{device_state['preset_num']}] {device_state['preset_name']} | Mode: {device_state['routing_mode']}")
    except Exception as e:
        print(f"[-] Sync error: {e}")

def background_loop():
    global ser, device_state
    last_poll = 0
    last_reconnect_try = 0
    while True:
        now = time.time()
        if ser:
            try:
                # Check preset change every 2.5 seconds
                if now - last_poll > 2.5:
                    last_poll = now
                    cur_num = ser.query(f"/ID{DEVICE_ID}/Misc/Prognumber ?")
                    clean = cur_num.replace(f"/ID{DEVICE_ID}/MISC/PROGNUMBER", "").strip()
                    if clean and clean != device_state["preset_num"]:
                        sync_hardware()

                # Live VU Meter polling with -30 dB LUFS hardware calibration
                vu_data = ser.query_vu()
                if vu_data:
                    device_state["vu"] = vu_data.get("pcts", [])
                    device_state["vu_steps"] = vu_data.get("steps", [])
                    device_state["vu_flags"] = vu_data.get("flags", "")
                    device_state["comp"] = vu_data.get("comp", [False, False, False, False])
                device_state["connected"] = True
            except Exception as e:
                print(f"[-] Serial disconnected: {e}")
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                device_state["connected"] = False
        else:
            # Device unplugged: attempt automatic reconnection every 2.0s
            if now - last_reconnect_try > 2.0:
                last_reconnect_try = now
                try:
                    ser = WinSerial(COM_PORT)
                    device_state["connected"] = True
                    print(f"[+] Device reconnected on {COM_PORT}!")
                    sync_hardware()
                except Exception:
                    ser = None
                    device_state["connected"] = False

        time.sleep(0.08)

# The Complete Single-Page UI Application
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>EV Dx38 Pro Web Console</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;700;800&display=swap" rel="stylesheet">
<style>
:root {
  --bg-core: #090d16;
  --bg-surface: #0f172a;
  --bg-panel: #131c31;
  --bg-panel-alt: #17233d;
  --bg-raised: #1e2d4d;
  --bg-hover: #24355a;
  
  --border-subtle: #1e293b;
  --border-main: #273859;
  --border-glow: #38517e;
  
  --cyan: #00e5ff;
  --cyan-glow: rgba(0, 229, 255, 0.35);
  --teal: #14b8a6;
  --amber: #f59e0b;
  --amber-glow: rgba(245, 158, 11, 0.4);
  --orange: #ff6b2b;
  --purple: #a855f7;
  --green: #10b981;
  --red: #ef4444;
  --red-glow: rgba(239, 68, 68, 0.5);
  
  --text-main: #f8fafc;
  --text-dim: #94a3b8;
  --text-muted: #64748b;
  
  --font: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --mono: 'JetBrains Mono', monospace;
  --radius: 8px;
  --radius-sm: 5px;
  --trans: 0.15s ease;
}

* { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
body {
  background: var(--bg-core);
  color: var(--text-main);
  font-family: var(--font);
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  -webkit-font-smoothing: antialiased;
}

/* TOP CONSOLE HEADER */
#console-header {
  height: 52px;
  background: linear-gradient(180deg, #111a2f 0%, #0c1322 100%);
  border-bottom: 1px solid var(--border-main);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 16px;
  flex-shrink: 0;
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
  z-index: 50;
}
.brand-box {
  display: flex;
  align-items: center;
  gap: 8px;
}
.brand-badge {
  background: linear-gradient(135deg, #00d2ff, #0077ff);
  color: #fff;
  font-weight: 900;
  font-size: 11px;
  letter-spacing: 0.08em;
  padding: 3px 7px;
  border-radius: 4px;
  text-shadow: 0 1px 2px rgba(0,0,0,0.4);
}
.brand-title {
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #fff;
}
.brand-title span { color: var(--cyan); }
.header-sep {
  width: 1px;
  height: 24px;
  background: var(--border-main);
}
.header-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-dim);
}
.header-tag b { color: var(--text-main); font-family: var(--mono); font-weight: 700; }
.mode-pill {
  background: rgba(0, 229, 255, 0.12);
  border: 1px solid rgba(0, 229, 255, 0.35);
  color: var(--cyan);
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 800;
  padding: 3px 9px;
  border-radius: 12px;
  letter-spacing: 0.06em;
}

.preset-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.35);
  border-radius: 6px;
  padding: 3px 10px;
  cursor: pointer;
  transition: all var(--trans);
}
.preset-chip:hover {
  background: rgba(245, 158, 11, 0.22);
  border-color: var(--amber);
}
.preset-chip .p-num {
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 800;
  color: var(--amber);
}
.preset-chip .p-name {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-main);
  max-width: 160px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}
.link-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: var(--green);
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.3);
  padding: 4px 9px;
  border-radius: 12px;
}
.link-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 8px var(--green);
  animation: pulse 1.5s infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.85); } }

.hdr-btn {
  background: var(--bg-raised);
  border: 1px solid var(--border-main);
  color: var(--text-main);
  font-family: var(--font);
  font-size: 11px;
  font-weight: 700;
  padding: 5px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  letter-spacing: 0.04em;
  transition: all var(--trans);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.hdr-btn:hover {
  background: var(--bg-hover);
  border-color: var(--cyan);
  color: var(--cyan);
}
.hdr-btn.danger {
  border-color: rgba(239, 68, 68, 0.4);
  color: #ff6b88;
}
.hdr-btn.danger:hover {
  background: var(--red);
  color: #fff;
  border-color: var(--red);
  box-shadow: 0 0 12px var(--red-glow);
}

/* CHANNEL SELECTOR STRIP DECK */
#channel-deck {
  height: 76px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle);
  display: grid;
  grid-template-columns: 210px repeat(4, 1fr);
  gap: 8px;
  padding: 7px 14px;
  flex-shrink: 0;
}
.deck-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  padding: 6px 12px;
  gap: 10px;
  cursor: pointer;
  transition: all var(--trans);
  position: relative;
  overflow: hidden;
}
.deck-card:hover {
  background: var(--bg-panel-alt);
  border-color: var(--border-main);
}
.deck-card.active {
  background: var(--bg-panel-alt);
  border-color: var(--cyan);
  box-shadow: 0 0 14px rgba(0, 229, 255, 0.15), inset 0 0 0 1px var(--cyan);
}
.deck-indicator {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 4px;
}
.deck-body {
  flex: 1;
  min-width: 0;
}
.deck-ch-title {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.deck-ch-name {
  font-weight: 800;
  font-size: 13px;
  color: var(--text-main);
  letter-spacing: 0.02em;
}
.deck-ch-sub {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
}
.deck-metric {
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 700;
  color: var(--cyan);
  margin-top: 2px;
}
.deck-meter-box {
  width: 70px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.deck-vu-track {
  height: 6px;
  background: #080c14;
  border-radius: 3px;
  overflow: hidden;
  border: 1px solid rgba(255,255,255,0.06);
}
.deck-vu-fill {
  height: 100%;
  width: 0%;
  background: linear-gradient(90deg, #10b981 0%, #00e5ff 60%, #f59e0b 85%, #ef4444 100%);
  border-radius: 3px;
  transition: width 0.08s linear;
}
.deck-mute-btn {
  background: var(--bg-raised);
  border: 1px solid var(--border-main);
  color: var(--text-dim);
  font-weight: 800;
  font-size: 9px;
  padding: 3px 8px;
  border-radius: 12px;
  cursor: pointer;
  letter-spacing: 0.06em;
  transition: all var(--trans);
}
.deck-mute-btn:hover { border-color: var(--red); color: var(--red); }
.deck-mute-btn.muted {
  background: var(--red);
  color: #fff;
  border-color: #ff859d;
  box-shadow: 0 0 10px var(--red-glow);
}

/* MAIN BODY & WORKSPACE */
#main-view {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
}

/* LEFT NAVIGATION MENU */
#side-nav {
  width: 60px;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 0;
  gap: 6px;
  flex-shrink: 0;
  z-index: 20;
}
.nav-item {
  width: 46px;
  height: 46px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  border-radius: var(--radius);
  border: 1px solid transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  transition: all var(--trans);
}
.nav-item svg {
  width: 19px;
  height: 19px;
  stroke: currentColor;
  fill: none;
  stroke-width: 2;
  transition: transform var(--trans);
}
.nav-item:hover {
  color: var(--text-main);
  background: var(--bg-panel);
  border-color: var(--border-subtle);
}
.nav-item:hover svg { transform: translateY(-1px); }
.nav-item.active {
  background: var(--bg-raised);
  color: var(--cyan);
  border-color: var(--border-glow);
  box-shadow: inset 3px 0 0 var(--cyan);
}

/* CONTENT VIEWPORT */
#viewport {
  flex: 1;
  overflow: hidden;
  position: relative;
  background: var(--bg-core);
}
.tab-pane {
  display: none;
  height: 100%;
  overflow-y: auto;
  padding: 16px;
  gap: 14px;
  flex-direction: column;
}
.tab-pane.active {
  display: flex;
}

/* CARDS & PANELS */
.hd-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-main);
  border-radius: var(--radius);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}
.hd-card-header {
  height: 38px;
  padding: 0 14px;
  background: var(--bg-panel-alt);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-dim);
  flex-shrink: 0;
}
.hd-card-header .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--cyan);
  box-shadow: 0 0 6px var(--cyan);
}
.hd-card-header .title-text { color: var(--text-main); }
.hd-card-body {
  padding: 14px;
  flex: 1;
}

/* OVERVIEW / MIXER VIRTUAL CONSOLE STRIPS */
.console-strip-deck {
  display: grid;
  grid-template-columns: repeat(4, 1fr) 260px;
  gap: 12px;
  height: 100%;
  min-height: 520px;
}
.console-fader-strip {
  background: var(--bg-panel);
  border: 1px solid var(--border-main);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  padding: 12px;
  gap: 10px;
  position: relative;
  overflow: hidden;
  box-shadow: 0 4px 14px rgba(0,0,0,0.3);
}
.cfs-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: 8px;
}
.cfs-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 800;
  font-size: 13px;
}
.cfs-dot { width: 10px; height: 10px; border-radius: 50%; }
.cfs-source {
  font-size: 10px;
  font-family: var(--mono);
  font-weight: 700;
  color: var(--text-muted);
  background: var(--bg-surface);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--border-subtle);
}

.cfs-middle {
  flex: 1;
  display: flex;
  align-items: stretch;
  justify-content: center;
  gap: 16px;
  padding: 10px 0;
}
.fader-track-wrap {
  display: flex;
  align-items: center;
  position: relative;
  width: 60px;
}
.fader-scale {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 280px;
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 700;
  color: var(--text-muted);
  text-align: right;
  width: 24px;
  padding-right: 4px;
  border-right: 1px solid rgba(255,255,255,0.06);
}
/* Vertical Range Slider */
.v-slider-box {
  position: relative;
  height: 280px;
  width: 32px;
  display: flex;
  justify-content: center;
  align-items: center;
}
input[type=range].v-fader {
  -webkit-appearance: none;
  writing-mode: bt-lr; /* IE */
  transform: rotate(-90deg);
  width: 280px;
  height: 6px;
  background: #080d17;
  border-radius: 3px;
  border: 1px solid var(--border-main);
  outline: none;
  cursor: pointer;
}
input[type=range].v-fader::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 44px;
  height: 24px;
  border-radius: 4px;
  background: linear-gradient(180deg, #475569 0%, #1e293b 50%, #0f172a 100%);
  border: 1px solid #94a3b8;
  box-shadow: 0 4px 10px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.4);
  cursor: pointer;
  position: relative;
}
input[type=range].v-fader::-webkit-slider-thumb::after {
  content: '';
  display: block;
  position: absolute;
  top: 11px;
  left: 6px;
  right: 6px;
  height: 2px;
  background: var(--amber);
  box-shadow: 0 0 6px var(--amber);
}

/* Vertical LED Meter alongside fader */
.v-meter-strip {
  width: 14px;
  height: 280px;
  background: #070b13;
  border-radius: 3px;
  border: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column-reverse;
  padding: 2px;
  gap: 2px;
  overflow: hidden;
}
.v-led {
  flex: 1;
  border-radius: 1px;
  background: #111b2c;
  transition: background 0.05s;
}
.v-led.lit-g { background: #10b981; box-shadow: 0 0 4px #10b981; }
.v-led.lit-y { background: #eab308; box-shadow: 0 0 4px #eab308; }
.v-led.lit-o { background: #f97316; box-shadow: 0 0 4px #f97316; }
.v-led.lit-r { background: #ef4444; box-shadow: 0 0 6px #ef4444; }

.cfs-readout {
  font-family: var(--mono);
  font-size: 15px;
  font-weight: 800;
  color: var(--cyan);
  text-align: center;
  background: #080d17;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 6px 0;
}
.cfs-controls {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.cfs-btn {
  background: var(--bg-raised);
  border: 1px solid var(--border-main);
  color: var(--text-dim);
  font-family: var(--font);
  font-size: 10px;
  font-weight: 800;
  padding: 7px 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
  text-align: center;
  letter-spacing: 0.05em;
  transition: all var(--trans);
}
.cfs-btn:hover { border-color: var(--cyan); color: var(--cyan); }
.cfs-btn.pol-inv { background: rgba(245, 158, 11, 0.22); border-color: var(--amber); color: var(--amber); box-shadow: 0 0 12px var(--amber-glow); }
.cfs-btn.pol-btn {
  font-family: var(--font);
  font-size: 13px;
  font-weight: 900;
  letter-spacing: 0.04em;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
}
.cfs-btn.pol-btn:hover {
  border-color: var(--amber);
  color: var(--amber);
}
.deck-pol-badge {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 700;
  transition: all var(--trans);
}
.deck-pol-badge.pol-inv {
  color: var(--amber) !important;
  font-weight: 800;
  text-shadow: 0 0 6px var(--amber-glow);
}
.cfs-mute-big {
  grid-column: span 2;
  background: #1c273e;
  border: 1px solid var(--border-main);
  color: #94a3b8;
  font-size: 12px;
  font-weight: 900;
  padding: 10px 0;
  letter-spacing: 0.08em;
}
.cfs-mute-big:hover { border-color: var(--red); color: var(--red); }
.cfs-mute-big.muted {
  background: var(--red);
  color: #fff;
  border-color: #ff758f;
  box-shadow: 0 0 16px var(--red-glow);
}

/* EQ GRAPH & CONTROLS */
.eq-layout {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}
.eq-graph-container {
  height: 320px;
  background: #040812;
  border: 1px solid var(--border-main);
  border-radius: var(--radius);
  position: relative;
  overflow: hidden;
}
#eqCanvas {
  width: 100%;
  height: 100%;
  display: block;
}
.eq-graph-axis-x {
  position: absolute;
  bottom: 4px;
  left: 10px;
  right: 10px;
  display: flex;
  justify-content: space-between;
  pointer-events: none;
}
.eq-graph-axis-x span { font-family: var(--mono); font-size: 9px; color: #475569; font-weight: 600; }
.eq-graph-axis-y {
  position: absolute;
  top: 10px;
  bottom: 24px;
  right: 8px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  pointer-events: none;
}
.eq-graph-axis-y span { font-family: var(--mono); font-size: 9px; color: #475569; font-weight: 600; text-align: right; }

.eq-band-deck {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  flex: 1;
}
.eq-band-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-main);
  border-radius: var(--radius);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all var(--trans);
}
.eq-band-card.selected {
  border-color: var(--cyan);
  box-shadow: 0 0 14px rgba(0, 229, 255, 0.15), inset 0 0 0 1px var(--cyan);
}
.eq-bc-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.eq-bc-title {
  font-weight: 800;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.eq-bc-dot { width: 8px; height: 8px; border-radius: 50%; }
.eq-type-select {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  color: var(--text-main);
  font-family: var(--font);
  font-size: 10px;
  font-weight: 700;
  border-radius: 4px;
  padding: 2px 4px;
  outline: none;
}
.eq-knob-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.eq-knob-meta {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
}
.eq-knob-meta .k-label { color: var(--text-muted); font-weight: 700; }
.eq-knob-meta .k-val { font-family: var(--mono); font-weight: 800; color: var(--cyan); }
input[type=range].eq-slider {
  -webkit-appearance: none;
  width: 100%;
  height: 5px;
  background: #0a0f1d;
  border-radius: 3px;
  outline: none;
  border: 1px solid var(--border-subtle);
  cursor: pointer;
}
input[type=range].eq-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--cyan);
  border: 2px solid #040812;
  box-shadow: 0 0 8px var(--cyan);
  cursor: pointer;
}

/* CROSSOVER */
.xov-layout {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
}
.xov-graph-wrap {
  height: 280px;
  background: #040812;
  border: 1px solid var(--border-main);
  border-radius: var(--radius);
  position: relative;
  overflow: hidden;
}
#xovCanvas {
  width: 100%;
  height: 100%;
  display: block;
}
.xov-axis-x {
  position: absolute;
  bottom: 4px;
  left: 10px;
  right: 10px;
  display: flex;
  justify-content: space-between;
  pointer-events: none;
}
.xov-axis-x span { font-family: var(--mono); font-size: 9px; color: #475569; font-weight: 600; }
.xov-axis-y {
  position: absolute;
  top: 18px;
  bottom: 24px;
  right: 8px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  pointer-events: none;
}
.xov-axis-y span { font-family: var(--mono); font-size: 9px; color: #475569; font-weight: 600; text-align: right; }
.xov-legend {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}
.xov-leg-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  font-weight: 700;
  cursor: pointer;
  padding: 2px 7px;
  border-radius: 4px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--border-subtle);
  transition: all var(--trans);
}
.xov-leg-item:hover { background: var(--bg-hover); border-color: var(--border-main); }
.xov-leg-line { width: 18px; height: 3px; border-radius: 1px; }
.xov-leg-line.dashed { border-top: 2px dashed; height: 0; }
.xov-controls-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

/* DYNAMICS COMP / LIMITER */
.dyn-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  height: 100%;
}
.dyn-graph-box {
  height: 160px;
  background: #040812;
  border: 1px solid var(--border-main);
  border-radius: var(--radius-sm);
  position: relative;
  overflow: hidden;
  margin-bottom: 12px;
}
.dyn-graph-box canvas { width: 100%; height: 100%; display: block; }
.dyn-param-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
}
.dyn-label { width: 80px; font-size: 11px; font-weight: 700; color: var(--text-dim); }
.dyn-val { width: 70px; font-family: var(--mono); font-size: 11px; font-weight: 800; color: var(--cyan); text-align: right; }

/* METER BRIDGE (FULL 6 CHANNELS) */
.meter-assembly {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 280px;
}
.meter-scale-col {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 280px;
  font-family: var(--mono);
  font-size: 8px;
  font-weight: 700;
  color: var(--text-muted);
  text-align: right;
  padding-right: 2px;
}
.meter-scale-col .sc-clip { color: #ef4444; font-weight: 800; }
.meter-scale-col .sc-0 { color: #f59e0b; font-weight: 800; }
.meter-scale-col .sc-30 { color: #10b981; font-weight: 800; }
.sc-comp {
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.5px;
  padding: 1px 3px;
  border-radius: 2px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.25);
  color: #78716c;
  transition: all 0.1s ease;
  user-select: none;
}
.sc-comp.lit-comp {
  background: #f59e0b !important;
  border-color: #fbbf24 !important;
  color: #000 !important;
  font-weight: 900 !important;
  box-shadow: 0 0 10px rgba(245, 158, 11, 0.8), 0 0 4px #fbbf24 !important;
}

.meter-bridge-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 14px;
  height: 100%;
  padding: 8px;
}
.mb-channel-col {
  background: var(--bg-panel);
  border: 1px solid var(--border-main);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 14px 10px;
  gap: 8px;
  position: relative;
}
.mb-col-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.mb-ch-name {
  font-weight: 900;
  font-size: 14px;
  letter-spacing: 0.04em;
}
.mb-ch-type {
  font-size: 8px;
  font-weight: 800;
  color: var(--text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.mb-meter-assembly {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  width: 100%;
  justify-content: center;
  padding: 6px 0;
}
.mb-scale {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
  max-height: 480px;
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 700;
  color: var(--text-muted);
  text-align: right;
  padding-right: 4px;
}
.mb-scale .scale-clip { color: #ef4444; font-weight: 800; }
.mb-scale .scale-0 { color: #f59e0b; font-weight: 800; }
.mb-scale .scale-30 { color: #10b981; font-weight: 800; }
.mb-ladder-wrap {
  flex: 1;
  max-height: 480px;
  width: 32px;
  background: #040711;
  border-radius: 4px;
  border: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column-reverse;
  padding: 4px;
  gap: 3px;
}
.mb-segment {
  height: 15px;
  border-radius: 2px;
  background: #0e1526;
  transition: background 0.04s ease;
}
.mb-peak-readout {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 800;
  color: var(--amber);
  background: #080d17;
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 4px 10px;
  white-space: nowrap;
}

/* PRESET LIBRARY */
.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
  max-height: 540px;
  overflow-y: auto;
  padding-right: 4px;
}
.preset-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-main);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition: all var(--trans);
}
.preset-card:hover {
  background: var(--bg-panel-alt);
  border-color: var(--cyan);
}
.preset-card.active {
  background: rgba(245, 158, 11, 0.15);
  border-color: var(--amber);
  box-shadow: 0 0 12px var(--amber-glow);
}
.pc-num {
  font-family: var(--mono);
  font-size: 15px;
  font-weight: 900;
  color: var(--amber);
  min-width: 32px;
}
.pc-info { flex: 1; min-width: 0; }
.pc-name {
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pc-type { font-size: 9px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; }

/* ROUTING MATRIX */
.matrix-wrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 20px;
}
.matrix-row {
  display: flex;
  gap: 20px;
  align-items: center;
}
.matrix-node {
  background: var(--bg-panel);
  border: 1px solid var(--border-main);
  border-radius: var(--radius);
  padding: 14px 24px;
  text-align: center;
  min-width: 140px;
}
.matrix-node .node-title { font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; }
.matrix-node .node-val { font-size: 15px; font-weight: 900; color: var(--cyan); margin-top: 4px; }
.matrix-arrow { font-size: 20px; color: var(--text-muted); }

/* SCROLLBAR */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-core); }
::-webkit-scrollbar-thumb { background: var(--border-main); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--border-glow); }
</style>
</head>
<body>

<!-- TOP CONSOLE HEADER BAR -->
<header id="console-header">
  <div class="brand-box">
    <div class="brand-badge">EV DSP</div>
    <div class="brand-title">Dx38 <span>PRO CONSOLE</span></div>
  </div>
  <div class="header-sep"></div>
  <div class="header-tag">DEVICE: <b id="hdrDev">EV DX38 V3.21</b></div>
  <div class="header-sep"></div>
  <div class="header-tag">MODE: <div class="mode-pill" id="hdrMode">TWOWAY</div></div>
  <div class="header-sep"></div>
  <div class="preset-chip" onclick="switchTab('preset')" title="Click to open Presets Library">
    <span class="p-num" id="hdrPresetNum">28</span>
    <span class="p-name" id="hdrPresetName">CAF+b3</span>
  </div>
  
  <div class="header-right">
    <div class="link-badge" id="hdrLinkBadge">
      <div class="link-dot" id="hdrLinkDot"></div>
      <span id="hdrLinkText">RS-232 COM2 ONLINE</span>
    </div>
    <button class="hdr-btn danger" onclick="emergencyMuteAll()">MUTE ALL</button>
    <button class="hdr-btn" onclick="unmuteAll()">UNMUTE ALL</button>
    <button class="hdr-btn" onclick="forceSync()">FORCE SYNC</button>
  </div>
</header>

<!-- CHANNEL STRIP SELECTOR DECK -->
<div id="channel-deck">
  <!-- Inputs Mini Summary -->
  <div class="deck-card" id="deckCardIn" style="border-left: 3px solid #38bdf8;">
    <div class="deck-body">
      <div class="deck-ch-title">
        <span class="deck-ch-name" style="color:#38bdf8;">INPUTS</span>
        <span class="deck-ch-sub">IN 1 & 2</span>
      </div>
      <div class="deck-metric">STEREO MASTER</div>
    </div>
    <div class="deck-meter-box">
      <div class="deck-vu-track"><div class="deck-vu-fill" id="vuIn1"></div></div>
      <div class="deck-vu-track"><div class="deck-vu-fill" id="vuIn2"></div></div>
    </div>
  </div>

  <!-- Outputs 1..4 -->
  {% for ch in [1, 2, 3, 4] %}
  {% set colors = ['#ff6b2b', '#00b4d8', '#d946ef', '#10b981'] %}
  {% set names = ['OUT 1 (Low L)', 'OUT 2 (Low R)', 'OUT 3 (High L)', 'OUT 4 (High R)'] %}
  <div class="deck-card {{ 'active' if ch==1 else '' }}" id="deckCard{{ch}}" onclick="selectChannel({{ch}})">
    <div class="deck-indicator" style="background: {{colors[ch-1]}};"></div>
    <div class="deck-body">
      <div class="deck-ch-title">
        <span class="deck-ch-name" style="color:{{colors[ch-1]}}">OUT {{ch}}</span>
        <span class="deck-ch-sub deck-pol-badge" id="deckPol{{ch}}" title="Phase / Polarity">Ø</span>
        <span class="sc-comp" id="deckComp{{ch}}" style="font-size:7px;padding:0 3px;margin-left:auto;">COMP</span>
      </div>
      <div class="deck-metric" id="deckLevel{{ch}}">0.0 dB</div>
    </div>
    <div class="deck-meter-box">
      <div class="deck-vu-track"><div class="deck-vu-fill" id="deckVu{{ch}}"></div></div>
      <button class="deck-mute-btn" id="deckMute{{ch}}" onclick="toggleMute({{ch}}, event)">MUTE</button>
    </div>
  </div>
  {% endfor %}
</div>

<!-- MAIN VIEWPORT WITH LEFT NAVIGATION -->
<div id="main-view">
  <nav id="side-nav">
    <div class="nav-item active" id="btn-overview" onclick="switchTab('overview')" title="Overview Console">
      <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
      OVW
    </div>
    <div class="nav-item" id="btn-eq" onclick="switchTab('eq')" title="Parametric EQ">
      <svg viewBox="0 0 24 24"><path d="M3 17c3-8 6-8 9 0s6 8 9 0"/></svg>
      PEQ
    </div>
    <div class="nav-item" id="btn-xover" onclick="switchTab('xover')" title="Crossover / X-Over">
      <svg viewBox="0 0 24 24"><path d="M4 20L12 4L20 20"/><line x1="6" y1="15" x2="18" y2="15"/></svg>
      XOV
    </div>
    <div class="nav-item" id="btn-dyn" onclick="switchTab('dyn')" title="Dynamics (Compressor & Limiter)">
      <svg viewBox="0 0 24 24"><polyline points="2 12 6 4 10 16 14 8 18 14 22 12"/></svg>
      DYN
    </div>
    <div class="nav-item" id="btn-delay" onclick="switchTab('delay')" title="Delay & Alignment">
      <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>
      DLY
    </div>
    <div class="nav-item" id="btn-meter" onclick="switchTab('meter')" title="Meter Bridge">
      <svg viewBox="0 0 24 24"><rect x="4" y="6" width="4" height="12" rx="1"/><rect x="10" y="3" width="4" height="15" rx="1"/><rect x="16" y="9" width="4" height="9" rx="1"/></svg>
      MTR
    </div>
    <div class="nav-item" id="btn-preset" onclick="switchTab('preset')" title="Preset Library">
      <svg viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/></svg>
      PRE
    </div>
    <div class="nav-item" id="btn-routing" onclick="switchTab('routing')" title="Signal Routing">
      <svg viewBox="0 0 24 24"><circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="M6 9v3a3 3 0 0 0 3 3h6"/></svg>
      RTG
    </div>
  </nav>

  <main id="viewport">
    
    <!-- 1. OVERVIEW CONSOLE MIXER PANE -->
    <section class="tab-pane active" id="pane-overview">
      <div class="console-strip-deck">
        {% for ch in [1, 2, 3, 4] %}
        {% set colors = ['#ff6b2b', '#00b4d8', '#d946ef', '#10b981'] %}
        <div class="console-fader-strip" id="cfs{{ch}}">
          <div class="cfs-top">
            <div class="cfs-badge">
              <div class="cfs-dot" style="background: {{colors[ch-1]}};"></div>
              <span style="color:{{colors[ch-1]}}">OUT {{ch}}</span>
            </div>
            <span class="cfs-source" id="cfsSource{{ch}}">IN 1</span>
          </div>

          <div class="cfs-middle">
            <div class="fader-track-wrap">
              <div class="fader-scale">
                <span>+6</span>
                <span>0</span>
                <span>-6</span>
                <span>-12</span>
                <span>-18</span>
                <span>-24</span>
                <span>-36</span>
                <span>-inf</span>
              </div>
              <div class="v-slider-box">
                <input type="range" class="v-fader" id="fader{{ch}}" min="-40" max="6" step="0.5" value="0" 
                  oninput="onFaderChange({{ch}}, this.value)" 
                  onchange="sendFaderChange({{ch}}, this.value)">
              </div>
            </div>

            <!-- LED Ladder with Hardware -30 dB Scale -->
            <div class="meter-assembly">
              <div class="meter-scale-col">
                <span class="sc-clip">CLIP</span>
                <span class="sc-comp" id="compLed{{ch}}">COMP</span>
                <span class="sc-0">0</span>
                <span>-6</span>
                <span>-12</span>
                <span>-18</span>
                <span>-24</span>
                <span class="sc-30">-30</span>
              </div>
              <div class="v-meter-strip" id="ledStrip{{ch}}">
                {% for i in range(20) %}
                <div class="v-led" id="led_{{ch}}_{{i}}"></div>
                {% endfor %}
              </div>
            </div>
          </div>

          <div class="cfs-readout" id="faderVal{{ch}}">0.0 dB</div>

          <div class="cfs-controls">
            <button class="cfs-btn pol-btn" id="polBtn{{ch}}" onclick="togglePolarity({{ch}})" title="Phase / Polarity Invert (Ø)">Ø</button>
            <button class="cfs-btn" onclick="openChannelTab({{ch}}, 'eq')">EQ EDIT</button>
            <button class="cfs-btn cfs-mute-big" id="cfsMute{{ch}}" onclick="toggleMute({{ch}}, event)">MUTE</button>
          </div>
        </div>
        {% endfor %}

        <!-- Right Side Master Control Card -->
        <div class="hd-card">
          <div class="hd-card-header">
            <div class="dot"></div>
            <span class="title-text">SYSTEM STATUS</span>
          </div>
          <div class="hd-card-body" style="display:flex;flex-direction:column;gap:12px;">
            <div style="background:var(--bg-core);padding:10px;border-radius:var(--radius-sm);border:1px solid var(--border-subtle)">
              <div style="font-size:10px;color:var(--text-muted);font-weight:700;">CURRENT ROUTING</div>
              <div style="font-size:14px;font-weight:800;color:var(--cyan);margin-top:2px;" id="ovwMode">TWOWAY 2-WAY STEREO</div>
            </div>
            <div style="background:var(--bg-core);padding:10px;border-radius:var(--radius-sm);border:1px solid var(--border-subtle)">
              <div style="font-size:10px;color:var(--text-muted);font-weight:700;">ACTIVE PRESET</div>
              <div style="font-size:13px;font-weight:800;color:var(--amber);margin-top:2px;" id="ovwPreset">[28] CAF+b3</div>
            </div>
            <div style="background:var(--bg-core);padding:10px;border-radius:var(--radius-sm);border:1px solid var(--border-subtle)">
              <div style="font-size:10px;color:var(--text-muted);font-weight:700;">RS-232 CONNECTION</div>
              <div style="font-size:12px;font-weight:700;color:var(--green);margin-top:2px;">COM2 @ 19200 bps 8-N-1</div>
            </div>
            <div style="margin-top:auto;display:flex;flex-direction:column;gap:8px;">
              <button class="hdr-btn" style="width:100%;justify-content:center;padding:10px 0;" onclick="switchTab('preset')">LOAD PRESET LIBRARY</button>
              <button class="hdr-btn" style="width:100%;justify-content:center;padding:10px 0;" onclick="forceSync()">FULL HARDWARE SYNC</button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 2. PARAMETRIC EQ PANE -->
    <section class="tab-pane" id="pane-eq">
      <div class="eq-layout">
        <div class="hd-card" style="flex-shrink:0;">
          <div class="hd-card-header">
            <div class="dot"></div>
            <span class="title-text">4-BAND PARAMETRIC EQUALIZER</span>
            <span style="color:var(--amber);margin-left:6px;" id="eqChannelLabel">— OUT 1</span>
            <div style="margin-left:auto;display:flex;gap:8px;">
              <button class="hdr-btn" onclick="resetEqFlat()">FLAT</button>
              <button class="hdr-btn" id="btnApplyEq" onclick="applyEqHardware(event)">APPLY TO HARDWARE</button>
            </div>
          </div>
          <div class="hd-card-body" style="padding:10px;">
            <div class="eq-graph-container">
              <canvas id="eqCanvas"></canvas>
              <div class="eq-graph-axis-x">
                <span>20</span><span>50</span><span>100</span><span>200</span><span>500</span>
                <span>1k</span><span>2k</span><span>5k</span><span>10k</span><span>20k Hz</span>
              </div>
              <div class="eq-graph-axis-y">
                <span>+15</span><span>+10</span><span>+5</span><span>0</span><span>-5</span><span>-10</span><span>-15 dB</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 4 Bands Parameters Controls -->
        <div class="eq-band-deck">
          {% for b, color, name in [(1,'#22d3ee','Low'), (2,'#2dd4bf','Lo-Mid'), (3,'#f43f5e','Hi-Mid'), (4,'#fb923c','High')] %}
          <div class="eq-band-card {{ 'selected' if b==1 else '' }}" id="eqBandCard{{b}}" onclick="selectEqBand({{b}})">
            <div class="eq-bc-hdr">
              <div class="eq-bc-title">
                <div class="eq-bc-dot" style="background:{{color}}"></div>
                <span style="color:{{color}}">BAND {{b}} ({{name}})</span>
              </div>
              <select class="eq-type-select" id="eqType{{b}}" onchange="onEqTypeChange({{b}}, this.value)">
                <option value="PEQ" selected>PEQ (Bell)</option>
                <option value="LOSHELF">Low Shelf</option>
                <option value="HISHELF">High Shelf</option>
                <option value="LOCUT">Low Cut</option>
                <option value="HICUT">High Cut</option>
              </select>
            </div>

            <!-- Gain Slider -->
            <div class="eq-knob-row">
              <div class="eq-knob-meta">
                <span class="k-label">GAIN</span>
                <span class="k-val" id="eqGainVal{{b}}">+0.0 dB</span>
              </div>
              <input type="range" class="eq-slider" id="eqGain{{b}}" min="-15" max="15" step="0.25" value="0"
                oninput="onEqParamChange({{b}})">
            </div>

            <!-- Frequency Slider -->
            <div class="eq-knob-row">
              <div class="eq-knob-meta">
                <span class="k-label">FREQUENCY</span>
                <span class="k-val" id="eqFreqVal{{b}}">1000 Hz</span>
              </div>
              <input type="range" class="eq-slider" id="eqFreq{{b}}" min="20" max="20000" step="1" value="1000"
                oninput="onEqParamChange({{b}})">
            </div>

            <!-- Q Factor Slider -->
            <div class="eq-knob-row">
              <div class="eq-knob-meta">
                <span class="k-label">Q (BANDWIDTH)</span>
                <span class="k-val" id="eqQVal{{b}}">1.4</span>
              </div>
              <input type="range" class="eq-slider" id="eqQ{{b}}" min="0.4" max="14.0" step="0.1" value="1.4"
                oninput="onEqParamChange({{b}})">
            </div>
          </div>
          {% endfor %}
        </div>
      </div>
    </section>

    <!-- 3. CROSSOVER PANE -->
    <section class="tab-pane" id="pane-xover">
      <div class="xov-layout">
        <div class="hd-card" style="flex-shrink:0;">
          <div class="hd-card-header">
            <div class="dot"></div>
            <span class="title-text">CROSSOVER BANDPASS NETWORK</span>
            <span style="color:var(--amber);margin-left:6px;" id="xovChannelLabel">— OUT 1</span>
            <div class="xov-legend">
              {% for ch in [1, 2, 3, 4] %}
              {% set colors = ['#ff6b2b', '#00b4d8', '#d946ef', '#10b981'] %}
              <div class="xov-leg-item" onclick="selectChannel({{ch}})" title="Switch to OUT {{ch}}">
                <div class="xov-leg-line {{ 'dashed' if ch != 1 else '' }}" id="xovLegLine{{ch}}" style="{{ 'border-color:' + colors[ch-1] if ch != 1 else 'background:' + colors[ch-1] }}"></div>
                <span style="color:{{colors[ch-1]}}">OUT {{ch}}</span>
              </div>
              {% endfor %}
            </div>
            <div style="margin-left:8px;">
              <button class="hdr-btn" id="btnApplyXov" onclick="applyXoverHardware(event)">APPLY TO HARDWARE</button>
            </div>
          </div>
          <div class="hd-card-body" style="padding:10px;">
            <div class="xov-graph-wrap">
              <canvas id="xovCanvas"></canvas>
              <div class="xov-axis-x">
                <span>20</span><span>50</span><span>100</span><span>200</span><span>500</span>
                <span>1k</span><span>2k</span><span>5k</span><span>10k</span><span>20k Hz</span>
              </div>
              <div class="xov-axis-y">
                <span>0 dB</span><span>-12 dB</span><span>-24 dB</span><span>-36 dB</span><span>-48 dB</span>
              </div>
            </div>
          </div>
        </div>

        <div class="xov-controls-grid">
          <!-- High-Pass Filter (Low Cut) -->
          <div class="hd-card">
            <div class="hd-card-header">
              <div class="dot" style="background:#3b82f6;box-shadow:0 0 6px #3b82f6;"></div>
              <span class="title-text">HIGH-PASS FILTER (LOW CUT)</span>
            </div>
            <div class="hd-card-body" style="display:flex;flex-direction:column;gap:12px;">
              <div class="eq-knob-row">
                <div class="eq-knob-meta">
                  <span class="k-label">CUTOFF FREQUENCY</span>
                  <span class="k-val" id="xovHpFreqVal">35 Hz</span>
                </div>
                <input type="range" class="eq-slider" id="xovHpFreq" min="20" max="2000" step="1" value="35" oninput="renderXovGraph()">
              </div>
              <div style="display:flex;align-items:center;justify-content:space-between;">
                <span style="font-size:11px;font-weight:700;color:var(--text-dim);">FILTER SLOPE</span>
                <select class="eq-type-select" id="xovHpSlope" onchange="renderXovGraph()">
                  <option>6dB/oct</option>
                  <option>12dB Butterworth</option>
                  <option>12dB Bessel</option>
                  <option>12dB Linkwitz</option>
                  <option>18dB Butterworth</option>
                  <option selected>24dB Linkwitz</option>
                  <option>24dB Butterworth</option>
                  <option>THRU</option>
                </select>
              </div>
            </div>
          </div>

          <!-- Low-Pass Filter (High Cut) -->
          <div class="hd-card">
            <div class="hd-card-header">
              <div class="dot" style="background:#a855f7;box-shadow:0 0 6px #a855f7;"></div>
              <span class="title-text">LOW-PASS FILTER (HIGH CUT)</span>
            </div>
            <div class="hd-card-body" style="display:flex;flex-direction:column;gap:12px;">
              <div class="eq-knob-row">
                <div class="eq-knob-meta">
                  <span class="k-label">CUTOFF FREQUENCY</span>
                  <span class="k-val" id="xovLpFreqVal">120 Hz</span>
                </div>
                <input type="range" class="eq-slider" id="xovLpFreq" min="100" max="20000" step="1" value="120" oninput="renderXovGraph()">
              </div>
              <div style="display:flex;align-items:center;justify-content:space-between;">
                <span style="font-size:11px;font-weight:700;color:var(--text-dim);">FILTER SLOPE</span>
                <select class="eq-type-select" id="xovLpSlope" onchange="renderXovGraph()">
                  <option>6dB/oct</option>
                  <option>12dB Butterworth</option>
                  <option>12dB Bessel</option>
                  <option>12dB Linkwitz</option>
                  <option>18dB Butterworth</option>
                  <option selected>24dB Linkwitz</option>
                  <option>24dB Butterworth</option>
                  <option>THRU</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 4. DYNAMICS PANE (COMP & LIMITER) -->
    <!-- 4. DYNAMICS PANE -->
    <section class="tab-pane" id="pane-dyn">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;background:var(--bg-panel);padding:10px 16px;border-radius:var(--radius-sm);border:1px solid var(--border-subtle);flex-wrap:wrap;gap:8px;">
        <div style="display:flex;align-items:center;gap:12px;">
          <div style="display:flex;align-items:center;gap:8px;">
            <div class="dot" style="background:var(--amber);box-shadow:0 0 6px var(--amber)"></div>
            <span style="font-size:13px;font-weight:800;letter-spacing:0.06em;color:#fff;">DYNAMICS ENGINE</span>
            <span style="color:var(--cyan);font-weight:700;font-size:13px;" id="dynChannelLabel">— OUT 1</span>
          </div>
          <div style="display:flex;gap:6px;margin-left:8px;">
            {% for ch in [1, 2, 3, 4] %}
            <button class="hdr-btn dyn-ch-pill" id="dynChPill{{ch}}" onclick="selectChannel({{ch}})" style="padding:3px 10px;font-size:11px;font-weight:700;">OUT {{ch}}</button>
            {% endfor %}
          </div>
        </div>
        <button class="hdr-btn" id="btnApplyDyn" onclick="applyDynamicsHardware(event)" style="font-weight:800;letter-spacing:0.05em;padding:6px 16px;">APPLY TO HARDWARE</button>
      </div>
      <div class="dyn-grid">
        <!-- Compressor Card -->
        <div class="hd-card">
          <div class="hd-card-header">
            <div class="dot" style="background:var(--teal);box-shadow:0 0 6px var(--teal)"></div>
            <span class="title-text">COMPRESSOR</span>
            <span style="color:var(--amber);margin-left:6px;" id="compChannelLabel">— OUT 1</span>
            <div style="margin-left:auto;">
              <button class="hdr-btn" id="btnApplyComp" onclick="applyCompHardware(event)">APPLY</button>
            </div>
          </div>
          <div class="hd-card-body">
            <div class="dyn-graph-box"><canvas id="compCanvas"></canvas></div>
            <div class="dyn-param-row">
              <span class="dyn-label">Threshold</span>
              <input type="range" class="eq-slider" id="compThresh" min="-40" max="0" step="0.5" value="-18" oninput="updateCompDisplay()">
              <span class="dyn-val" id="compThreshVal">-18.0 dB</span>
            </div>
            <div class="dyn-param-row">
              <span class="dyn-label">Ratio</span>
              <input type="range" class="eq-slider" id="compRatio" min="1" max="20" step="0.5" value="4" oninput="updateCompDisplay()">
              <span class="dyn-val" id="compRatioVal">4.0 : 1</span>
            </div>
            <div class="dyn-param-row">
              <span class="dyn-label">Attack</span>
              <input type="range" class="eq-slider" id="compAttack" min="0.1" max="200" step="0.1" value="5" oninput="updateCompDisplay()">
              <span class="dyn-val" id="compAttackVal">5.0 ms</span>
            </div>
            <div class="dyn-param-row">
              <span class="dyn-label">Release</span>
              <input type="range" class="eq-slider" id="compRelease" min="10" max="2000" step="10" value="50" oninput="updateCompDisplay()">
              <span class="dyn-val" id="compReleaseVal">50 ms</span>
            </div>
          </div>
        </div>

        <!-- Limiter Card -->
        <div class="hd-card">
          <div class="hd-card-header">
            <div class="dot" style="background:var(--red);box-shadow:0 0 6px var(--red)"></div>
            <span class="title-text">PEAK LIMITER</span>
            <span style="color:var(--amber);margin-left:6px;" id="limChannelLabel">— OUT 1</span>
            <div style="margin-left:auto;">
              <button class="hdr-btn" id="btnApplyLim" onclick="applyLimiterHardware(event)">APPLY</button>
            </div>
          </div>
          <div class="hd-card-body">
            <div class="dyn-graph-box"><canvas id="limCanvas"></canvas></div>
            <div class="dyn-param-row">
              <span class="dyn-label">Threshold</span>
              <input type="range" class="eq-slider" id="limThresh" min="-20" max="20" step="0.5" value="-6" oninput="updateLimDisplay()">
              <span class="dyn-val" id="limThreshVal">-6.0 dB</span>
            </div>
            <div class="dyn-param-row">
              <span class="dyn-label">Release</span>
              <input type="range" class="eq-slider" id="limRelease" min="10" max="2000" step="10" value="100" oninput="updateLimDisplay()">
              <span class="dyn-val" id="limReleaseVal">100 ms</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 5. DELAY PANE -->
    <section class="tab-pane" id="pane-delay">
      <div class="hd-card" style="height:100%;">
        <div class="hd-card-header">
          <div class="dot"></div>
          <span class="title-text">SPEAKER ALIGNMENT & DELAY ENGINE</span>
        </div>
        <div class="hd-card-body" style="display:flex;flex-direction:column;gap:16px;">
          {% for ch in [1, 2, 3, 4] %}
          {% set colors = ['#ff6b2b', '#00b4d8', '#d946ef', '#10b981'] %}
          <div style="background:var(--bg-core);padding:14px;border-radius:var(--radius-sm);border:1px solid var(--border-subtle)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
              <div style="display:flex;align-items:center;gap:8px;font-weight:800;">
                <div style="width:10px;height:10px;border-radius:50%;background:{{colors[ch-1]}}"></div>
                <span style="color:{{colors[ch-1]}}">OUT {{ch}} DELAY</span>
              </div>
              <div style="font-family:var(--mono);font-size:14px;font-weight:800;color:var(--amber);" id="dlyReadout{{ch}}">0.000 ms</div>
              <div style="font-size:11px;color:var(--text-muted);" id="dlyDist{{ch}}">(0.00 m / 0.0 ft)</div>
            </div>
            <div style="display:flex;align-items:center;gap:12px;">
              <input type="range" class="eq-slider" style="flex:1" id="dlySlider{{ch}}" min="0" max="500" step="0.05" value="0"
                oninput="onDelayChange({{ch}}, this.value)"
                onchange="sendDelayHardware({{ch}}, this.value)">
              <button class="hdr-btn" onclick="sendDelayHardware({{ch}}, document.getElementById('dlySlider{{ch}}').value, event)">SET</button>
            </div>
          </div>
          {% endfor %}
        </div>
      </div>
    </section>

    <!-- 6. METER BRIDGE PANE -->
    <section class="tab-pane" id="pane-meter">
      <div class="hd-card" style="height:100%;">
        <div class="hd-card-header">
          <div class="dot"></div>
          <span class="title-text">REALTIME 6-CHANNEL BROADCAST METER BRIDGE</span>
        </div>
        <div class="hd-card-body">
          <div class="meter-bridge-grid">
            {% set ch_names = ['IN 1', 'IN 2', 'OUT 1', 'OUT 2', 'OUT 3', 'OUT 4'] %}
            {% set ch_colors = ['#38bdf8', '#38bdf8', '#ff6b2b', '#00b4d8', '#d946ef', '#10b981'] %}
            {% for idx in range(6) %}
            <div class="mb-channel-col">
              <div class="mb-col-header">
                <span class="mb-ch-name" style="color:{{ch_colors[idx]}}">{{ch_names[idx]}}</span>
                {% if idx >= 2 %}
                <span class="sc-comp" id="mbComp{{idx-1}}" style="font-size:7px;padding:0 3px;">COMP</span>
                {% else %}
                <span class="mb-ch-type">ANALOG IN</span>
                {% endif %}
              </div>
              <div class="mb-meter-assembly">
                <div class="mb-scale">
                  <span class="scale-clip">CLIP</span>
                  <span class="scale-0">0</span>
                  <span>-3</span>
                  <span>-6</span>
                  <span>-12</span>
                  <span>-18</span>
                  <span>-24</span>
                  <span class="scale-30">-30</span>
                </div>
                <div class="mb-ladder-wrap" id="mbLadder{{idx}}">
                  {% for seg in range(24) %}
                  <div class="mb-segment" id="mbSeg_{{idx}}_{{seg}}"></div>
                  {% endfor %}
                </div>
              </div>
              <div class="mb-peak-readout" id="mbPeak{{idx}}">&lt; -30.0 dB LUFS</div>
            </div>
            {% endfor %}
          </div>
        </div>
      </div>
    </section>

    <!-- 7. PRESET LIBRARY PANE -->
    <section class="tab-pane" id="pane-preset">
      <div class="hd-card" style="height:100%;">
        <div class="hd-card-header">
          <div class="dot"></div>
          <span class="title-text">HARDWARE PRESET LIBRARY (1-30)</span>
          <span style="margin-left:auto;font-size:11px;color:var(--text-dim)">ACTIVE PRESET: <b style="color:var(--amber);" id="preLibActive">28</b></span>
        </div>
        <div class="hd-card-body">
          <div class="preset-grid">
            {% for p in range(1, 31) %}
            <div class="preset-card {{ 'active' if p==28 else '' }}" id="preCard{{p}}" onclick="recallPreset({{p}})">
              <div class="pc-num">#{{p}}</div>
              <div class="pc-info">
                <div class="pc-name" id="preName{{p}}">Preset {{p}}</div>
                <div class="pc-type">{{ 'User Program' if p >= 25 else 'Factory Setup' }}</div>
              </div>
            </div>
            {% endfor %}
          </div>
        </div>
      </div>
    </section>

    <!-- 8. ROUTING MATRIX PANE -->
    <section class="tab-pane" id="pane-routing">
      <div class="hd-card" style="height:100%;">
        <div class="hd-card-header">
          <div class="dot"></div>
          <span class="title-text">SIGNAL ROUTING MATRIX</span>
        </div>
        <div class="hd-card-body">
          <div class="matrix-wrap">
            <div class="matrix-row">
              <div class="matrix-node">
                <div class="node-title">ANALOG INPUTS</div>
                <div class="node-val">IN 1 + IN 2</div>
              </div>
              <div class="matrix-arrow">&#10230;</div>
              <div class="matrix-node" style="border-color:var(--cyan);">
                <div class="node-title">DSP ENGINE</div>
                <div class="node-val" style="color:var(--cyan);" id="rtgModeLabel">TWOWAY</div>
              </div>
              <div class="matrix-arrow">&#10230;</div>
              <div style="display:flex;flex-direction:column;gap:8px;">
                <div class="matrix-node" style="min-width:180px;"><div class="node-title">OUT 1 (LF-L)</div><div class="node-val" style="color:#ff6b2b">IN 1 &rarr; Low</div></div>
                <div class="matrix-node" style="min-width:180px;"><div class="node-title">OUT 2 (LF-R)</div><div class="node-val" style="color:#00b4d8">IN 2 &rarr; Low</div></div>
                <div class="matrix-node" style="min-width:180px;"><div class="node-title">OUT 3 (HF-L)</div><div class="node-val" style="color:#d946ef">IN 1 &rarr; High</div></div>
                <div class="matrix-node" style="min-width:180px;"><div class="node-title">OUT 4 (HF-R)</div><div class="node-val" style="color:#10b981">IN 2 &rarr; High</div></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

  </main>
</div>

<script>
'use strict';

let STATE = {};
let activeChannel = 1;
let activeEqBand = 1;
let isInteracting = false;

// Tab Navigation
function switchTab(tabId) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  
  const pane = document.getElementById('pane-' + tabId);
  const btn = document.getElementById('btn-' + tabId);
  if (pane) pane.classList.add('active');
  if (btn) btn.classList.add('active');

  // Trigger redraw of canvas elements on tab switch
  if (tabId === 'eq') renderEqGraph();
  if (tabId === 'xover') renderXovGraph();
  if (tabId === 'dyn') { renderCompGraph(); renderLimGraph(); }
}

function openChannelTab(ch, tabId) {
  selectChannel(ch);
  switchTab(tabId);
}

// Channel Selection
function selectChannel(ch) {
  activeChannel = ch;
  for (let i = 1; i <= 4; i++) {
    const card = document.getElementById('deckCard' + i);
    if (card) card.classList.toggle('active', i === ch);
    const strip = document.getElementById('cfs' + i);
    if (strip) {
      strip.style.borderColor = (i === ch) ? 'var(--cyan)' : 'var(--border-main)';
      strip.style.boxShadow = (i === ch) ? '0 0 16px rgba(0, 229, 255, 0.2)' : '0 4px 14px rgba(0,0,0,0.3)';
    }
    const pill = document.getElementById('dynChPill' + i);
    if (pill) {
      pill.style.background = (i === ch) ? 'var(--cyan)' : 'var(--bg-core)';
      pill.style.color = (i === ch) ? '#000' : 'var(--text-main)';
      pill.style.borderColor = (i === ch) ? 'var(--cyan)' : 'var(--border-subtle)';
    }
  }
  const inCard = document.getElementById('deckCardIn');
  if (inCard) inCard.classList.toggle('active', ch === 0);
  
  // Update Channel Labels in views
  const chLabel = `— OUT ${ch}`;
  ['eqChannelLabel', 'xovChannelLabel', 'compChannelLabel', 'limChannelLabel', 'dynChannelLabel'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = chLabel;
  });

  loadChannelSettingsIntoUi();
  renderXovGraph();
}

// Load channel settings into detailed editors
function loadChannelSettingsIntoUi() {
  if (!STATE.channels || !STATE.channels[activeChannel]) return;
  const c = STATE.channels[activeChannel];

  // EQ
  for (let b = 1; b <= 4; b++) {
    const eq = c.eq[b];
    if (eq) {
      document.getElementById('eqGain' + b).value = eq.gain;
      document.getElementById('eqFreq' + b).value = eq.freq;
      document.getElementById('eqQ' + b).value = eq.q;
      document.getElementById('eqType' + b).value = eq.mode || 'PEQ';
      updateEqBandLabels(b);
    }
  }
  renderEqGraph();

  // Xover
  document.getElementById('xovHpFreq').value = c.lowcut_freq || 35;
  document.getElementById('xovHpSlope').value = c.lowcut_slope || '24dB Linkwitz';
  document.getElementById('xovLpFreq').value = c.highcut_freq || 120;
  document.getElementById('xovLpSlope').value = c.highcut_slope || '24dB Linkwitz';
  renderXovGraph();

  // Dynamics
  document.getElementById('compThresh').value = c.comp.thresh;
  document.getElementById('compRatio').value = c.comp.ratio;
  document.getElementById('compAttack').value = c.comp.attack;
  document.getElementById('compRelease').value = c.comp.release;
  updateCompDisplay();

  document.getElementById('limThresh').value = c.limiter.thresh;
  document.getElementById('limRelease').value = c.limiter.release;
  updateLimDisplay();
}

function selectEqBand(b) {
  activeEqBand = b;
  document.querySelectorAll('.eq-band-card').forEach((card, idx) => {
    card.classList.toggle('selected', (idx + 1) === b);
  });
  renderEqGraph();
}

function updateEqBandLabels(b) {
  const g = parseFloat(document.getElementById('eqGain' + b).value);
  const f = parseFloat(document.getElementById('eqFreq' + b).value);
  const q = parseFloat(document.getElementById('eqQ' + b).value);
  
  document.getElementById('eqGainVal' + b).textContent = (g > 0 ? '+' : '') + g.toFixed(1) + ' dB';
  document.getElementById('eqFreqVal' + b).textContent = f >= 1000 ? (f / 1000).toFixed(1) + ' kHz' : f.toFixed(0) + ' Hz';
  document.getElementById('eqQVal' + b).textContent = q.toFixed(1);
}

function onEqParamChange(b) {
  updateEqBandLabels(b);
  if (STATE.channels && STATE.channels[activeChannel]) {
    const eq = STATE.channels[activeChannel].eq[b];
    eq.gain = parseFloat(document.getElementById('eqGain' + b).value);
    eq.freq = parseFloat(document.getElementById('eqFreq' + b).value);
    eq.q = parseFloat(document.getElementById('eqQ' + b).value);
  }
  renderEqGraph();
}

function onEqTypeChange(b, val) {
  if (STATE.channels && STATE.channels[activeChannel]) {
    STATE.channels[activeChannel].eq[b].mode = val;
  }
  renderEqGraph();
}

function resetEqFlat() {
  if (!STATE.channels || !STATE.channels[activeChannel]) return;
  for (let b = 1; b <= 4; b++) {
    document.getElementById('eqGain' + b).value = 0;
    STATE.channels[activeChannel].eq[b].gain = 0;
    updateEqBandLabels(b);
  }
  renderEqGraph();
  applyEqHardware();
}

function applyEqHardware(e) {
  const btn = (e && e.target) ? e.target : document.getElementById('btnApplyEq');
  const done = triggerBtnFeedback(btn);
  const ch = activeChannel;
  const eqData = STATE.channels && STATE.channels[ch] ? STATE.channels[ch].eq : {};
  fetch('/api/eq', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel: ch, eq: eqData })
  }).then(r => r.json()).then(d => {
    if (done) done(d.status === 'ok');
  }).catch(() => { if (done) done(false); });
}

function applyXoverHardware(e) {
  const btn = (e && e.target) ? e.target : document.getElementById('btnApplyXov');
  const done = triggerBtnFeedback(btn);
  const ch = activeChannel;
  const hp_freq = parseFloat(document.getElementById('xovHpFreq').value);
  const hp_slope = document.getElementById('xovHpSlope').value;
  const lp_freq = parseFloat(document.getElementById('xovLpFreq').value);
  const lp_slope = document.getElementById('xovLpSlope').value;

  fetch('/api/xover', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      channel: ch,
      hp_freq: hp_freq,
      hp_slope: hp_slope,
      lp_freq: lp_freq,
      lp_slope: lp_slope
    })
  }).then(r => r.json()).then(d => {
    if (d.status === 'ok') {
      if (STATE.channels && STATE.channels[ch]) {
        STATE.channels[ch].lowcut_freq = hp_freq;
        STATE.channels[ch].lowcut_slope = hp_slope;
        STATE.channels[ch].highcut_freq = lp_freq;
        STATE.channels[ch].highcut_slope = lp_slope;
      }
      if (done) done(true);
    } else {
      if (done) done(false);
    }
  }).catch(() => { if (done) done(false); });
}

function updateCompDisplay() {
  const t = parseFloat(document.getElementById('compThresh').value);
  const r = parseFloat(document.getElementById('compRatio').value);
  const a = parseFloat(document.getElementById('compAttack').value);
  const rel = parseFloat(document.getElementById('compRelease').value);
  document.getElementById('compThreshVal').textContent = t.toFixed(1) + ' dB';
  document.getElementById('compRatioVal').textContent = r.toFixed(1) + ' : 1';
  document.getElementById('compAttackVal').textContent = a.toFixed(1) + ' ms';
  document.getElementById('compReleaseVal').textContent = rel.toFixed(0) + ' ms';
  renderCompGraph();
}

function triggerBtnFeedback(btn) {
  if (!btn) return null;
  const origText = btn.textContent;
  btn.textContent = 'APPLYING...';
  btn.style.borderColor = 'var(--cyan)';
  btn.style.color = 'var(--cyan)';
  return function(success) {
    if (success) {
      btn.textContent = 'APPLIED ✓';
      btn.style.background = '#10b981';
      btn.style.borderColor = '#34d399';
      btn.style.color = '#fff';
    } else {
      btn.textContent = 'ERROR ✗';
      btn.style.background = '#ef4444';
      btn.style.borderColor = '#f87171';
      btn.style.color = '#fff';
    }
    setTimeout(() => {
      btn.textContent = origText;
      btn.style.background = '';
      btn.style.borderColor = '';
      btn.style.color = '';
    }, 1400);
  };
}

function applyCompHardware(e) {
  const btn = (e && e.target) ? e.target : document.getElementById('btnApplyComp');
  const done = triggerBtnFeedback(btn);
  const ch = activeChannel;
  const cData = {
    channel: ch,
    thresh: parseFloat(document.getElementById('compThresh').value),
    ratio: parseFloat(document.getElementById('compRatio').value),
    attack: parseFloat(document.getElementById('compAttack').value),
    release: parseFloat(document.getElementById('compRelease').value)
  };
  fetch('/api/comp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cData)
  }).then(r => r.json()).then(d => {
    if (d.status === 'ok') {
      if (STATE.channels && STATE.channels[ch]) {
        STATE.channels[ch].comp = { ...cData };
      }
      if (done) done(true);
    } else {
      if (done) done(false);
    }
  }).catch(() => { if (done) done(false); });
}

function updateLimDisplay() {
  const t = parseFloat(document.getElementById('limThresh').value);
  const rel = parseFloat(document.getElementById('limRelease').value);
  document.getElementById('limThreshVal').textContent = t.toFixed(1) + ' dB';
  document.getElementById('limReleaseVal').textContent = rel.toFixed(0) + ' ms';
  renderLimGraph();
}

function applyLimiterHardware(e) {
  const btn = (e && e.target) ? e.target : document.getElementById('btnApplyLim');
  const done = triggerBtnFeedback(btn);
  const ch = activeChannel;
  const lData = {
    channel: ch,
    thresh: parseFloat(document.getElementById('limThresh').value),
    release: parseFloat(document.getElementById('limRelease').value)
  };
  fetch('/api/limiter', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(lData)
  }).then(r => r.json()).then(d => {
    if (d.status === 'ok') {
      if (STATE.channels && STATE.channels[ch]) {
        STATE.channels[ch].limiter = { ...lData };
      }
      if (done) done(true);
    } else {
      if (done) done(false);
    }
  }).catch(() => { if (done) done(false); });
}

function applyDynamicsHardware(e) {
  const btn = (e && e.target) ? e.target : document.getElementById('btnApplyDyn');
  const done = triggerBtnFeedback(btn);
  const ch = activeChannel;
  const cData = {
    channel: ch,
    thresh: parseFloat(document.getElementById('compThresh').value),
    ratio: parseFloat(document.getElementById('compRatio').value),
    attack: parseFloat(document.getElementById('compAttack').value),
    release: parseFloat(document.getElementById('compRelease').value)
  };
  const lData = {
    channel: ch,
    thresh: parseFloat(document.getElementById('limThresh').value),
    release: parseFloat(document.getElementById('limRelease').value)
  };
  const p1 = fetch('/api/comp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cData)
  }).then(r => r.json());
  const p2 = fetch('/api/limiter', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(lData)
  }).then(r => r.json());

  Promise.all([p1, p2]).then(([d1, d2]) => {
    const ok = (d1.status === 'ok' && d2.status === 'ok');
    if (ok && STATE.channels && STATE.channels[ch]) {
      STATE.channels[ch].comp = { ...cData };
      STATE.channels[ch].limiter = { ...lData };
    }
    if (done) done(ok);
  }).catch(() => { if (done) done(false); });
}

// Faders & Level Handlers
function onFaderChange(ch, val) {
  isInteracting = true;
  val = parseFloat(val);
  const str = (val > 0 ? '+' : '') + val.toFixed(1) + ' dB';
  document.getElementById('faderVal' + ch).textContent = str;
  document.getElementById('deckLevel' + ch).textContent = str;
}

function sendFaderChange(ch, val) {
  isInteracting = false;
  fetch('/api/level', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel: ch, level: parseFloat(val) })
  });
}

// Mute & Polarity
function toggleMute(ch, e) {
  if (e) e.stopPropagation();
  if (!STATE.channels) return;
  const c = STATE.channels[ch];
  c.muted = !c.muted;
  updateChannelMuteVisuals(ch, c.muted);
  fetch('/api/mute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel: ch, muted: c.muted ? 1 : 0 })
  });
}

function updateChannelMuteVisuals(ch, isMuted) {
  const dm = document.getElementById('deckMute' + ch);
  const cm = document.getElementById('cfsMute' + ch);
  if (dm) dm.classList.toggle('muted', isMuted);
  if (cm) cm.classList.toggle('muted', isMuted);
}

function togglePolarity(ch) {
  if (!STATE.channels) return;
  const c = STATE.channels[ch];
  c.polarity = (c.polarity === 'NORMAL') ? 'INVERTED' : 'NORMAL';
  const isInv = (c.polarity === 'INVERTED');
  
  updatePolarityVisuals(ch, isInv);

  fetch('/api/polarity', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel: ch, polarity: c.polarity })
  });
}

function updatePolarityVisuals(ch, isInv) {
  const pb = document.getElementById('polBtn' + ch);
  const dp = document.getElementById('deckPol' + ch);
  if (pb) {
    pb.classList.toggle('pol-inv', isInv);
    pb.innerHTML = isInv ? 'Ø <span style="font-size:9px;font-weight:800;">180°</span>' : 'Ø';
  }
  if (dp) {
    dp.classList.toggle('pol-inv', isInv);
    dp.textContent = isInv ? 'Ø 180°' : 'Ø';
  }
}

// Delay Handlers
function onDelayChange(ch, val) {
  val = parseFloat(val);
  document.getElementById('dlyReadout' + ch).textContent = val.toFixed(3) + ' ms';
  const m = (val * 0.343).toFixed(2);
  const ft = (val * 1.125).toFixed(1);
  document.getElementById('dlyDist' + ch).textContent = `(${m} m / ${ft} ft)`;
}

function sendDelayHardware(ch, val, e) {
  const btn = (e && e.target) ? e.target : null;
  const done = triggerBtnFeedback(btn);
  fetch('/api/delay', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel: ch, delay: parseFloat(val) })
  }).then(r => r.json()).then(d => {
    if (done) done(d.status === 'ok');
  }).catch(() => { if (done) done(false); });
}

// Presets
function recallPreset(num) {
  fetch('/api/preset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ preset: num })
  }).then(() => {
    setTimeout(forceSync, 600);
  });
}

function emergencyMuteAll() {
  fetch('/api/mute_all', { method: 'POST' }).then(() => forceSync());
}

function unmuteAll() {
  fetch('/api/unmute_all', { method: 'POST' }).then(() => forceSync());
}

function forceSync() {
  fetch('/api/sync', { method: 'POST' }).then(() => {
    fetch('/api/state').then(r => r.json()).then(applyState);
  });
}

// CANVAS DRAWING ENGINES
function freqToX(f, W) {
  const minF = Math.log10(20), maxF = Math.log10(20000);
  return ((Math.log10(Math.max(20, Math.min(20000, f))) - minF) / (maxF - minF)) * W;
}

function xToFreq(x, W) {
  const minF = Math.log10(20), maxF = Math.log10(20000);
  return Math.pow(10, minF + (x / W) * (maxF - minF));
}

function renderEqGraph() {
  const cvs = document.getElementById('eqCanvas');
  if (!cvs || !cvs.parentElement) return;
  cvs.width = cvs.parentElement.clientWidth;
  cvs.height = cvs.parentElement.clientHeight;
  const ctx = cvs.getContext('2d');
  const W = cvs.width, H = cvs.height;
  ctx.clearRect(0, 0, W, H);

  const zeroY = H * 0.5;
  const dbScale = H / 36; // Range: -18 to +18 dB

  // Grid lines
  [-15, -10, -5, 0, 5, 10, 15].forEach(db => {
    const y = zeroY - db * dbScale;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(W, y);
    ctx.strokeStyle = (db === 0) ? '#1e3a5f' : '#0c1829';
    ctx.lineWidth = (db === 0) ? 1.5 : 1;
    ctx.stroke();
  });

  [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000].forEach(f => {
    const x = freqToX(f, W);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, H);
    ctx.strokeStyle = '#0c1829';
    ctx.lineWidth = 1;
    ctx.stroke();
  });

  const ch = STATE.channels ? STATE.channels[activeChannel] : null;
  if (!ch) return;

  function calcResponse(f) {
    let totGain = 0;
    for (let b = 1; b <= 4; b++) {
      const eq = ch.eq[b];
      if (!eq || eq.gain === 0) continue;
      const f0 = eq.freq || 1000;
      const q = eq.q || 1.4;
      const octDiff = (Math.log10(f) - Math.log10(f0)) / (1.0 / q);
      totGain += eq.gain * Math.exp(-0.5 * octDiff * octDiff);
    }
    return totGain;
  }

  // Draw fill under curve
  ctx.beginPath();
  for (let x = 0; x <= W; x += 2) {
    const f = xToFreq(x, W);
    const y = zeroY - calcResponse(f) * dbScale;
    if (x === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.lineTo(W, H);
  ctx.lineTo(0, H);
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, 'rgba(0, 229, 255, 0.18)');
  grad.addColorStop(1, 'rgba(0, 229, 255, 0.01)');
  ctx.fillStyle = grad;
  ctx.fill();

  // Draw response line
  ctx.beginPath();
  ctx.strokeStyle = '#00e5ff';
  ctx.lineWidth = 2.5;
  ctx.shadowColor = 'rgba(0, 229, 255, 0.6)';
  ctx.shadowBlur = 8;
  for (let x = 0; x <= W; x += 2) {
    const f = xToFreq(x, W);
    const y = zeroY - calcResponse(f) * dbScale;
    if (x === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Draw Band Nodes
  const bandColors = ['#22d3ee', '#2dd4bf', '#f43f5e', '#fb923c'];
  for (let b = 1; b <= 4; b++) {
    const eq = ch.eq[b];
    if (!eq) continue;
    const nx = freqToX(eq.freq, W);
    const ny = zeroY - calcResponse(eq.freq) * dbScale;

    ctx.beginPath();
    ctx.arc(nx, ny, (b === activeEqBand) ? 9 : 7, 0, Math.PI * 2);
    ctx.fillStyle = bandColors[b - 1];
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = (b === activeEqBand) ? 2.5 : 1.5;
    ctx.fill();
    ctx.stroke();
  }
}

function getFilterSlopeVal(slopeStr) {
  if (!slopeStr || slopeStr.includes('THRU')) return 0;
  if (slopeStr.includes('6dB')) return 6;
  if (slopeStr.includes('12dB')) return 12;
  if (slopeStr.includes('18dB')) return 18;
  return 24;
}

function calcXovAtten(f, hp, hpSlope, lp, lpSlope) {
  let atten = 0;
  const sHp = getFilterSlopeVal(hpSlope);
  const sLp = getFilterSlopeVal(lpSlope);
  
  if (sHp > 0 && f < hp) {
    atten += sHp * Math.log2(hp / f);
  }
  if (sLp > 0 && f > lp) {
    atten += sLp * Math.log2(f / lp);
  }
  return Math.min(54, atten);
}

function renderXovGraph() {
  const cvs = document.getElementById('xovCanvas');
  if (!cvs || !cvs.parentElement) return;
  cvs.width = cvs.parentElement.clientWidth;
  cvs.height = cvs.parentElement.clientHeight;
  const ctx = cvs.getContext('2d');
  const W = cvs.width, H = cvs.height;
  ctx.clearRect(0, 0, W, H);

  const topY = 24;
  const botY = H - 28;
  const usableH = botY - topY;

  // Grid Lines (Log Frequencies)
  [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000].forEach(f => {
    const x = freqToX(f, W);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, H);
    ctx.strokeStyle = '#0c1829';
    ctx.lineWidth = 1;
    ctx.stroke();
  });

  // Horizontal dB Lines (0, -12, -24, -36, -48 dB)
  [0, 12, 24, 36, 48].forEach(db => {
    const y = topY + (db / 48) * usableH;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(W, y);
    ctx.strokeStyle = (db === 0) ? '#1e3a5f' : '#0c1829';
    ctx.lineWidth = (db === 0) ? 1.5 : 1;
    ctx.stroke();
  });

  const chColors = ['#ff6b2b', '#00b4d8', '#d946ef', '#10b981'];

  // Update Legend lines (solid for activeChannel, dashed for other channels)
  for (let ch = 1; ch <= 4; ch++) {
    const legLine = document.getElementById('xovLegLine' + ch);
    if (legLine) {
      if (ch === activeChannel) {
        legLine.className = 'xov-leg-line';
        legLine.style.background = chColors[ch - 1];
        legLine.style.borderTop = 'none';
        legLine.style.height = '3px';
      } else {
        legLine.className = 'xov-leg-line dashed';
        legLine.style.background = 'none';
        legLine.style.borderTop = '2px dashed ' + chColors[ch - 1];
        legLine.style.height = '0';
      }
    }
  }

  // Active channel live settings
  const hpLive = parseFloat(document.getElementById('xovHpFreq').value) || 35;
  const lpLive = parseFloat(document.getElementById('xovLpFreq').value) || 120;
  const hpSlopeLive = document.getElementById('xovHpSlope').value;
  const lpSlopeLive = document.getElementById('xovLpSlope').value;
  document.getElementById('xovHpFreqVal').textContent = hpLive + ' Hz';
  document.getElementById('xovLpFreqVal').textContent = lpLive + ' Hz';

  // Keep STATE synchronized with slider adjustments for accurate dashed previews
  if (STATE.channels && STATE.channels[activeChannel]) {
    STATE.channels[activeChannel].lowcut_freq = hpLive;
    STATE.channels[activeChannel].lowcut_slope = hpSlopeLive;
    STATE.channels[activeChannel].highcut_freq = lpLive;
    STATE.channels[activeChannel].highcut_slope = lpSlopeLive;
  }

  // 1. Draw PREVIEWS of other channels as DASHED lines
  for (let ch = 1; ch <= 4; ch++) {
    if (ch === activeChannel) continue;
    const cData = STATE.channels ? STATE.channels[ch] : null;
    if (!cData) continue;

    const hp = cData.lowcut_freq || 35;
    const hpSlope = cData.lowcut_slope || '24dB Linkwitz';
    const lp = cData.highcut_freq || 120;
    const lpSlope = cData.highcut_slope || '24dB Linkwitz';

    ctx.beginPath();
    ctx.setLineDash([5, 4]);
    ctx.lineWidth = 1.8;
    ctx.strokeStyle = chColors[ch - 1];
    ctx.globalAlpha = 0.65;

    for (let x = 0; x <= W; x += 3) {
      const f = xToFreq(x, W);
      const atten = calcXovAtten(f, hp, hpSlope, lp, lpSlope);
      const y = topY + (atten / 48) * usableH;
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Channel badge text near peak of the bandpass
    const centerFreq = Math.sqrt(Math.max(20, hp) * Math.min(20000, lp));
    const badgeX = freqToX(centerFreq, W);
    ctx.fillStyle = chColors[ch - 1];
    ctx.font = 'bold 9px monospace';
    ctx.fillText('OUT ' + ch, Math.max(10, Math.min(W - 45, badgeX - 14)), topY + 14);
  }

  // Reset dash and alpha for active channel
  ctx.setLineDash([]);
  ctx.globalAlpha = 1.0;

  // 2. Draw ACTIVE CHANNEL as 1 SINGLE COMBINED BANDPASS GRAPH (Solid + Gradient Area)
  const actColor = chColors[activeChannel - 1];

  // Fill gradient
  ctx.beginPath();
  for (let x = 0; x <= W; x += 2) {
    const f = xToFreq(x, W);
    const atten = calcXovAtten(f, hpLive, hpSlopeLive, lpLive, lpSlopeLive);
    const y = topY + (atten / 48) * usableH;
    if (x === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.lineTo(W, H);
  ctx.lineTo(0, H);
  const grad = ctx.createLinearGradient(0, topY, 0, H);
  grad.addColorStop(0, actColor + '44');
  grad.addColorStop(1, actColor + '04');
  ctx.fillStyle = grad;
  ctx.fill();

  // Solid curve line
  ctx.beginPath();
  ctx.strokeStyle = actColor;
  ctx.lineWidth = 3.0;
  ctx.shadowColor = actColor;
  ctx.shadowBlur = 10;
  for (let x = 0; x <= W; x += 2) {
    const f = xToFreq(x, W);
    const atten = calcXovAtten(f, hpLive, hpSlopeLive, lpLive, lpSlopeLive);
    const y = topY + (atten / 48) * usableH;
    if (x === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Draw HPF and LPF cutoff vertical marker lines & dots
  [ { f: hpLive, label: 'HPF ' + hpLive.toFixed(0) + ' Hz', align: 'left' },
    { f: lpLive, label: 'LPF ' + (lpLive >= 1000 ? (lpLive/1000).toFixed(1)+'k' : lpLive.toFixed(0)) + ' Hz', align: 'right' }
  ].forEach(pt => {
    const px = freqToX(pt.f, W);
    const py = topY + (3 / 48) * usableH; // -3dB knee point
    ctx.beginPath();
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = actColor;
    ctx.lineWidth = 1;
    ctx.moveTo(px, topY);
    ctx.lineTo(px, botY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Node circle
    ctx.beginPath();
    ctx.arc(px, py, 6, 0, Math.PI * 2);
    ctx.fillStyle = actColor;
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.fill();
    ctx.stroke();

    // Cutoff text label
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 10px monospace';
    const tx = (pt.align === 'left') ? px + 8 : px - 82;
    ctx.fillText(pt.label, Math.max(10, Math.min(W - 85, tx)), topY + 30);
  });
}

function renderCompGraph() {
  const cvs = document.getElementById('compCanvas');
  if (!cvs || !cvs.parentElement) return;
  cvs.width = cvs.parentElement.clientWidth;
  cvs.height = cvs.parentElement.clientHeight;
  const ctx = cvs.getContext('2d');
  const W = cvs.width, H = cvs.height;
  ctx.clearRect(0, 0, W, H);

  const thresh = parseFloat(document.getElementById('compThresh').value) || -18;
  const ratio = parseFloat(document.getElementById('compRatio').value) || 4;
  const tx = ((thresh + 40) / 40) * W;

  ctx.beginPath();
  ctx.strokeStyle = '#14b8a6';
  ctx.lineWidth = 2.5;
  ctx.moveTo(0, H);
  ctx.lineTo(tx, H - (tx / W) * H);
  const grY = (W - tx) / ratio;
  ctx.lineTo(W, H - (tx / W) * H - grY);
  ctx.stroke();

  // Threshold marker
  ctx.beginPath();
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = 'rgba(20, 184, 166, 0.5)';
  ctx.moveTo(tx, 0); ctx.lineTo(tx, H);
  ctx.stroke();
  ctx.setLineDash([]);
}

function renderLimGraph() {
  const cvs = document.getElementById('limCanvas');
  if (!cvs || !cvs.parentElement) return;
  cvs.width = cvs.parentElement.clientWidth;
  cvs.height = cvs.parentElement.clientHeight;
  const ctx = cvs.getContext('2d');
  const W = cvs.width, H = cvs.height;
  ctx.clearRect(0, 0, W, H);

  const thresh = parseFloat(document.getElementById('limThresh').value) || -6;
  const tx = ((thresh + 20) / 40) * W;

  ctx.beginPath();
  ctx.strokeStyle = '#ef4444';
  ctx.lineWidth = 2.5;
  ctx.moveTo(0, H);
  ctx.lineTo(tx, H - (tx / W) * H);
  ctx.lineTo(W, H - (tx / W) * H);
  ctx.stroke();
}

// STATE UPDATE & METERS
function applyState(data) {
  STATE = data;
  if (!data) return;

  // Header
  document.getElementById('hdrDev').textContent = data.device_name || 'EV DX38';
  document.getElementById('hdrMode').textContent = data.routing_mode || 'TWOWAY';
  document.getElementById('hdrPresetNum').textContent = data.preset_num || '—';
  document.getElementById('hdrPresetName').textContent = data.preset_name || '—';

  // Link status indicator
  const linkText = document.getElementById('hdrLinkText');
  const linkDot = document.getElementById('hdrLinkDot');
  if (linkText && linkDot) {
    if (data.connected) {
      linkText.textContent = 'RS-232 COM2 ONLINE';
      linkDot.style.background = 'var(--green)';
      linkDot.style.boxShadow = '0 0 8px var(--green)';
    } else {
      linkText.textContent = 'OFFLINE / DEMO (AUTO-RECONNECT)';
      linkDot.style.background = 'var(--amber)';
      linkDot.style.boxShadow = '0 0 8px var(--amber)';
    }
  }
  document.getElementById('ovwMode').textContent = data.routing_mode;
  document.getElementById('ovwPreset').textContent = `[${data.preset_num}] ${data.preset_name}`;
  document.getElementById('preLibActive').textContent = data.preset_num;
  document.getElementById('rtgModeLabel').textContent = data.routing_mode;

  // Highlight active preset card
  document.querySelectorAll('.preset-card').forEach(pc => pc.classList.remove('active'));
  const activePc = document.getElementById('preCard' + data.preset_num);
  if (activePc) activePc.classList.add('active');

  // Channels
  for (let ch = 1; ch <= 4; ch++) {
    const c = data.channels[ch];
    if (!c) continue;

    // Only update faders when user is not dragging
    if (!isInteracting && document.activeElement !== document.getElementById('fader' + ch)) {
      document.getElementById('fader' + ch).value = c.level;
      const str = (c.level > 0 ? '+' : '') + c.level.toFixed(1) + ' dB';
      document.getElementById('faderVal' + ch).textContent = str;
      document.getElementById('deckLevel' + ch).textContent = str;
    }

    // Mutes
    updateChannelMuteVisuals(ch, c.muted);

    // Polarity
    const isInv = (c.polarity === 'INVERTED');
    updatePolarityVisuals(ch, isInv);

    // Delay
    const dly = parseFloat(c.delay) || 0;
    if (document.activeElement !== document.getElementById('dlySlider' + ch)) {
      document.getElementById('dlySlider' + ch).value = dly;
      onDelayChange(ch, dly);
    }
  }

  // Live VU updates with -30 dB LUFS scale
  if (data.vu) {
    applyVuMeters(data.vu, data.vu_steps, data.comp);
  }
}

function applyVuMeters(vu, steps, comp) {
  if (!vu) return;
  // vu is percentage [in1, in2, out1, out2, out3, out4] (0 to 100%)
  // steps is hardware dB step count above -30 dB (0 = below -30 dB, 1..30 = -30 dB to 0 dB, >30 = CLIP)
  
  // Deck mini meters
  const in1 = vu[0] || 0, in2 = vu[1] || 0;
  const vuIn1 = document.getElementById('vuIn1');
  const vuIn2 = document.getElementById('vuIn2');
  if (vuIn1) vuIn1.style.width = in1 + '%';
  if (vuIn2) vuIn2.style.width = in2 + '%';

  for (let ch = 1; ch <= 4; ch++) {
    const val = vu[ch + 1] || 0;
    const s = steps ? (steps[ch + 1] || 0) : Math.round((val / 100) * 30);
    const dvu = document.getElementById('deckVu' + ch);
    if (dvu) dvu.style.width = val + '%';

    // Update COMP LED indicators (Overview, Deck, and Meter Bridge)
    const isComp = comp ? !!comp[ch - 1] : false;
    const cLed = document.getElementById('compLed' + ch);
    if (cLed) cLed.classList.toggle('lit-comp', isComp);
    const dComp = document.getElementById('deckComp' + ch);
    if (dComp) dComp.classList.toggle('lit-comp', isComp);
    const mbComp = document.getElementById('mbComp' + ch);
    if (mbComp) mbComp.classList.toggle('lit-comp', isComp);

    // Overview Fader Strip LED Ladder (20 segments, calibrated -30 dB to 0 dB / CLIP)
    const activeSegs = (s <= 0) ? 0 : Math.min(20, Math.max(1, Math.round((s / 30) * 20)));
    for (let i = 0; i < 20; i++) {
      const led = document.getElementById(`led_${ch}_${i}`);
      if (led) {
        led.className = 'v-led';
        if (i < activeSegs) {
          if (i < 12) led.classList.add('lit-g');      // -30 dB to -12 dB (Green)
          else if (i < 16) led.classList.add('lit-y'); // -12 dB to -6 dB (Yellow)
          else if (i < 19) led.classList.add('lit-o'); // -6 dB to 0 dB (Orange)
          else led.classList.add('lit-r');             // >= 0 dB (Red / CLIP)
        }
      }
    }
  }

  // Full Meter Bridge (6 channels, 24 segments, Hardware -30 dB LUFS scale)
  for (let idx = 0; idx < 6; idx++) {
    const s = steps ? (steps[idx] || 0) : 0;
    const activeSegs = (s <= 0) ? 0 : Math.min(24, Math.max(1, Math.round((s / 30) * 24)));
    
    for (let segIdx = 0; segIdx < 24; segIdx++) {
      const seg = document.getElementById(`mbSeg_${idx}_${segIdx}`);
      if (seg) {
        if (segIdx < activeSegs) {
          // Hardware LED color bands matching EV Dx38 scale:
          // seg 0-9: -30 dB to -18 dB (Green #10b981)
          // seg 10-14: -18 dB to -12 dB (Lime #22c55e)
          // seg 15-18: -12 dB to -6 dB (Yellow #eab308)
          // seg 19-21: -6 dB to 0 dB (Amber/Orange #f97316)
          // seg 22-23: 0 dB to CLIP (Red #ef4444)
          seg.style.background = (segIdx < 10) ? '#10b981' :
                                 (segIdx < 15) ? '#22c55e' :
                                 (segIdx < 19) ? '#eab308' :
                                 (segIdx < 22) ? '#f97316' : '#ef4444';
          seg.style.boxShadow = (segIdx >= 22) ? '0 0 8px #ef4444' : 'none';
        } else {
          seg.style.background = '#0e1526';
          seg.style.boxShadow = 'none';
        }
      }
    }

    const pkEl = document.getElementById('mbPeak' + idx);
    if (pkEl) {
      if (s <= 0) {
        pkEl.textContent = '< -30.0 dB LUFS';
        pkEl.style.color = 'var(--text-muted)';
      } else {
        const db = -30.0 + s * 1.0;
        pkEl.textContent = (db > 0 ? '+' : '') + db.toFixed(1) + ' dB LUFS';
        pkEl.style.color = (db >= 0) ? '#ef4444' : (db > -6) ? '#f59e0b' : (db > -18) ? 'var(--cyan)' : '#10b981';
      }
    }
  }
}

// Initial fetch and fast polling
fetch('/api/state').then(r => r.json()).then(data => {
  applyState(data);
  loadChannelSettingsIntoUi();
});

setInterval(() => {
  fetch('/api/state').then(r => r.json()).then(applyState);
}, 180);

window.addEventListener('resize', () => {
  renderEqGraph();
  renderXovGraph();
  renderCompGraph();
  renderLimGraph();
});
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/state')
def get_state():
    return jsonify(device_state)

@app.route('/api/level', methods=['POST'])
def set_level():
    data = request.json
    try:
        ch = int(data.get('channel', 1))
        lvl = float(data.get('level', 0.0))
        if ch in device_state['channels']:
            device_state['channels'][ch]['level'] = lvl
            if ser:
                ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Level {lvl:.1f}")
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "ok"})

@app.route('/api/mute', methods=['POST'])
def set_mute():
    data = request.json
    try:
        ch = int(data.get('channel', 1))
        muted = 1 if data.get('muted') in [1, True, "1", "true"] else 0
        if ch in device_state['channels']:
            device_state['channels'][ch]['muted'] = (muted == 1)
            if ser:
                ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Mute {muted}")
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "ok"})

@app.route('/api/polarity', methods=['POST'])
def set_polarity():
    data = request.json
    try:
        ch = int(data.get('channel', 1))
        pol = 'INVERTED' if data.get('polarity') == 'INVERTED' else 'NORMAL'
        if ch in device_state['channels']:
            device_state['channels'][ch]['polarity'] = pol
            if ser:
                ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Polarity {pol}")
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "ok"})

@app.route('/api/delay', methods=['POST'])
def set_delay():
    data = request.json
    try:
        ch = int(data.get('channel', 1))
        dly = float(data.get('delay', 0.0))
        if ch in device_state['channels']:
            device_state['channels'][ch]['delay'] = f"{dly:.3f}"
            if ser:
                ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Delay {dly:.3f}")
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "ok"})

@app.route('/api/preset', methods=['POST'])
def set_preset():
    data = request.json
    try:
        p = int(data.get('preset', 1))
        if ser:
            ser.send_cmd(f"/ID{DEVICE_ID}/Recall {p}")
            time.sleep(0.5)
            sync_hardware()
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "ok"})

@app.route('/api/routing', methods=['POST'])
def set_routing():
    data = request.json
    mode = data.get('mode', 'TWOWAY')
    device_state['routing_mode'] = mode
    if ser:
        ser.send_cmd(f"/ID{DEVICE_ID}/Misc/Config {mode}")
    return jsonify({"status": "ok"})

@app.route('/api/sync', methods=['POST'])
def do_sync():
    sync_hardware()
    return jsonify({"status": "ok"})

@app.route('/api/mute_all', methods=['POST'])
def mute_all():
    for ch in range(1, 5):
        device_state['channels'][ch]['muted'] = True
        if ser:
            ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Mute 1")
    return jsonify({"status": "ok"})

@app.route('/api/unmute_all', methods=['POST'])
def unmute_all():
    for ch in range(1, 5):
        device_state['channels'][ch]['muted'] = False
        if ser:
            ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Mute 0")
    return jsonify({"status": "ok"})

def map_slope(slope_str: str) -> str:
    s = str(slope_str).upper()
    if "THRU" in s or "OFF" in s: return "THRU"
    if "LINKWITZ" in s:
        return "LINKWITZ_24DB" if "24" in s else "LINKWITZ_12DB"
    if "BUTTER" in s:
        if "24" in s: return "BUTTER_24DB"
        if "18" in s: return "BUTTER_18DB"
        return "BUTTER_12DB"
    if "BESSEL" in s:
        if "24" in s: return "BESSEL_24DB"
        if "18" in s: return "BESSEL_18DB"
        return "BESSEL_12DB"
    if "6DB" in s: return "6DB"
    return "LINKWITZ_24DB"

@app.route('/api/eq', methods=['POST'])
def set_eq():
    data = request.json
    try:
        ch = int(data.get('channel', 1))
        eq_data = data.get('eq', {})
        if ch in device_state['channels']:
            for b_str, band_vals in eq_data.items():
                b = int(b_str)
                if b in device_state['channels'][ch]['eq']:
                    device_state['channels'][ch]['eq'][b].update(band_vals)
                    band = device_state['channels'][ch]['eq'][b]
                    if ser:
                        try:
                            f = int(float(band.get('freq', 1000)))
                            g = float(band.get('gain', 0.0))
                            q = float(band.get('q', 1.4))
                            m = str(band.get('mode', 'PEQ')).upper()
                            byp = 1 if band.get('bypass') else 0

                            # 1. Full RACE protocol specification (/DEVICE%d/OUTEQ/OUT%d/FILTER%d/...)
                            ser.send_cmd(f"/DEVICE{DEVICE_ID}/OUTEQ/OUT{ch}/FILTER{b}/TYPE {m}")
                            ser.send_cmd(f"/DEVICE{DEVICE_ID}/OUTEQ/OUT{ch}/FILTER{b}/FREQUENCY {f} 0")
                            ser.send_cmd(f"/DEVICE{DEVICE_ID}/OUTEQ/OUT{ch}/FILTER{b}/GAIN {int(g * 10)}")
                            ser.send_cmd(f"/DEVICE{DEVICE_ID}/OUTEQ/OUT{ch}/FILTER{b}/QUALITY {int(q * 100)}")
                            ser.send_cmd(f"/DEVICE{DEVICE_ID}/OUTEQ/OUT{ch}/FILTER{b}/BYPASS {byp}")

                            # 2. Dx38 Live mode short protocol (/ID%d/...)
                            ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Eq{b}/Freq {f}")
                            ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Eq{b}/Gain {g:.1f}")
                            ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Eq{b}/Q {q:.2f}")
                            ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Eq{b}/Type {m}")
                            ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Eq{b}/Bypass {byp}")
                            ser.send_cmd(f"/ID{DEVICE_ID}/OUT{ch}/EQ{b}/FREQ {f}")
                            ser.send_cmd(f"/ID{DEVICE_ID}/OUT{ch}/EQ{b}/GAIN {g:.1f}")
                        except Exception:
                            pass
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "ok"})

@app.route('/api/xover', methods=['POST'])
def set_xover():
    data = request.json
    try:
        ch = int(data.get('channel', 1))
        if ch in device_state['channels']:
            hp_freq = float(data.get('hp_freq', 35.0))
            hp_slope = str(data.get('hp_slope', '24dB Linkwitz'))
            lp_freq = float(data.get('lp_freq', 120.0))
            lp_slope = str(data.get('lp_slope', '24dB Linkwitz'))

            device_state['channels'][ch]['lowcut_freq'] = hp_freq
            device_state['channels'][ch]['lowcut_slope'] = hp_slope
            device_state['channels'][ch]['highcut_freq'] = lp_freq
            device_state['channels'][ch]['highcut_slope'] = lp_slope

            if ser:
                try:
                    hp_slope_cmd = map_slope(hp_slope)
                    lp_slope_cmd = map_slope(lp_slope)

                    # 1. Full RACE protocol specification (/DEVICE%d/XOVER/...)
                    # Highpass / Lowcut (Filter 1)
                    ser.send_cmd(f"/DEVICE{DEVICE_ID}/XOVER/OUT{ch}/FILTER1/PARTITION1/TYPE HIPASS")
                    ser.send_cmd(f"/DEVICE{DEVICE_ID}/XOVER/OUT{ch}/FILTER1/PARTITION1/FREQUENCY {int(hp_freq)} 0")
                    ser.send_cmd(f"/DEVICE{DEVICE_ID}/XOVER/OUT{ch}/FILTER1/PARTITION1/RESPSLOPE {hp_slope_cmd}")

                    # Lowpass / Highcut (Filter 2)
                    ser.send_cmd(f"/DEVICE{DEVICE_ID}/XOVER/OUT{ch}/FILTER2/PARTITION1/TYPE LOPASS")
                    ser.send_cmd(f"/DEVICE{DEVICE_ID}/XOVER/OUT{ch}/FILTER2/PARTITION1/FREQUENCY {int(lp_freq)} 0")
                    ser.send_cmd(f"/DEVICE{DEVICE_ID}/XOVER/OUT{ch}/FILTER2/PARTITION1/RESPSLOPE {lp_slope_cmd}")

                    # 2. Dx38 Live mode short protocol (/ID%d/...)
                    ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Hpf/Freq {int(hp_freq)}")
                    ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Hpf/Slope {hp_slope_cmd}")
                    ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Lpf/Freq {int(lp_freq)}")
                    ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Lpf/Slope {lp_slope_cmd}")
                    ser.send_cmd(f"/ID{DEVICE_ID}/OUT{ch}/HPF/FREQ {int(hp_freq)}")
                    ser.send_cmd(f"/ID{DEVICE_ID}/OUT{ch}/LPF/FREQ {int(lp_freq)}")
                except Exception:
                    pass
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "ok"})

@app.route('/api/comp', methods=['POST'])
def set_comp():
    data = request.json
    try:
        ch = int(data.get('channel', 1))
        if ch in device_state['channels']:
            c = device_state['channels'][ch]['comp']
            c['thresh'] = data.get('thresh', c['thresh'])
            c['ratio'] = data.get('ratio', c['ratio'])
            c['attack'] = data.get('attack', c['attack'])
            c['release'] = data.get('release', c['release'])
            if 'bypass' in data:
                c['bypass'] = bool(data['bypass'])
            if ser:
                try:
                    r_val = float(c['ratio'])
                    r_str = "1OVER4.0"
                    if r_val <= 1.2: r_str = "1OVER1.0"
                    elif r_val <= 1.7: r_str = "1OVER1.4"
                    elif r_val <= 3.0: r_str = "1OVER2.0"
                    elif r_val <= 6.0: r_str = "1OVER4.0"
                    else: r_str = "1OVER8.0"

                    # 1. Full RACE protocol specification (/DEVICE%d/CONTROL/OUT%d/...)
                    ser.send_cmd(f"/DEVICE{DEVICE_ID}/CONTROL/OUT{ch}/COMPRESSOR/THRESHOLD {int(c['thresh'])}")
                    ser.send_cmd(f"/DEVICE{DEVICE_ID}/CONTROL/OUT{ch}/COMPRESSOR/RATIO {r_str}")
                    ser.send_cmd(f"/DEVICE{DEVICE_ID}/CONTROL/OUT{ch}/COMPRESSOR/ATTACK {int(float(c['attack']))}")
                    ser.send_cmd(f"/DEVICE{DEVICE_ID}/CONTROL/OUT{ch}/COMPRESSOR/RELEASE {int(c['release'])}")
                    if 'bypass' in c:
                        ser.send_cmd(f"/DEVICE{DEVICE_ID}/CONTROL/OUT{ch}/COMPRESSOR/BYPASS {1 if c['bypass'] else 0}")

                    # 2. Dx38 Live mode short protocol (/ID%d/...)
                    ser.send_cmd(f"/ID{DEVICE_ID}/OUT{ch}/COMPRESSOR/THRESH {int(c['thresh'])}")
                    ser.send_cmd(f"/ID{DEVICE_ID}/OUT{ch}/COMPRESSOR/RATIO {r_str}")
                    ser.send_cmd(f"/ID{DEVICE_ID}/OUT{ch}/COMPRESSOR/ATTACK {float(c['attack']):.1f}")
                    ser.send_cmd(f"/ID{DEVICE_ID}/OUT{ch}/COMPRESSOR/RELEASE {int(c['release'])}")
                    ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Comp/Threshold {c['thresh']:.1f}")
                    ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Comp/Ratio {c['ratio']:.1f}")
                except Exception:
                    pass
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "ok"})

@app.route('/api/limiter', methods=['POST'])
def set_limiter():
    data = request.json
    try:
        ch = int(data.get('channel', 1))
        if ch in device_state['channels']:
            lm = device_state['channels'][ch]['limiter']
            lm['thresh'] = data.get('thresh', lm['thresh'])
            lm['release'] = data.get('release', lm['release'])
            if 'bypass' in data:
                lm['bypass'] = bool(data['bypass'])
            if ser:
                try:
                    # 1. Full RACE protocol specification (/DEVICE%d/CONTROL/OUT%d/...)
                    ser.send_cmd(f"/DEVICE{DEVICE_ID}/CONTROL/OUT{ch}/LIMITER/THRESHOLD {int(lm['thresh'])}")
                    ser.send_cmd(f"/DEVICE{DEVICE_ID}/CONTROL/OUT{ch}/LIMITER/RELEASE {int(lm['release'])}")
                    if 'bypass' in lm:
                        ser.send_cmd(f"/DEVICE{DEVICE_ID}/CONTROL/OUT{ch}/LIMITER/BYPASS {1 if lm['bypass'] else 0}")

                    # 2. Dx38 Live mode short protocol (/ID%d/...)
                    ser.send_cmd(f"/ID{DEVICE_ID}/OUT{ch}/LIMITER/THRESH {int(lm['thresh'])}")
                    ser.send_cmd(f"/ID{DEVICE_ID}/OUT{ch}/LIMITER/RELEASE {int(lm['release'])}")
                    ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Lim/Threshold {lm['thresh']:.1f}")
                except Exception:
                    pass
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    print("[*] EV Dx38 Pro Web Console")
    try:
        ser = WinSerial(COM_PORT)
        sync_hardware()
    except Exception as e:
        print(f"[-] Serial error: {e} (running in demo mode)")

    t = threading.Thread(target=background_loop, daemon=True)
    t.start()

    app.run(host='0.0.0.0', port=5000, debug=False)
