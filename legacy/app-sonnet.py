"""
Flask Web Controller — Electro-Voice Dx38
Adaptive DSP dashboard with dark professional console UI.
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
            raise Exception(f"Gagal buka port {port}. Error: {err}")

        timeouts = COMMTIMEOUTS()
        timeouts.ReadIntervalTimeout = 30
        timeouts.ReadTotalTimeoutConstant = 100
        timeouts.ReadTotalTimeoutMultiplier = 0
        timeouts.WriteTotalTimeoutConstant = 50
        timeouts.WriteTotalTimeoutMultiplier = 0
        ctypes.windll.kernel32.SetCommTimeouts(self.handle, ctypes.byref(timeouts))
        print(f"[+] WinSerial connected: {port}")

    def write(self, data: bytes):
        with self.lock:
            written = wintypes.DWORD()
            ctypes.windll.kernel32.WriteFile(self.handle, data, len(data), ctypes.byref(written), None)
            return written.value

    def read_clean(self, max_bytes=512):
        with self.lock:
            buf = ctypes.create_string_buffer(max_bytes)
            bytes_read = wintypes.DWORD()
            ctypes.windll.kernel32.ReadFile(self.handle, buf, max_bytes, ctypes.byref(bytes_read), None)
            raw = buf.raw[:bytes_read.value].decode('latin1', errors='ignore').strip()
            lines = [l.strip() for l in raw.splitlines() if l.strip() and not l.startswith(";")]
            return lines[0] if lines else raw

    def send_cmd(self, cmd: str):
        full_cmd = (cmd + "\r").encode("ascii")
        self.write(full_cmd)

    def query(self, cmd: str):
        full_cmd = (cmd + "\r").encode("ascii")
        with self.lock:
            written = wintypes.DWORD()
            ctypes.windll.kernel32.WriteFile(self.handle, full_cmd, len(full_cmd), ctypes.byref(written), None)
            buf = ctypes.create_string_buffer(512)
            bytes_read = wintypes.DWORD()
            ctypes.windll.kernel32.ReadFile(self.handle, buf, 512, ctypes.byref(bytes_read), None)
            raw = buf.raw[:bytes_read.value].decode('latin1', errors='ignore').strip()
            lines = [l.strip() for l in raw.splitlines() if l.strip() and not l.startswith(";")]
            return lines[0] if lines else raw

ser = None

device_state = {
    "connected": True,
    "device_name": "EV DX38 V3.21",
    "preset_num": "27",
    "preset_name": "User program 27",
    "routing_mode": "TWOWAY",
    "master_mute": False,
    "vu": [0, 0, 0, 0, 0, 0],
    "selected_channel": 1,
    "channels": {
        1: {
            "name": "OUT 1", "color": "#f97316", "level": 0.0, "muted": False, "polarity": "NORMAL", "delay": "3.700",
            "lowcut_freq": 80, "lowcut_slope": "24dB/oct", "highcut_freq": 3200, "highcut_slope": "24dB/oct",
            "comp": {"thresh": -18.0, "ratio": 4.0, "attack": 5.0, "release": 50.0},
            "limiter": {"thresh": -6.0, "release": 100.0},
            "eq": {
                1: {"name": "Low",   "mode": "PEQ", "gain": 4.5,  "freq": 60.0,   "q": 1.7, "color": "#22d3ee"},
                2: {"name": "LoMid", "mode": "PEQ", "gain": -8.0, "freq": 200.0,  "q": 3.0, "color": "#2dd4bf"},
                3: {"name": "HiMid", "mode": "PEQ", "gain": -6.0, "freq": 800.0,  "q": 2.0, "color": "#f43f5e"},
                4: {"name": "High",  "mode": "PEQ", "gain": 3.0,  "freq": 2500.0, "q": 1.5, "color": "#fb923c"}
            }
        },
        2: {
            "name": "OUT 2", "color": "#3b82f6", "level": 0.0, "muted": False, "polarity": "NORMAL", "delay": "0.000",
            "lowcut_freq": 80, "lowcut_slope": "24dB/oct", "highcut_freq": 3200, "highcut_slope": "24dB/oct",
            "comp": {"thresh": -18.0, "ratio": 4.0, "attack": 5.0, "release": 50.0},
            "limiter": {"thresh": -6.0, "release": 100.0},
            "eq": {
                1: {"name": "Low",   "mode": "PEQ", "gain": 0.0,  "freq": 80.0,   "q": 1.5, "color": "#22d3ee"},
                2: {"name": "LoMid", "mode": "PEQ", "gain": -3.0, "freq": 250.0,  "q": 2.0, "color": "#2dd4bf"},
                3: {"name": "HiMid", "mode": "PEQ", "gain": 2.5,  "freq": 2800.0, "q": 1.4, "color": "#f43f5e"},
                4: {"name": "High",  "mode": "PEQ", "gain": 4.0,  "freq": 8000.0, "q": 1.0, "color": "#fb923c"}
            }
        },
        3: {
            "name": "OUT 3", "color": "#a855f7", "level": 0.0, "muted": False, "polarity": "NORMAL", "delay": "5.000",
            "lowcut_freq": 3200, "lowcut_slope": "24dB/oct", "highcut_freq": 20000, "highcut_slope": "24dB/oct",
            "comp": {"thresh": -18.0, "ratio": 4.0, "attack": 5.0, "release": 50.0},
            "limiter": {"thresh": -6.0, "release": 100.0},
            "eq": {
                1: {"name": "Low",   "mode": "PEQ", "gain": -4.0, "freq": 4000.0,  "q": 1.0, "color": "#22d3ee"},
                2: {"name": "LoMid", "mode": "PEQ", "gain": 0.0,  "freq": 6000.0,  "q": 1.0, "color": "#2dd4bf"},
                3: {"name": "HiMid", "mode": "PEQ", "gain": 2.0,  "freq": 10000.0, "q": 1.2, "color": "#f43f5e"},
                4: {"name": "High",  "mode": "PEQ", "gain": 1.5,  "freq": 16000.0, "q": 1.0, "color": "#fb923c"}
            }
        },
        4: {
            "name": "OUT 4", "color": "#10b981", "level": 0.0, "muted": False, "polarity": "NORMAL", "delay": "8.000",
            "lowcut_freq": 3200, "lowcut_slope": "24dB/oct", "highcut_freq": 20000, "highcut_slope": "24dB/oct",
            "comp": {"thresh": -18.0, "ratio": 4.0, "attack": 5.0, "release": 50.0},
            "limiter": {"thresh": -6.0, "release": 100.0},
            "eq": {
                1: {"name": "Low",   "mode": "PEQ", "gain": 2.0,  "freq": 4000.0,  "q": 1.8, "color": "#22d3ee"},
                2: {"name": "LoMid", "mode": "PEQ", "gain": -2.0, "freq": 7000.0,  "q": 2.5, "color": "#2dd4bf"},
                3: {"name": "HiMid", "mode": "PEQ", "gain": 1.0,  "freq": 12000.0, "q": 1.6, "color": "#f43f5e"},
                4: {"name": "High",  "mode": "PEQ", "gain": -1.5, "freq": 16000.0, "q": 1.0, "color": "#fb923c"}
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
        if pname: device_state["preset_name"] = pname.replace(f"/ID{DEVICE_ID}/MISC/PROGNAME", "").strip()
        if pnum:  device_state["preset_num"]  = pnum.replace(f"/ID{DEVICE_ID}/MISC/PROGNUMBER", "").strip()
        if cfg:   device_state["routing_mode"] = cfg.replace(f"/ID{DEVICE_ID}/MISC/CONFIG", "").strip()
        for ch in range(1, 5):
            lvl  = ser.query(f"/ID{DEVICE_ID}/Out{ch}/Level ?")
            mute = ser.query(f"/ID{DEVICE_ID}/Out{ch}/Mute ?")
            pol  = ser.query(f"/ID{DEVICE_ID}/Out{ch}/Polarity ?")
            dly  = ser.query(f"/ID{DEVICE_ID}/Out{ch}/Delay ?")
            try: device_state["channels"][ch]["level"] = float(lvl.split()[-1])
            except: pass
            device_state["channels"][ch]["muted"]    = mute.endswith("1") or "MUTE 1" in mute.upper()
            device_state["channels"][ch]["polarity"] = "INVERTED" if "INVERTED" in pol.upper() else "NORMAL"
            if dly: device_state["channels"][ch]["delay"] = dly.split()[-1]
        print(f"[+] Sync OK — Preset [{device_state['preset_num']}] {device_state['preset_name']}")
    except Exception as e:
        print(f"[-] Sync error: {e}")

def background_loop():
    global ser, device_state
    last_p = 0
    while True:
        if ser:
            try:
                now = time.time()
                if now - last_p > 2.0:
                    last_p = now
                    cur_num = ser.query(f"/ID{DEVICE_ID}/Misc/Prognumber ?")
                    clean   = cur_num.replace(f"/ID{DEVICE_ID}/MISC/PROGNUMBER", "").strip()
                    if clean and clean != device_state["preset_num"]:
                        sync_hardware()
                ser.send_cmd(f"/ID{DEVICE_ID}/VU ?")
                time.sleep(0.04)
                txt = ser.read_clean(128)
                if "VU" in txt:
                    idx = txt.find("VU")
                    vc  = txt[idx+2 : idx+8]
                    if len(vc) == 6:
                        device_state["vu"] = [max(0, min(100, int((ord(c) - 64) * 3.5))) for c in vc]
            except:
                pass
        time.sleep(0.12)

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>EV Dx38 Controller</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root {
  --c-bg:      #030b1a;
  --c-surface: #07142e;
  --c-panel:   #0d2044;
  --c-raised:  #122456;
  --c-border:  #1e3a6e;
  --c-border2: #2a5099;
  --c-cyan:    #00d4ff;
  --c-teal:    #00e5b0;
  --c-amber:   #ffb800;
  --c-red:     #ff3b5c;
  --c-green:   #1aff7a;
  --c-text:    #d6eaff;
  --c-dim:     #5a84c0;
  --c-muted:   #2e5080;
  --font:      'Inter', sans-serif;
  --mono:      'JetBrains Mono', monospace;
  --r:         6px;
  --rs:        3px;
  --tr:        0.15s ease;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
html,body{width:100%;height:100%;overflow:hidden;}
body{font-family:var(--font);background:var(--c-bg);color:var(--c-text);font-size:12px;display:flex;flex-direction:column;}
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-track{background:var(--c-surface);}
::-webkit-scrollbar-thumb{background:var(--c-border2);border-radius:3px;}

/* TOP BAR */
#topbar{height:46px;min-height:46px;background:linear-gradient(180deg,#061227,#040e1e);border-bottom:1px solid var(--c-border);display:flex;align-items:center;padding:0 16px;gap:14px;z-index:100;}
.tb-logo{font-weight:900;font-size:16px;letter-spacing:.06em;color:var(--c-cyan);white-space:nowrap;text-shadow:0 0 18px rgba(0,212,255,.5);}
.tb-logo span{color:var(--c-amber);}
.tb-sep{width:1px;height:22px;background:var(--c-border);flex-shrink:0;}
.tb-info{font-size:11px;color:var(--c-dim);font-family:var(--mono);}
.tb-info b{color:var(--c-text);font-weight:600;}
.tb-status{margin-left:auto;display:flex;align-items:center;gap:16px;}
.status-dot{display:flex;align-items:center;gap:5px;font-size:11px;font-weight:600;color:var(--c-green);}
.status-dot::before{content:'';width:7px;height:7px;border-radius:50%;background:var(--c-green);box-shadow:0 0 8px var(--c-green);animation:pulse 2s infinite;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.preset-badge{background:var(--c-panel);border:1px solid var(--c-border2);border-radius:var(--rs);padding:3px 10px;font-size:11px;font-family:var(--mono);color:var(--c-amber);font-weight:700;}

/* CHANNEL STRIP ROW */
#ch-selector{height:68px;min-height:68px;background:var(--c-surface);border-bottom:2px solid var(--c-border);display:flex;align-items:stretch;padding:0 12px;gap:8px;}
.ch-strip{display:flex;align-items:center;gap:10px;padding:0 14px;border:1px solid var(--c-border);border-radius:var(--rs);background:var(--c-panel);cursor:pointer;margin:8px 0;position:relative;transition:border-color var(--tr),background var(--tr);min-width:0;flex:1;}
.ch-strip:hover{border-color:var(--c-border2);background:var(--c-raised);}
.ch-strip.active{border-color:var(--c-cyan);background:#0e2b5c;box-shadow:0 0 0 1px var(--c-cyan) inset,0 2px 16px rgba(0,212,255,.15);}
.ch-strip.active::after{content:'';position:absolute;bottom:-2px;left:8px;right:8px;height:2px;background:var(--c-cyan);border-radius:2px 2px 0 0;}
.ch-color-swatch{width:4px;height:36px;border-radius:2px;flex-shrink:0;}
.ch-strip-info{flex:1;min-width:0;}
.ch-strip-name{font-weight:800;font-size:13px;color:var(--c-text);}
.ch-strip-sub{font-size:10px;color:var(--c-dim);margin-top:1px;font-family:var(--mono);}
.ch-strip-right{display:flex;flex-direction:column;align-items:flex-end;gap:4px;}
.ch-level-num{font-family:var(--mono);font-size:13px;font-weight:700;color:var(--c-cyan);}
.ch-vu-bar{width:60px;height:6px;background:var(--c-muted);border-radius:3px;overflow:hidden;}
.ch-vu-fill{height:100%;width:0%;background:linear-gradient(to right,var(--c-teal),var(--c-green) 60%,var(--c-amber) 80%,var(--c-red));transition:width .08s;border-radius:3px;}
.mute-pill{background:var(--c-raised);border:1px solid var(--c-border2);color:var(--c-dim);font-weight:700;font-size:10px;padding:2px 8px;border-radius:20px;cursor:pointer;letter-spacing:.06em;transition:all var(--tr);}
.mute-pill:hover{border-color:var(--c-red);color:var(--c-red);}
.mute-pill.muted{background:var(--c-red);border-color:#ff6b88;color:#fff;box-shadow:0 0 10px rgba(255,59,92,.6);}

/* WORKSPACE */
#workspace{flex:1;display:flex;overflow:hidden;}

/* LEFT NAV */
#left-nav{width:54px;background:var(--c-surface);border-right:1px solid var(--c-border);display:flex;flex-direction:column;align-items:center;padding:10px 0;gap:4px;flex-shrink:0;}
.nav-btn{width:40px;height:40px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;border-radius:var(--rs);border:1px solid transparent;cursor:pointer;color:var(--c-dim);font-size:8px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;transition:all var(--tr);}
.nav-btn svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:1.8;}
.nav-btn:hover{background:var(--c-panel);color:var(--c-text);border-color:var(--c-border);}
.nav-btn.active{background:var(--c-panel);color:var(--c-cyan);border-color:var(--c-border2);box-shadow:inset 3px 0 0 var(--c-cyan);}

/* CONTENT */
#content{flex:1;overflow:hidden;position:relative;}
.tab-panel{display:none;height:100%;overflow-y:auto;padding:14px;gap:12px;flex-direction:column;}
.tab-panel.active{display:flex;}

/* PANEL CARD */
.panel{background:var(--c-panel);border:1px solid var(--c-border);border-radius:var(--r);overflow:hidden;}
.panel-hdr{padding:8px 14px;background:var(--c-raised);border-bottom:1px solid var(--c-border);display:flex;align-items:center;gap:8px;font-weight:700;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--c-dim);}
.panel-hdr .accent{color:var(--c-cyan);}
.panel-hdr .dot{width:6px;height:6px;border-radius:50%;background:var(--c-cyan);box-shadow:0 0 6px var(--c-cyan);}
.panel-body{padding:12px 14px;}

/* KV */
.kv-row{display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid rgba(30,58,110,.5);}
.kv-row:last-child{border-bottom:none;}
.kv-key{color:var(--c-dim);font-size:11px;}
.kv-val{font-family:var(--mono);font-size:12px;font-weight:700;color:var(--c-text);}
.kv-val.cyan{color:var(--c-cyan);}
.kv-val.amber{color:var(--c-amber);}

/* SLIDER */
.slider-row{display:flex;align-items:center;gap:10px;padding:5px 0;}
.slider-label{color:var(--c-dim);font-size:11px;width:70px;flex-shrink:0;}
input[type=range].dx-slider{-webkit-appearance:none;flex:1;height:4px;background:var(--c-muted);border-radius:2px;outline:none;cursor:pointer;}
input[type=range].dx-slider::-webkit-slider-thumb{-webkit-appearance:none;width:14px;height:14px;border-radius:50%;background:var(--c-cyan);border:2px solid var(--c-bg);box-shadow:0 0 6px var(--c-cyan);cursor:pointer;}
.slider-val{font-family:var(--mono);font-size:11px;color:var(--c-cyan);width:60px;text-align:right;flex-shrink:0;}

/* BUTTON */
.dx-btn{background:var(--c-raised);border:1px solid var(--c-border2);color:var(--c-text);font-family:var(--font);font-weight:700;font-size:11px;padding:6px 14px;border-radius:var(--rs);cursor:pointer;letter-spacing:.05em;transition:all var(--tr);}
.dx-btn:hover{background:var(--c-border);border-color:var(--c-cyan);color:var(--c-cyan);}
.dx-btn.active{background:rgba(0,212,255,.15);border-color:var(--c-cyan);color:var(--c-cyan);}
.dx-btn.danger{border-color:var(--c-red);color:var(--c-red);}
.dx-btn.danger:hover{background:rgba(255,59,92,.15);}

/* GRID */
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:10px;}

/* OVERVIEW TABLE */
.overview-table{width:100%;border-collapse:collapse;font-size:12px;}
.overview-table th{text-align:left;padding:7px 12px;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--c-dim);background:var(--c-raised);border-bottom:1px solid var(--c-border);}
.overview-table td{padding:9px 12px;border-bottom:1px solid rgba(30,58,110,.4);vertical-align:middle;}
.overview-table tr:last-child td{border-bottom:none;}
.overview-table tr:hover td{background:rgba(0,212,255,.03);}
.ov-color-dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:6px;vertical-align:middle;}
.ov-name{font-weight:700;}
.level-fader{-webkit-appearance:none;width:120px;height:4px;background:var(--c-muted);border-radius:2px;outline:none;cursor:pointer;}
.level-fader::-webkit-slider-thumb{-webkit-appearance:none;width:14px;height:14px;border-radius:50%;background:var(--c-amber);border:2px solid var(--c-bg);box-shadow:0 0 6px var(--c-amber);cursor:pointer;}
.pol-btn{font-size:10px;font-weight:700;border:1px solid var(--c-border2);background:var(--c-raised);color:var(--c-dim);border-radius:var(--rs);padding:3px 7px;cursor:pointer;transition:all var(--tr);}
.pol-btn.inv{color:var(--c-amber);border-color:var(--c-amber);background:rgba(255,184,0,.1);}

/* EQ */
#eq-canvas-wrap{position:relative;border-radius:var(--rs);overflow:hidden;background:#030b17;border:1px solid var(--c-border);}
#eqCanvas{display:block;width:100%;}
.eq-labels{position:absolute;bottom:0;left:0;right:0;display:flex;justify-content:space-between;padding:2px 6px;pointer-events:none;}
.eq-labels span{font-size:9px;color:var(--c-muted);font-family:var(--mono);}
.eq-db-labels{position:absolute;top:0;bottom:0;right:4px;display:flex;flex-direction:column;justify-content:space-between;padding:4px 0;pointer-events:none;}
.eq-db-labels span{font-size:9px;color:var(--c-muted);font-family:var(--mono);text-align:right;}
.eq-band-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;}
.eq-band-card{background:var(--c-raised);border:1px solid var(--c-border);border-radius:var(--rs);padding:10px;display:flex;flex-direction:column;gap:6px;}
.eq-band-card.selected{border-color:var(--c-cyan);box-shadow:0 0 0 1px var(--c-cyan) inset;}
.eq-band-hdr{display:flex;justify-content:space-between;align-items:center;}
.eq-band-name{font-weight:800;font-size:11px;}
.eq-band-gain{font-family:var(--mono);font-size:18px;font-weight:900;text-align:center;padding:4px 0;}
.eq-band-row{display:flex;justify-content:space-between;font-size:10px;}
.eq-band-row .k{color:var(--c-dim);}
.eq-band-row .v{font-family:var(--mono);font-weight:600;}

/* CROSSOVER */
.xo-diagram{display:flex;align-items:stretch;border:1px solid var(--c-border);border-radius:var(--r);overflow:hidden;height:52px;}
.xo-seg{flex:1;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;letter-spacing:.06em;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,.5);border-right:1px solid rgba(0,0,0,.3);}
.xo-seg:last-child{border-right:none;}
.xo-seg.lf{background:linear-gradient(135deg,#1e40af,#1d4ed8);}
.xo-seg.hf{background:linear-gradient(135deg,#7c3aed,#a855f7);}
.xo-field{display:flex;flex-direction:column;gap:4px;}
.xo-field label{font-size:10px;color:var(--c-dim);letter-spacing:.04em;}
.xo-field select,.xo-field input[type=number]{background:var(--c-raised);border:1px solid var(--c-border2);color:var(--c-text);font-family:var(--mono);font-size:12px;padding:5px 8px;border-radius:var(--rs);outline:none;width:100%;}
.xo-field select:focus,.xo-field input[type=number]:focus{border-color:var(--c-cyan);}

/* DYNAMICS */
.dyn-graph{height:80px;background:#030b17;border:1px solid var(--c-border);border-radius:var(--rs);overflow:hidden;}
.dyn-graph canvas{display:block;width:100%;height:100%;}
.toggle{width:32px;height:17px;background:var(--c-muted);border-radius:99px;cursor:pointer;position:relative;transition:background var(--tr);border:none;}
.toggle::after{content:'';position:absolute;width:13px;height:13px;background:#fff;border-radius:50%;top:2px;left:2px;transition:left var(--tr);}
.toggle.on{background:var(--c-cyan);}
.toggle.on::after{left:17px;}

/* DELAY */
.delay-visual{height:44px;background:#030b17;border:1px solid var(--c-border);border-radius:var(--rs);overflow:hidden;}
.delay-bar{height:100%;background:linear-gradient(to right,rgba(0,212,255,.2),rgba(0,212,255,.05));border-right:2px solid var(--c-cyan);transition:width .3s ease;}

/* PRESETS */
.preset-list{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;}
.preset-item{background:var(--c-raised);border:1px solid var(--c-border);border-radius:var(--rs);padding:8px 10px;cursor:pointer;transition:all var(--tr);display:flex;flex-direction:column;gap:2px;}
.preset-item:hover{border-color:var(--c-border2);background:#163060;}
.preset-item.current{border-color:var(--c-amber);box-shadow:0 0 0 1px var(--c-amber) inset;}
.preset-num{font-size:10px;color:var(--c-dim);font-family:var(--mono);}
.preset-name{font-size:11px;font-weight:700;color:var(--c-text);}

/* BIG VU */
.big-vu-wrap{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;height:200px;}
.big-vu-ch{display:flex;flex-direction:column;gap:6px;align-items:center;}
.big-vu-bar{flex:1;width:100%;background:var(--c-muted);border-radius:var(--rs);overflow:hidden;display:flex;flex-direction:column-reverse;}
.big-vu-fill{width:100%;height:0%;background:linear-gradient(to top,var(--c-teal),var(--c-green) 55%,var(--c-amber) 80%,var(--c-red));transition:height .08s;}
.big-vu-label{font-size:10px;color:var(--c-dim);font-weight:700;}
.big-vu-val{font-family:var(--mono);font-size:12px;color:var(--c-cyan);font-weight:700;}

/* ROUTING */
.routing-diagram{display:flex;align-items:center;justify-content:center;gap:0;padding:16px 0;}
.rd-block{background:var(--c-raised);border:1px solid var(--c-border2);border-radius:var(--rs);padding:12px 18px;text-align:center;min-width:80px;}
.rd-title{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--c-dim);margin-bottom:4px;}
.rd-name{font-size:12px;font-weight:800;color:var(--c-text);}
.rd-arrow{padding:0 12px;color:var(--c-border2);font-size:18px;}
.mode-badge{display:inline-block;background:rgba(0,212,255,.1);border:1px solid var(--c-cyan);color:var(--c-cyan);font-size:11px;font-weight:800;padding:3px 12px;border-radius:var(--rs);letter-spacing:.06em;}
</style>
</head>
<body>

<div id="topbar">
  <div class="tb-logo">EV&nbsp;<span>Dx38</span></div>
  <div class="tb-sep"></div>
  <div class="tb-info"><b id="tbDevice">EV DX38 V3.21</b> &nbsp;·&nbsp; COM2 19200</div>
  <div class="tb-sep"></div>
  <div class="tb-info">Mode: <b id="tbMode">TWOWAY</b></div>
  <div class="tb-status">
    <div class="preset-badge">PRESET <span id="tbPresetNum">27</span> — <span id="tbPresetName">User program 27</span></div>
    <div class="status-dot" id="statusDot">RS-232 ONLINE</div>
  </div>
</div>

<div id="ch-selector">
  {% for ch in [1,2,3,4] %}
  {% set colors = ['#f97316','#3b82f6','#a855f7','#10b981'] %}
  <div class="ch-strip {{ 'active' if ch==1 else '' }}" id="strip{{ch}}" onclick="selectCh({{ch}})">
    <div class="ch-color-swatch" id="swatch{{ch}}" style="background:{{colors[ch-1]}};"></div>
    <div class="ch-strip-info">
      <div class="ch-strip-name" id="stripName{{ch}}">OUT {{ch}}</div>
      <div class="ch-strip-sub" id="stripSub{{ch}}">0.0 dB &nbsp;·&nbsp; NORMAL</div>
    </div>
    <div class="ch-strip-right">
      <div class="ch-level-num" id="stripLevel{{ch}}">0.0 dB</div>
      <div class="ch-vu-bar"><div class="ch-vu-fill" id="stripVu{{ch}}"></div></div>
      <button class="mute-pill" id="stripMute{{ch}}" onclick="toggleMute({{ch}},event)">MUTE</button>
    </div>
  </div>
  {% endfor %}
</div>

<div id="workspace">
  <div id="left-nav">
    <div class="nav-btn active" id="nav-overview" onclick="switchTab('overview')" title="Overview">
      <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>OVW
    </div>
    <div class="nav-btn" id="nav-eq" onclick="switchTab('eq')" title="EQ">
      <svg viewBox="0 0 24 24"><path d="M3 17c3-8 6-8 9 0s6 8 9 0"/></svg>EQ
    </div>
    <div class="nav-btn" id="nav-xover" onclick="switchTab('xover')" title="Crossover">
      <svg viewBox="0 0 24 24"><path d="M4 20L12 4L20 20"/><line x1="6" y1="15" x2="18" y2="15"/></svg>XOV
    </div>
    <div class="nav-btn" id="nav-dyn" onclick="switchTab('dyn')" title="Dynamics">
      <svg viewBox="0 0 24 24"><polyline points="2 12 6 4 10 16 14 8 18 14 22 12"/></svg>DYN
    </div>
    <div class="nav-btn" id="nav-delay" onclick="switchTab('delay')" title="Delay">
      <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>DLY
    </div>
    <div class="nav-btn" id="nav-preset" onclick="switchTab('preset')" title="Presets">
      <svg viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/></svg>PRE
    </div>
    <div class="nav-btn" id="nav-meter" onclick="switchTab('meter')" title="Meters">
      <svg viewBox="0 0 24 24"><rect x="4" y="6" width="4" height="12" rx="1"/><rect x="10" y="3" width="4" height="15" rx="1"/><rect x="16" y="9" width="4" height="9" rx="1"/></svg>MTR
    </div>
    <div class="nav-btn" id="nav-routing" onclick="switchTab('routing')" title="Routing">
      <svg viewBox="0 0 24 24"><path d="M5 9V5h4"/><path d="M9 5L4 10"/><path d="M19 15v4h-4"/><path d="M15 19l5-5"/><line x1="9" y1="15" x2="15" y2="9"/></svg>RTG
    </div>
  </div>

  <div id="content">

    <!-- OVERVIEW -->
    <div class="tab-panel active" id="tab-overview">
      <div class="panel">
        <div class="panel-hdr"><div class="dot"></div><span class="accent">OUTPUT</span>&nbsp;CHANNELS</div>
        <div class="panel-body" style="padding:0;">
          <table class="overview-table">
            <thead><tr><th>CH</th><th>NAME</th><th>LEVEL</th><th>FADER</th><th>MUTE</th><th>POLARITY</th><th>DELAY</th></tr></thead>
            <tbody>
            {% for ch in [1,2,3,4] %}
            {% set colors = ['#f97316','#3b82f6','#a855f7','#10b981'] %}
            <tr>
              <td><span class="ov-color-dot" style="background:{{colors[ch-1]}}"></span>OUT {{ch}}</td>
              <td class="ov-name" id="ovName{{ch}}">OUT {{ch}}</td>
              <td><span class="kv-val cyan" id="ovLevel{{ch}}">0.0 dB</span></td>
              <td><input type="range" class="level-fader" id="ovFader{{ch}}" min="-40" max="6" step="0.5" value="0" oninput="onFader({{ch}},this.value)"></td>
              <td><button class="mute-pill" id="ovMute{{ch}}" onclick="toggleMute({{ch}},event)">MUTE</button></td>
              <td><button class="pol-btn" id="ovPol{{ch}}" onclick="togglePol({{ch}})">NORMAL</button></td>
              <td><span class="kv-val amber" id="ovDelay{{ch}}">0.000 ms</span></td>
            </tr>
            {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
      <div class="grid-2">
        <div class="panel">
          <div class="panel-hdr"><div class="dot"></div><span class="accent">DEVICE</span>&nbsp;INFO</div>
          <div class="panel-body">
            <div class="kv-row"><span class="kv-key">Hardware</span><span class="kv-val" id="infoHw">EV DX38 V3.21</span></div>
            <div class="kv-row"><span class="kv-key">Active Preset</span><span class="kv-val amber" id="infoPreset">27 — User program 27</span></div>
            <div class="kv-row"><span class="kv-key">Routing Mode</span><span class="kv-val cyan" id="infoMode">TWOWAY</span></div>
            <div class="kv-row"><span class="kv-key">Port</span><span class="kv-val">COM2 @ 19200 baud</span></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-hdr"><div class="dot"></div><span class="accent">QUICK</span>&nbsp;ACTIONS</div>
          <div class="panel-body" style="display:flex;flex-wrap:wrap;gap:8px;">
            <button class="dx-btn" onclick="recallPreset(prompt('Preset (1-30):'))">Recall Preset</button>
            <button class="dx-btn danger" onclick="muteAll()">Mute All</button>
            <button class="dx-btn" onclick="unmuteAll()">Unmute All</button>
            <button class="dx-btn" onclick="syncNow()">Force Sync</button>
          </div>
        </div>
      </div>
    </div>

    <!-- EQ -->
    <div class="tab-panel" id="tab-eq">
      <div class="panel">
        <div class="panel-hdr">
          <div class="dot"></div><span class="accent">4-BAND PEQ</span>&nbsp;— <span id="eqChLabel" style="color:var(--c-amber)">OUT 1</span>
          <div style="margin-left:auto;"><button class="dx-btn" onclick="eqFlat()">FLAT</button></div>
        </div>
        <div class="panel-body" style="padding:10px;">
          <div id="eq-canvas-wrap" style="height:180px;">
            <canvas id="eqCanvas" height="180"></canvas>
            <div class="eq-db-labels"><span>+15</span><span>+9</span><span>+3</span><span>0</span><span>-3</span><span>-9</span><span>-15</span></div>
            <div class="eq-labels"><span>20</span><span>50</span><span>100</span><span>200</span><span>500</span><span>1k</span><span>2k</span><span>5k</span><span>10k</span><span>20k</span></div>
          </div>
        </div>
      </div>
      <div class="eq-band-grid">
        {% for b,color,name in [(1,'#22d3ee','Low'),(2,'#2dd4bf','LoMid'),(3,'#f43f5e','HiMid'),(4,'#fb923c','High')] %}
        <div class="eq-band-card" id="eqCard{{b}}" onclick="selectBand({{b}})">
          <div class="eq-band-hdr">
            <span class="eq-band-name" style="color:{{color}}">{{name}}</span>
            <span style="font-size:10px;color:var(--c-dim)" id="eqMode{{b}}">PEQ</span>
          </div>
          <div class="eq-band-gain" style="color:{{color}}" id="eqGain{{b}}">0.00 dB</div>
          <div class="eq-band-row"><span class="k">Freq</span><span class="v" id="eqFreq{{b}}">—</span></div>
          <div class="eq-band-row"><span class="k">Q</span><span class="v" id="eqQ{{b}}">—</span></div>
          <input type="range" class="dx-slider" style="width:100%;margin-top:4px" min="-15" max="15" step="0.25" value="0" id="eqSlider{{b}}" oninput="onEqGain({{b}},this.value)">
        </div>
        {% endfor %}
      </div>
    </div>

    <!-- CROSSOVER -->
    <div class="tab-panel" id="tab-xover">
      <div class="panel">
        <div class="panel-hdr"><div class="dot"></div><span class="accent">CROSSOVER</span>&nbsp;— <span id="xoChLabel" style="color:var(--c-amber)">OUT 1</span></div>
        <div class="panel-body">
          <div class="xo-diagram" style="margin-bottom:14px;">
            <div class="xo-seg lf" style="flex:2">LOW PASS</div>
            <div class="xo-seg hf" style="flex:2">HIGH PASS</div>
          </div>
          <div class="grid-2" style="margin-bottom:12px;">
            <div class="panel" style="border-color:var(--c-border);">
              <div class="panel-hdr" style="font-size:10px;">HIGH-PASS FILTER (Low Cut)</div>
              <div class="panel-body" style="display:flex;gap:10px;">
                <div class="xo-field" style="flex:1"><label>FREQUENCY Hz</label><input type="number" id="xoHpFreq" value="80" min="20" max="20000" oninput="renderXO()"></div>
                <div class="xo-field" style="flex:1"><label>SLOPE</label><select id="xoHpSlope" onchange="renderXO()"><option>6dB/oct</option><option>12dB/oct</option><option selected>24dB/oct</option><option>48dB/oct</option></select></div>
              </div>
            </div>
            <div class="panel" style="border-color:var(--c-border);">
              <div class="panel-hdr" style="font-size:10px;">LOW-PASS FILTER (High Cut)</div>
              <div class="panel-body" style="display:flex;gap:10px;">
                <div class="xo-field" style="flex:1"><label>FREQUENCY Hz</label><input type="number" id="xoLpFreq" value="3200" min="20" max="20000" oninput="renderXO()"></div>
                <div class="xo-field" style="flex:1"><label>SLOPE</label><select id="xoLpSlope" onchange="renderXO()"><option>6dB/oct</option><option>12dB/oct</option><option selected>24dB/oct</option><option>48dB/oct</option></select></div>
              </div>
            </div>
          </div>
          <canvas id="xoCanvas" height="100" style="width:100%;display:block;border-radius:var(--rs);border:1px solid var(--c-border);background:#030b17;"></canvas>
          <div style="margin-top:10px;"><button class="dx-btn active" onclick="sendXo()">Apply to Hardware</button></div>
        </div>
      </div>
    </div>

    <!-- DYNAMICS -->
    <div class="tab-panel" id="tab-dyn">
      <div class="grid-2">
        <div class="panel">
          <div class="panel-hdr">
            <div class="dot" style="background:var(--c-teal);box-shadow:0 0 6px var(--c-teal)"></div>
            <span class="accent">COMPRESSOR</span>&nbsp;— <span id="compChLabel" style="color:var(--c-amber)">OUT 1</span>
            <div style="margin-left:auto;"><button class="toggle" id="compToggle" onclick="this.classList.toggle('on')"></button></div>
          </div>
          <div class="panel-body">
            <div class="dyn-graph" style="margin-bottom:12px;"><canvas id="compCanvas"></canvas></div>
            <div class="slider-row"><span class="slider-label">Threshold</span><input type="range" class="dx-slider" id="compThresh" min="-40" max="0" step="0.5" value="-18" oninput="onDyn()"><span class="slider-val" id="compThreshVal">-18.0 dB</span></div>
            <div class="slider-row"><span class="slider-label">Ratio</span><input type="range" class="dx-slider" id="compRatio" min="1" max="20" step="0.5" value="4" oninput="onDyn()"><span class="slider-val" id="compRatioVal">4.0 : 1</span></div>
            <div class="slider-row"><span class="slider-label">Attack</span><input type="range" class="dx-slider" id="compAttack" min="0.1" max="200" step="0.1" value="5" oninput="onDyn()"><span class="slider-val" id="compAttackVal">5.0 ms</span></div>
            <div class="slider-row"><span class="slider-label">Release</span><input type="range" class="dx-slider" id="compRelease" min="10" max="2000" step="10" value="50" oninput="onDyn()"><span class="slider-val" id="compReleaseVal">50 ms</span></div>
            <div style="margin-top:10px;"><button class="dx-btn active" onclick="sendComp()">Apply</button></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-hdr">
            <div class="dot" style="background:var(--c-red);box-shadow:0 0 6px var(--c-red)"></div>
            <span class="accent">LIMITER</span>&nbsp;— <span id="limChLabel" style="color:var(--c-amber)">OUT 1</span>
            <div style="margin-left:auto;"><button class="toggle on" id="limToggle" onclick="this.classList.toggle('on')"></button></div>
          </div>
          <div class="panel-body">
            <div class="dyn-graph" style="margin-bottom:12px;"><canvas id="limCanvas"></canvas></div>
            <div class="slider-row"><span class="slider-label">Threshold</span><input type="range" class="dx-slider" id="limThresh" min="-20" max="0" step="0.5" value="-6" oninput="onDyn()"><span class="slider-val" id="limThreshVal">-6.0 dB</span></div>
            <div class="slider-row"><span class="slider-label">Release</span><input type="range" class="dx-slider" id="limRelease" min="10" max="2000" step="10" value="100" oninput="onDyn()"><span class="slider-val" id="limReleaseVal">100 ms</span></div>
            <div style="margin-top:10px;"><button class="dx-btn active" onclick="sendLim()">Apply</button></div>
          </div>
        </div>
      </div>
    </div>

    <!-- DELAY -->
    <div class="tab-panel" id="tab-delay">
      <div class="panel">
        <div class="panel-hdr"><div class="dot"></div><span class="accent">OUTPUT DELAY</span></div>
        <div class="panel-body">
          {% for ch in [1,2,3,4] %}
          {% set colors = ['#f97316','#3b82f6','#a855f7','#10b981'] %}
          <div style="margin-bottom:14px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
              <div style="width:8px;height:8px;border-radius:50%;background:{{colors[ch-1]}}"></div>
              <span style="font-weight:700;font-size:12px;">OUT {{ch}}</span>
              <span class="kv-val amber" id="dlyVal{{ch}}" style="margin-left:auto;">0.000 ms</span>
              <span style="font-size:10px;color:var(--c-dim)" id="dlyCm{{ch}}">(0.0 cm)</span>
            </div>
            <div class="delay-visual"><div class="delay-bar" id="dlyBar{{ch}}" style="width:0%"></div></div>
            <div class="slider-row" style="margin-top:6px;">
              <input type="range" class="dx-slider" style="flex:1" id="dlySlider{{ch}}" min="0" max="500" step="0.1" value="0" oninput="onDelay({{ch}},this.value)">
              <button class="dx-btn" onclick="sendDelay({{ch}})">Set</button>
            </div>
          </div>
          {% endfor %}
        </div>
      </div>
    </div>

    <!-- PRESETS -->
    <div class="tab-panel" id="tab-preset">
      <div class="panel">
        <div class="panel-hdr"><div class="dot"></div><span class="accent">PRESET LIBRARY</span>
          <span style="margin-left:auto;font-size:10px;color:var(--c-dim);">Active: <span id="presetActive" style="color:var(--c-amber)">27</span></span>
        </div>
        <div class="panel-body">
          <div class="preset-list">
            {% for i in range(1,31) %}
            <div class="preset-item {{ 'current' if i==27 else '' }}" id="preItem{{i}}" onclick="recallPreset({{i}})">
              <div class="preset-num">#{{i}}</div>
              <div class="preset-name">Program {{i}}</div>
            </div>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>

    <!-- METER -->
    <div class="tab-panel" id="tab-meter">
      <div class="panel">
        <div class="panel-hdr"><div class="dot"></div><span class="accent">OUTPUT VU METERS</span></div>
        <div class="panel-body">
          <div class="big-vu-wrap">
            {% for ch in [1,2,3,4] %}
            {% set colors = ['#f97316','#3b82f6','#a855f7','#10b981'] %}
            <div class="big-vu-ch">
              <div class="big-vu-bar"><div class="big-vu-fill" id="bigVu{{ch}}"></div></div>
              <div class="big-vu-label" style="color:{{colors[ch-1]}}">OUT {{ch}}</div>
              <div class="big-vu-val" id="bigVuVal{{ch}}">—</div>
            </div>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>

    <!-- ROUTING -->
    <div class="tab-panel" id="tab-routing">
      <div class="panel">
        <div class="panel-hdr"><div class="dot"></div><span class="accent">SIGNAL ROUTING</span></div>
        <div class="panel-body">
          <div style="text-align:center;margin-bottom:14px;">
            <span style="font-size:11px;color:var(--c-dim)">Current Mode:</span>&nbsp;
            <span class="mode-badge" id="routingMode">TWOWAY</span>
          </div>
          <div class="routing-diagram">
            <div class="rd-block"><div class="rd-title">INPUT</div><div class="rd-name">IN 1 + IN 2</div></div>
            <div class="rd-arrow">&#8594;</div>
            <div class="rd-block" style="border-color:var(--c-cyan);min-width:120px;"><div class="rd-title">DSP</div><div class="rd-name" style="color:var(--c-cyan)">EV Dx38</div></div>
            <div class="rd-arrow">&#8594;</div>
            <div>
              <div class="rd-block" style="margin-bottom:6px;"><div class="rd-title">OUT 1 (LF)</div><div class="rd-name" style="color:#f97316">Low Freq</div></div>
              <div class="rd-block" style="margin-bottom:6px;"><div class="rd-title">OUT 2 (LF)</div><div class="rd-name" style="color:#3b82f6">Low Freq</div></div>
              <div class="rd-block" style="margin-bottom:6px;"><div class="rd-title">OUT 3 (HF)</div><div class="rd-name" style="color:#a855f7">High Freq</div></div>
              <div class="rd-block"><div class="rd-title">OUT 4 (HF)</div><div class="rd-name" style="color:#10b981">High Freq</div></div>
            </div>
          </div>
          <div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap;">
            <button class="dx-btn active" onclick="setRouting('TWOWAY')">TWOWAY</button>
            <button class="dx-btn" onclick="setRouting('THREEWAY')">THREEWAY</button>
            <button class="dx-btn" onclick="setRouting('DUALMO')">DUAL MONO</button>
          </div>
        </div>
      </div>
    </div>

  </div>
</div>

<script>
'use strict';
let G={};let selCh=1;let selBand=1;

function switchTab(name){
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  document.getElementById('nav-'+name).classList.add('active');
  if(name==='eq')renderEQ();
  if(name==='xover')renderXO();
  if(name==='dyn'){renderComp();renderLim();}
}

function selectCh(ch){
  selCh=ch;
  document.querySelectorAll('.ch-strip').forEach(s=>s.classList.remove('active'));
  document.getElementById('strip'+ch).classList.add('active');
  refreshChPanels();
}

function refreshChPanels(){
  const c=G.channels?G.channels[selCh]:null;
  if(!c)return;
  const lbl=c.name||('OUT '+selCh);
  ['eqChLabel','xoChLabel','compChLabel','limChLabel'].forEach(id=>{
    const el=document.getElementById(id);if(el)el.textContent=lbl;
  });
  for(let b=1;b<=4;b++){
    const eq=c.eq[b];
    document.getElementById('eqGain'+b).textContent=fmtGain(eq.gain);
    document.getElementById('eqFreq'+b).textContent=fmtFreq(eq.freq);
    document.getElementById('eqQ'+b).textContent=eq.q.toFixed(1);
    document.getElementById('eqMode'+b).textContent=eq.mode;
    document.getElementById('eqSlider'+b).value=eq.gain;
  }
  document.getElementById('xoHpFreq').value=c.lowcut_freq||80;
  document.getElementById('xoLpFreq').value=c.highcut_freq||20000;
  document.getElementById('compThresh').value=c.comp.thresh;
  document.getElementById('compRatio').value=c.comp.ratio;
  document.getElementById('compAttack').value=c.comp.attack;
  document.getElementById('compRelease').value=c.comp.release;
  document.getElementById('limThresh').value=c.limiter.thresh;
  document.getElementById('limRelease').value=c.limiter.release;
  onDyn();renderEQ();renderXO();
}

function fmtGain(g){return(g>0?'+':'')+g.toFixed(2)+' dB';}
function fmtFreq(f){return f>=1000?(f/1000).toFixed(1)+' kHz':f.toFixed(0)+' Hz';}

function applyState(d){
  G=d;
  document.getElementById('tbDevice').textContent=d.device_name||'EV DX38';
  document.getElementById('tbPresetNum').textContent=d.preset_num||'—';
  document.getElementById('tbPresetName').textContent=d.preset_name||'—';
  document.getElementById('tbMode').textContent=d.routing_mode||'—';
  document.getElementById('infoHw').textContent=d.device_name;
  document.getElementById('infoPreset').textContent=d.preset_num+' — '+d.preset_name;
  document.getElementById('infoMode').textContent=d.routing_mode;
  document.getElementById('routingMode').textContent=d.routing_mode;
  document.getElementById('presetActive').textContent=d.preset_num;
  document.querySelectorAll('.preset-item').forEach(el=>el.classList.remove('current'));
  const pa=document.getElementById('preItem'+d.preset_num);if(pa)pa.classList.add('current');
  for(let ch=1;ch<=4;ch++){
    const c=d.channels[ch];
    const lv=c.level.toFixed(1)+' dB';
    document.getElementById('stripLevel'+ch).textContent=lv;
    document.getElementById('stripSub'+ch).textContent=lv+'  ·  '+c.polarity;
    document.getElementById('ovLevel'+ch).textContent=lv;
    document.getElementById('ovFader'+ch).value=c.level;
    document.getElementById('ovDelay'+ch).textContent=c.delay+' ms';
    document.getElementById('ovName'+ch).textContent=c.name;
    document.getElementById('ovPol'+ch).textContent=c.polarity;
    document.getElementById('ovPol'+ch).classList.toggle('inv',c.polarity==='INVERTED');
    ['stripMute','ovMute'].forEach(pfx=>{
      const el=document.getElementById(pfx+ch);
      if(el)el.classList.toggle('muted',c.muted);
    });
    const dv=parseFloat(c.delay)||0;
    const ds=document.getElementById('dlySlider'+ch);if(ds)ds.value=dv;
    const dv2=document.getElementById('dlyVal'+ch);if(dv2)dv2.textContent=dv.toFixed(3)+' ms';
    const dc=document.getElementById('dlyCm'+ch);if(dc)dc.textContent='('+(dv*34.3).toFixed(1)+' cm)';
    const db2=document.getElementById('dlyBar'+ch);if(db2)db2.style.width=Math.min(100,(dv/500)*100)+'%';
  }
  refreshChPanels();
}

function applyVu(vu){
  for(let ch=1;ch<=4;ch++){
    const v=vu[ch+1]||0;
    const svf=document.getElementById('stripVu'+ch);if(svf)svf.style.width=v+'%';
    const bvf=document.getElementById('bigVu'+ch);if(bvf)bvf.style.height=v+'%';
    const bvv=document.getElementById('bigVuVal'+ch);if(bvv)bvv.textContent=v>0?'-'+(100-v|0)+' dBFS':'−∞';
  }
}

function onFader(ch,val){
  document.getElementById('ovLevel'+ch).textContent=parseFloat(val).toFixed(1)+' dB';
  document.getElementById('stripLevel'+ch).textContent=parseFloat(val).toFixed(1)+' dB';
  fetch('/api/level',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel:ch,level:parseFloat(val)})});
}

function toggleMute(ch,e){
  if(e)e.stopPropagation();
  if(!G.channels)return;
  const c=G.channels[ch];c.muted=!c.muted;
  ['stripMute','ovMute'].forEach(pfx=>{const el=document.getElementById(pfx+ch);if(el)el.classList.toggle('muted',c.muted);});
  fetch('/api/mute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel:ch,muted:c.muted?1:0})});
}

function togglePol(ch){
  if(!G.channels)return;
  const c=G.channels[ch];
  c.polarity=c.polarity==='NORMAL'?'INVERTED':'NORMAL';
  document.getElementById('ovPol'+ch).textContent=c.polarity;
  document.getElementById('ovPol'+ch).classList.toggle('inv',c.polarity==='INVERTED');
  fetch('/api/polarity',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel:ch,polarity:c.polarity})});
}

function muteAll(){for(let ch=1;ch<=4;ch++){if(G.channels)G.channels[ch].muted=true;['stripMute','ovMute'].forEach(pfx=>{const el=document.getElementById(pfx+ch);if(el)el.classList.add('muted');});fetch('/api/mute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel:ch,muted:1})});}}
function unmuteAll(){for(let ch=1;ch<=4;ch++){if(G.channels)G.channels[ch].muted=false;['stripMute','ovMute'].forEach(pfx=>{const el=document.getElementById(pfx+ch);if(el)el.classList.remove('muted');});fetch('/api/mute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel:ch,muted:0})});}}
function syncNow(){fetch('/api/sync',{method:'POST'});}
function recallPreset(num){num=parseInt(num);if(!num||num<1||num>30)return;fetch('/api/preset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preset:num})});}
function setRouting(mode){fetch('/api/routing',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});}

function selectBand(b){
  selBand=b;
  document.querySelectorAll('.eq-band-card').forEach(c=>c.classList.remove('selected'));
  document.getElementById('eqCard'+b).classList.add('selected');
}

function onEqGain(b,val){
  val=parseFloat(val);
  if(!G.channels)return;
  G.channels[selCh].eq[b].gain=val;
  document.getElementById('eqGain'+b).textContent=fmtGain(val);
  renderEQ();
}

function eqFlat(){
  if(!G.channels)return;
  for(let b=1;b<=4;b++){G.channels[selCh].eq[b].gain=0;document.getElementById('eqSlider'+b).value=0;document.getElementById('eqGain'+b).textContent='0.00 dB';}
  renderEQ();
}

function freqToX(f,W){const a=Math.log10(20),b=Math.log10(20000);return((Math.log10(f)-a)/(b-a))*W;}
function xToFreq(x,W){const a=Math.log10(20),b=Math.log10(20000);return Math.pow(10,a+(x/W)*(b-a));}

function renderEQ(){
  const cvs=document.getElementById('eqCanvas');if(!cvs)return;
  const wrap=document.getElementById('eq-canvas-wrap');
  cvs.width=wrap.clientWidth;cvs.height=wrap.clientHeight;
  const ctx=cvs.getContext('2d');const W=cvs.width,H=cvs.height;
  ctx.clearRect(0,0,W,H);
  const zeroY=H*0.5;const scale=H/32;
  [-15,-12,-9,-6,-3,0,3,6,9,12,15].forEach(db=>{
    const y=zeroY-db*scale;ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);
    ctx.strokeStyle=db===0?'#1e4080':'#0a1e40';ctx.lineWidth=db===0?1.5:1;ctx.stroke();
  });
  [20,50,100,200,500,1000,2000,5000,10000,20000].forEach(f=>{
    const x=freqToX(f,W);ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.strokeStyle='#0a1e40';ctx.lineWidth=1;ctx.stroke();
  });
  const ch=G.channels?G.channels[selCh]:null;if(!ch)return;
  function totalDb(f){
    let g=0;
    for(let b=1;b<=4;b++){
      const eq=ch.eq[b];
      const d=(Math.log10(f)-Math.log10(eq.freq||1))/(1.4/(eq.q||1)/2);
      g+=eq.gain*Math.exp(-0.5*d*d);
    }
    return g;
  }
  ctx.beginPath();ctx.strokeStyle='#00d4ff';ctx.lineWidth=2.5;
  for(let x=0;x<=W;x+=2){const y=zeroY-totalDb(xToFreq(x,W))*scale;x===0?ctx.moveTo(x,y):ctx.lineTo(x,y);}
  ctx.stroke();
  ctx.beginPath();
  for(let x=0;x<=W;x+=2){const y=zeroY-totalDb(xToFreq(x,W))*scale;x===0?ctx.moveTo(x,y):ctx.lineTo(x,y);}
  ctx.lineTo(W,H);ctx.lineTo(0,H);ctx.fillStyle='rgba(0,212,255,.07)';ctx.fill();
  const bc=['#22d3ee','#2dd4bf','#f43f5e','#fb923c'];
  for(let b=1;b<=4;b++){
    const eq=ch.eq[b];
    const nx=freqToX(eq.freq,W);
    const ny=zeroY-totalDb(eq.freq)*scale;
    ctx.beginPath();ctx.arc(nx,ny,b===selBand?9:7,0,2*Math.PI);
    ctx.strokeStyle=bc[b-1];ctx.lineWidth=2.5;ctx.fillStyle='rgba(3,11,26,.7)';ctx.fill();ctx.stroke();
  }
}

function renderXO(){
  const cvs=document.getElementById('xoCanvas');if(!cvs)return;
  cvs.width=cvs.parentElement.clientWidth;cvs.height=100;
  const ctx=cvs.getContext('2d');const W=cvs.width,H=cvs.height;
  ctx.clearRect(0,0,W,H);
  const hp=parseFloat(document.getElementById('xoHpFreq').value)||80;
  const lp=parseFloat(document.getElementById('xoLpFreq').value)||3200;
  function drawCurve(color,getG){
    ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=2;
    for(let x=0;x<=W;x+=2){const f=xToFreq(x,W);const y=H-getG(f)*(H-8)-4;x===0?ctx.moveTo(x,y):ctx.lineTo(x,y);}
    ctx.stroke();
  }
  drawCurve('#3b82f6',f=>{let g=1;if(f<hp)g=0.02;else if(f<hp*3)g=(f-hp)/(hp*2);if(f>lp)g*=0.02;else if(f>lp/3)g*=1-(f-lp/3)/(lp*2/3);return Math.max(0,Math.min(1,g));});
  drawCurve('#a855f7',f=>{let g=1;if(f<hp)g=0.02;if(f<lp/3)g*=0.02;else if(f<lp)g*=(f-lp/3)/(lp*2/3);return Math.max(0,Math.min(1,g));});
  [hp,lp].forEach((f,i)=>{
    const x=freqToX(f,W);
    ctx.beginPath();ctx.setLineDash([3,4]);ctx.strokeStyle=i===0?'#3b82f6':'#a855f7';ctx.lineWidth=1;ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke();ctx.setLineDash([]);
    ctx.fillStyle=i===0?'#3b82f6':'#a855f7';ctx.font='9px monospace';ctx.fillText(fmtFreq(f),x+3,12);
  });
}

function renderComp(){
  const cvs=document.getElementById('compCanvas');if(!cvs)return;
  cvs.width=cvs.parentElement.clientWidth;cvs.height=cvs.parentElement.clientHeight;
  const ctx=cvs.getContext('2d');const W=cvs.width,H=cvs.height;
  ctx.clearRect(0,0,W,H);
  const thresh=parseFloat(document.getElementById('compThresh').value)||-18;
  const ratio=parseFloat(document.getElementById('compRatio').value)||4;
  const tx=(thresh+40)/40*W;
  ctx.beginPath();ctx.strokeStyle='#00e5b0';ctx.lineWidth=2;ctx.moveTo(0,H);ctx.lineTo(tx,H-(tx/W)*H);
  const gainRed=(W-tx)/ratio;ctx.lineTo(W,H-(tx/W)*H-gainRed);ctx.stroke();
  ctx.beginPath();ctx.setLineDash([4,4]);ctx.strokeStyle='#00e5b0';ctx.lineWidth=1;ctx.globalAlpha=0.4;ctx.moveTo(tx,0);ctx.lineTo(tx,H);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;
  ctx.fillStyle='#00e5b0';ctx.font='9px monospace';ctx.fillText(thresh+' dB',tx+2,H-4);ctx.fillText(ratio.toFixed(1)+':1',W-36,12);
}

function renderLim(){
  const cvs=document.getElementById('limCanvas');if(!cvs)return;
  cvs.width=cvs.parentElement.clientWidth;cvs.height=cvs.parentElement.clientHeight;
  const ctx=cvs.getContext('2d');const W=cvs.width,H=cvs.height;
  ctx.clearRect(0,0,W,H);
  const thresh=parseFloat(document.getElementById('limThresh').value)||-6;
  const tx=(thresh+20)/20*W;
  ctx.beginPath();ctx.strokeStyle='#ff3b5c';ctx.lineWidth=2;ctx.moveTo(0,H);ctx.lineTo(tx,H-(tx/W)*H);ctx.lineTo(W,H-(tx/W)*H);ctx.stroke();
  ctx.beginPath();ctx.setLineDash([4,4]);ctx.strokeStyle='#ff3b5c';ctx.lineWidth=1;ctx.globalAlpha=0.4;ctx.moveTo(tx,0);ctx.lineTo(tx,H);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;
  ctx.fillStyle='#ff3b5c';ctx.font='9px monospace';ctx.fillText(thresh+' dB',tx+2,H-4);ctx.fillText('\u221e:1',W-24,12);
}

function onDyn(){
  const ct=parseFloat(document.getElementById('compThresh').value)||-18;
  const cr=parseFloat(document.getElementById('compRatio').value)||4;
  const ca=parseFloat(document.getElementById('compAttack').value)||5;
  const ce=parseFloat(document.getElementById('compRelease').value)||50;
  document.getElementById('compThreshVal').textContent=ct.toFixed(1)+' dB';
  document.getElementById('compRatioVal').textContent=cr.toFixed(1)+' : 1';
  document.getElementById('compAttackVal').textContent=ca.toFixed(1)+' ms';
  document.getElementById('compReleaseVal').textContent=ce.toFixed(0)+' ms';
  const lt=parseFloat(document.getElementById('limThresh').value)||-6;
  const le=parseFloat(document.getElementById('limRelease').value)||100;
  document.getElementById('limThreshVal').textContent=lt.toFixed(1)+' dB';
  document.getElementById('limReleaseVal').textContent=le.toFixed(0)+' ms';
  renderComp();renderLim();
}

function onDelay(ch,val){
  val=parseFloat(val)||0;
  const dv=document.getElementById('dlyVal'+ch);if(dv)dv.textContent=val.toFixed(3)+' ms';
  const dc=document.getElementById('dlyCm'+ch);if(dc)dc.textContent='('+(val*34.3).toFixed(1)+' cm)';
  const db2=document.getElementById('dlyBar'+ch);if(db2)db2.style.width=Math.min(100,(val/500)*100)+'%';
}

function sendDelay(ch){
  const val=parseFloat(document.getElementById('dlySlider'+ch).value)||0;
  fetch('/api/delay',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel:ch,delay:val})});
}
function sendComp(){fetch('/api/comp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel:selCh,thresh:parseFloat(document.getElementById('compThresh').value),ratio:parseFloat(document.getElementById('compRatio').value),attack:parseFloat(document.getElementById('compAttack').value),release:parseFloat(document.getElementById('compRelease').value)})});}
function sendLim(){fetch('/api/limiter',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel:selCh,thresh:parseFloat(document.getElementById('limThresh').value),release:parseFloat(document.getElementById('limRelease').value)})});}
function sendXo(){fetch('/api/xover',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel:selCh,hp_freq:parseFloat(document.getElementById('xoHpFreq').value),hp_slope:document.getElementById('xoHpSlope').value,lp_freq:parseFloat(document.getElementById('xoLpFreq').value),lp_slope:document.getElementById('xoLpSlope').value})});}

fetch('/api/state').then(r=>r.json()).then(d=>applyState(d));
setInterval(()=>{
  fetch('/api/state').then(r=>r.json()).then(d=>{
    applyState(d);if(d.vu)applyVu(d.vu);
  });
},200);
window.addEventListener('resize',()=>{renderEQ();renderXO();renderComp();renderLim();});
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/state')
def get_state():
    return jsonify(device_state)

@app.route('/api/level', methods=['POST'])
def set_level():
    data = request.json
    ch   = data.get('channel')
    lvl  = data.get('level')
    if ser and ch in device_state['channels']:
        device_state['channels'][ch]['level'] = lvl
        ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Level {lvl}")
    return jsonify({"status": "ok"})

@app.route('/api/mute', methods=['POST'])
def set_mute():
    data  = request.json
    ch    = data.get('channel')
    muted = data.get('muted')
    if ser and ch in device_state['channels']:
        device_state['channels'][ch]['muted'] = (muted == 1)
        ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Mute {muted}")
    return jsonify({"status": "ok"})

@app.route('/api/polarity', methods=['POST'])
def set_polarity():
    data = request.json
    ch   = data.get('channel')
    pol  = data.get('polarity', 'NORMAL')
    if ser and ch in device_state['channels']:
        device_state['channels'][ch]['polarity'] = pol
        val = 1 if pol == 'INVERTED' else 0
        ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Polarity {val}")
    return jsonify({"status": "ok"})

@app.route('/api/delay', methods=['POST'])
def set_delay():
    data = request.json
    ch   = data.get('channel')
    dly  = data.get('delay', 0)
    if ser and ch in device_state['channels']:
        device_state['channels'][ch]['delay'] = str(dly)
        ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Delay {dly:.3f}")
    return jsonify({"status": "ok"})

@app.route('/api/preset', methods=['POST'])
def set_preset():
    data = request.json
    num  = data.get('preset')
    if ser and num:
        ser.send_cmd(f"/ID{DEVICE_ID}/Recall {num}")
        time.sleep(0.3)
        sync_hardware()
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

@app.route('/api/comp', methods=['POST'])
def set_comp():
    data = request.json
    ch   = data.get('channel')
    if ch in device_state['channels']:
        c = device_state['channels'][ch]['comp']
        c['thresh']  = data.get('thresh', c['thresh'])
        c['ratio']   = data.get('ratio',  c['ratio'])
        c['attack']  = data.get('attack', c['attack'])
        c['release'] = data.get('release',c['release'])
        if ser:
            ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Comp/Threshold {c['thresh']:.1f}")
            ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Comp/Ratio {c['ratio']:.1f}")
    return jsonify({"status": "ok"})

@app.route('/api/limiter', methods=['POST'])
def set_limiter():
    data = request.json
    ch   = data.get('channel')
    if ch in device_state['channels']:
        lm = device_state['channels'][ch]['limiter']
        lm['thresh']  = data.get('thresh',  lm['thresh'])
        lm['release'] = data.get('release', lm['release'])
        if ser:
            ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Lim/Threshold {lm['thresh']:.1f}")
    return jsonify({"status": "ok"})

@app.route('/api/xover', methods=['POST'])
def set_xover():
    data = request.json
    ch   = data.get('channel')
    if ch in device_state['channels']:
        device_state['channels'][ch]['lowcut_freq']  = data.get('hp_freq', 80)
        device_state['channels'][ch]['highcut_freq'] = data.get('lp_freq', 20000)
        if ser:
            ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Hpf/Freq {data.get('hp_freq', 80):.0f}")
            ser.send_cmd(f"/ID{DEVICE_ID}/Out{ch}/Lpf/Freq {data.get('lp_freq', 20000):.0f}")
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    print("[*] EV Dx38 Pro Web Controller — Adaptive DSP Dashboard")
    try:
        ser = WinSerial(COM_PORT)
        sync_hardware()
    except Exception as e:
        print(f"[-] Serial error: {e} (running in demo mode)")

    t = threading.Thread(target=background_loop, daemon=True)
    t.start()

    app.run(host='0.0.0.0', port=5000, debug=False)
