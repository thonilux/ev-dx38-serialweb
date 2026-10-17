# RACE Staging Application

A parallel Flask application package for incrementally restructuring the EV Dx38 / Dynacord DSP244 controller. The existing root-level `app.py` remains the primary working application and is not used or modified by this package.

## Status

This is an early staging foundation, not a replacement for the production console. It currently provides:

- Application factory (`create_app`) and environment-based configuration.
- Thread-safe in-memory state snapshots.
- A serial transport protocol and offline transport placeholder.
- Validated API endpoints for health, state, output level, and mute.
- A responsive browser web console with channel level and mute controls.
- Unit tests using a fake serial transport.

Hardware communication and the full existing dashboard are intentionally not integrated yet. Staging starts offline, so it will not send commands to a physical device unless a connected transport is explicitly supplied by code.

## Run

From the repository root:

```powershell
python -m staging
```

The server listens on `http://127.0.0.1:5001` by default. This staging app is separate from the current `app.py` server, which uses port 5000.

## Configuration

Set these environment variables before launching:

| Variable | Default | Description |
| --- | --- | --- |
| `RERACE_HOST` | `127.0.0.1` | Bind address. Keep localhost unless LAN access is explicitly required. |
| `RERACE_PORT` | `5001` | HTTP port for the staging server. |
| `RERACE_DEBUG` | `0` | Enable Flask debug mode for local development only. |
| `RERACE_COM_PORT` | `COM2` | Reserved serial port setting for future transport integration. |
| `RERACE_DEVICE_ID` | `1` | Device ID used when generating control commands. |
| `RERACE_SERIAL_BAUDRATE` | `19200` | Reserved serial baud-rate setting. |
| `RERACE_DEMO_MODE` | `1` | Reserved mode setting; staging currently uses the offline transport by default. |

## API

- `GET /` — staging web console.
- `GET /api/health` — application/transport status.
- `GET /api/state` — current in-memory state snapshot.
- `POST /api/level` — set an output level. JSON: `{"channel": 1, "level": -6.0}`. Channel must be 1–4 and level must be -80 to +12 dB.
- `POST /api/mute` — set output mute. JSON: `{"channel": 1, "muted": true}`. `muted` must be a JSON boolean.

With the default offline transport, control updates modify the in-memory staging state but are not hardware-confirmed. API responses report `confirmed: false` in this mode.

## Tests

From the repository root:

```powershell
python -m unittest tests.test_staging_app
```

The tests exercise route behavior and validation using a fake serial transport; they do not verify communication with physical Dx38/DSP244 hardware.

## Package Layout

```text
staging/
├── __init__.py   # Package marker
├── __main__.py   # `python -m staging` entrypoint
├── app.py        # Flask application factory
├── config.py     # Environment-backed configuration
├── routes.py     # HTTP API endpoints
├── serial.py     # Serial transport protocol and offline implementation
├── services.py  # Control validation and service logic
├── state.py      # Thread-safe in-memory state store
├── static/       # Console CSS and JavaScript
├── templates/    # Flask-rendered web console
└── README.md     # Staging-specific documentation
```
