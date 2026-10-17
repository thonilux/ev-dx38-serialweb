# EV Dx38 Pro Web Console

[![CI](https://github.com/thonilux/ev-dx38-serialweb/actions/workflows/ci.yml/badge.svg)](https://github.com/thonilux/ev-dx38-serialweb/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)

Modern, high-density Web Controller & DSP Management Interface for the **Electro-Voice Dx38** and **Dynacord DSP244** digital sound processors. Built as a high-performance web-based replacement for the legacy Windows `RACE.exe` software, offering adaptive touch-first workflows, live VU metering, and zero-latency hardware control.

---

## 📁 Repository Structure

```text
re-race/
├── .github/                    # GitHub configuration & workflows
│   ├── workflows/ci.yml        # Multi-OS CI automated testing pipeline
│   ├── ISSUE_TEMPLATE/         # Structured issue report forms
│   └── PULL_REQUEST_TEMPLATE.md# Pull request template & checklist
├── .gitattributes              # Git line endings & binary asset rules
├── .gitignore                  # Git untracked pattern definitions
├── LICENSE                     # MIT open source license
├── CONTRIBUTING.md             # Developer setup & contribution guidelines
├── SECURITY.md                 # Vulnerability reporting policy
├── app.py                      # Main production Web Console application
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation & reference
│
├── staging/                    # Modernized parallel Flask application
│   ├── app.py                  # Application factory
│   ├── config.py               # Environment configuration
│   ├── routes.py               # API endpoints
│   ├── serial.py               # Serial transport layer
│   ├── services.py             # Control service layer
│   ├── state.py                # Thread-safe state store
│   ├── static/                 # Console CSS and JS
│   └── templates/              # Console HTML template
│
├── docs/                       # Specifications, protocols, and documentation
│   ├── dx38_full_features.md   # Catalog of all extracted serial commands
│   ├── ev_dx38_protocol.md     # Sniffed hardware communication protocol
│   ├── plan.md                 # System architecture and roadmap
│   └── SKILL.md                # Reverse engineering & CHM reference
│
├── firmware/                   # Microcontroller & hardware controller code
│   └── esp32/
│       └── esp32_dx38_controller.ino # Standalone ESP32 WiFi web bridge
│
├── tools/                      # Reverse engineering & analysis utilities
│   ├── dump_commands.py        # Command strings extractor
│   ├── dump_rs232lib.py        # RS232Lib DLL exported function inspector
│   ├── find_protocol.py        # ASCII string pattern detector
│   ├── generate_feature_catalog.py # Automatic command catalog generator
│   ├── inspect_rs232.py        # Binary constant & opcode scanner
│   ├── probe.py                # Virtual serial port interceptor / proxy
│   └── serial_sniffer.py       # Serial traffic sniffer and logger
│
├── tests/                      # Hardware diagnostic & verification scripts
│   ├── fast_query.py           # High-speed parameter query tester
│   ├── running_led_mute.py     # Channel mute & LED sequence test
│   ├── sync_state.py           # Full state synchronization script
│   ├── test_com2.py            # Serial port COM2 liveness probe
│   ├── test_dump_trigger.py    # Binary memory dump trigger test
│   ├── test_freq_leds.py       # Frequency and filter LED tester
│   ├── test_get_params.py      # Parameter syntax query tester
│   ├── test_routing_leds.py    # Routing LED indicators test
│   ├── test_win32_serial.py    # Low-level Win32 serial communication test
│   └── test_win_write.py       # Raw serial packet writer test
│
├── legacy/                     # Archived earlier prototype versions
│   └── app-sonnet.py           # Initial prototype dashboard
│
├── vendor/                     # Original vendor software & utilities
│   ├── RACE.exe                # Electro-Voice RACE software v1.4.1
│   ├── RACE.chm                # Original compiled help manual
│   ├── Rs232Lib.dll            # Original communications dynamic library
│   ├── extracted_chm/          # Decompiled help documentation & HTML assets
│   └── PortMon/                # Sysinternals serial port monitoring tool
│
└── .agents/                    # Specialized AI agent skills
    └── skills/
        └── race-chm-guide/     # Dx38 knowledge base & operations guide
```

---

## Staging Application

A parallel, intentionally limited Flask package is available for incremental architecture work. It does not replace or modify the existing hardware console in `app.py` and defaults to offline mode.

Run it from the repository root:

```bash
python -m staging
```

It serves on `http://127.0.0.1:5001` by default. Available configuration variables are `RERACE_HOST`, `RERACE_PORT`, `RERACE_DEBUG`, `RERACE_COM_PORT`, `RERACE_DEVICE_ID`, `RERACE_SERIAL_BAUDRATE`, and `RERACE_DEMO_MODE`. Hardware integration is deliberately not enabled in this staging version; only the health/state, level, and mute API routes are currently implemented. Run its focused tests with:

```bash
python -m unittest tests.test_staging_app
```

## ⚡ Features & Capabilities

- **Adaptive Console Design**: Professional dark console theme, responsive channel faders, color-coded frequency indicators, and high-visibility status LEDs.
- **Hardware-Accurate Metering**:
  - Live 24-segment broadcast meter bridge with hardware -30 dB LUFS calibration.
  - Active **COMP** (Compressor) and **CLIP** (Peak Limiter) LEDs accurately decoded from live `/ID1/VU ?` status flags.
- **Full Hardware DSP Integration**:
  - **Fader & Output Level**: Realtime volume adjustments in 0.5 dB steps.
  - **Mute & Polarity**: Individual channel mute, Master Mute, and Polarity Invert ($\varnothing$).
  - **Speaker Alignment / Delay**: Millisecond, meter, and feet readouts up to 500 ms.
  - **4-Band Parametric Equalizer**: 4 PEQ bands per channel with visual Bode response graph.
  - **Crossover Engine**: High-pass & Low-pass with all Dx38 slopes (*Linkwitz-Riley 12/24dB, Butterworth 12/18/24dB, Bessel 12/18/24dB, 6dB, and Thru*).
  - **Dynamics Engine**: Threshold, Ratio, Attack, and Release controls with transfer characteristic curves.
  - **Preset Library & Routing Config**: 30 user presets and hardware routing modes (*2-Way Stereo, 3-Way Mono, etc.*).
- **Graceful Offline & Auto-Reconnect Engine**:
  - Runs in demo mode when disconnected.
  - Automatically reconnects to `COM2` the instant the physical hardware or USB adapter is plugged in.

---

## 🚀 Quickstart

### 1. Requirements
- Python 3.9+
- Windows OS (for native Win32 `COM2` serial communication) or Linux/macOS in demo mode.

Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Running the Web Console
```bash
python app.py
```
Open your browser at:
```text
http://127.0.0.1:5000/
```

### 3. RS-232 Serial Port Configuration
- **Port**: `COM2` (configurable via `COM_PORT` in `app.py`)
- **Baud Rate**: `19200 bps` (or `38400 bps` matching hardware utility menu)
- **Data Bits**: `8`
- **Parity**: `None`
- **Stop Bits**: `1`
- **Flow Control**: `None`
