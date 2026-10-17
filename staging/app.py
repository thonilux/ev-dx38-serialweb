"""Flask application factory for the parallel staging implementation."""

from copy import deepcopy

from flask import Flask, render_template

from .config import Config
from .routes import api
from .serial import OfflineTransport
from .services import ControlService
from .state import StateStore

_INITIAL_STATE = {
    "connected": False,
    "mode": "offline",
    "device_name": "EV Dx38 (offline)",
    "channels": {
        channel: {"name": f"OUT {channel}", "level": 0.0, "muted": False}
        for channel in range(1, 5)
    },
}


def create_app(config_object=Config, serial_transport=None, initial_state=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if isinstance(config_object, dict):
        app.config.update(config_object)
    elif config_object is not Config:
        app.config.from_object(config_object)
    state = StateStore(deepcopy(initial_state if initial_state is not None else _INITIAL_STATE))
    transport = serial_transport if serial_transport is not None else OfflineTransport()
    app.extensions["control_service"] = ControlService(
        state, transport, device_id=str(app.config["DEVICE_ID"])
    )
    app.register_blueprint(api)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"status": "error", "message": "not found"}), 404

    return app
