"""HTTP routes for the parallel staging application."""

from flask import Blueprint, current_app, jsonify, request

api = Blueprint("staging_api", __name__, url_prefix="/api")


def _payload() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("request body must be a JSON object")
    return data


def _service():
    return current_app.extensions["control_service"]


@api.get("/health")
def health():
    service = _service()
    return jsonify({
        "status": "ok",
        "mode": "hardware" if service.serial.connected else "offline",
        "serial_connected": service.serial.connected,
    })


@api.get("/state")
def get_state():
    return jsonify(_service().state.snapshot())


@api.post("/level")
def set_level():
    try:
        data = _payload()
        service = _service()
        channel = service.validate_channel_payload(data)
        level = float(data["level"])
        service.set_level(channel, level)
        return jsonify({"status": "ok", "confirmed": service.serial.connected})
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 503


@api.post("/mute")
def set_mute():
    try:
        data = _payload()
        service = _service()
        channel = service.validate_channel_payload(data)
        if not isinstance(data.get("muted"), bool):
            raise ValueError("muted must be a boolean")
        service.set_mute(channel, data["muted"])
        return jsonify({"status": "ok", "confirmed": service.serial.connected})
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 503
