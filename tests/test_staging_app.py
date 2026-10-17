import unittest

from flask.testing import FlaskClient
from werkzeug.test import EnvironBuilder

from staging.app import create_app


class CompatibleFlaskClient(FlaskClient):
    def open(self, *args, **kwargs):
        as_tuple = kwargs.pop("as_tuple", False)
        buffered = kwargs.pop("buffered", False)
        follow_redirects = kwargs.pop("follow_redirects", False)
        kwargs["environ_base"] = {**self.environ_base, **kwargs.get("environ_base", {})}
        builder = EnvironBuilder(*args, **kwargs)
        try:
            response = super(FlaskClient, self).open(
                builder.get_request(), buffered=buffered, follow_redirects=follow_redirects
            )
        finally:
            builder.close()
        return (response, response.status, response.headers) if as_tuple else response


class FakeSerial:
    def __init__(self):
        self.commands = []

    @property
    def connected(self):
        return True

    def send_cmd(self, command):
        self.commands.append(command)

    def query(self, command, max_bytes=512):
        return ""

    def close(self):
        pass


class StagingAppTests(unittest.TestCase):
    def setUp(self):
        self.serial = FakeSerial()
        self.app = create_app(serial_transport=self.serial, config_object={"TESTING": True, "DEVICE_ID": "1"})
        self.app.test_client_class = CompatibleFlaskClient
        self.client = self.app.test_client()

    def test_health_reports_hardware_transport(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["mode"], "hardware")

    def test_level_validates_and_sends_command(self):
        response = self.client.post("/api/level", json={"channel": 2, "level": -6.5})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.serial.commands, ["/ID1/Out2/Level -6.5"])
        state = self.client.get("/api/state").get_json()
        self.assertEqual(state["channels"]["2"]["level"], -6.5)

    def test_rejects_invalid_level_without_sending(self):
        response = self.client.post("/api/level", json={"channel": 1, "level": 99})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.serial.commands, [])

    def test_rejects_non_object_json(self):
        response = self.client.post("/api/mute", json=[1, 2])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.serial.commands, [])

    def test_mute_requires_boolean(self):
        response = self.client.post("/api/mute", json={"channel": 1, "muted": "true"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.serial.commands, [])
