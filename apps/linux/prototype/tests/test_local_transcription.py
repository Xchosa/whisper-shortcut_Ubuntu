import base64
import importlib.util
import json
import http.client
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from transcription_config import ConfigError, LocalTranscriptionConfig, load_config
from transcription_client import transcribe
from test_openrouter_transcription import Connection, wav_bytes

SERVER = Path(__file__).resolve().parents[2] / "services/transcription/server.py"


class LocalConfigurationTests(unittest.TestCase):
    def test_local_is_default_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config(Path("/nonexistent/config"))
        self.assertEqual(config.provider, "local")
        self.assertEqual(config.model, "base")
        self.assertEqual(config.base_url, "http://127.0.0.1:8765")
        self.assertFalse(hasattr(config, "api_key"))

    def test_cloud_key_alone_does_not_enable_cloud(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "unused-key"}, clear=True):
            config = load_config(Path("/nonexistent/config"))
        self.assertEqual(config.provider, "local")

    def test_local_url_must_be_plain_loopback_http(self):
        urls = ["https://example.com", "http://192.168.1.2:8765",
                "http://127.0.0.1:8765/steal", "http://key@localhost:8765",
                "http://localhost:8765?secret=value"]
        for url in urls:
            with self.subTest(url=url), patch.dict(os.environ,
                    {"LOCAL_TRANSCRIPTION_URL": url}, clear=True):
                with self.assertRaises(ConfigError):
                    load_config(Path("/nonexistent/config"))

    def test_local_request_never_contains_cloud_credentials(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.wav"
            path.write_bytes(wav_bytes())
            connection = Connection()
            def factory(host, port, timeout):
                self.assertEqual((host, port), ("127.0.0.1", 8765))
                return connection
            config = LocalTranscriptionConfig()
            self.assertEqual(transcribe(path, config, threading.Event(), lambda conn: None,
                                        connection_factory=factory), "Guten Morgen.")
            _, endpoint, body, headers = connection.requests[0]
            self.assertEqual(endpoint, "/v1/audio/transcriptions")
            self.assertNotIn("Authorization", headers)
            self.assertEqual(json.loads(body)["model"], "base")


class LocalServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("local_stt_server", SERVER)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def setUp(self):
        class Model:
            def transcribe(inner, audio, **options):
                self.options = options
                return iter([SimpleNamespace(text=" Guten Morgen.")]), SimpleNamespace(language="de")
        self.server = self.module.make_server(Model(), host="127.0.0.1", port=0)
        self.worker = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.01}, daemon=True)
        self.worker.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.worker.join, 1)
        self.addCleanup(self.server.shutdown)

    def request(self, method="POST", path="/v1/audio/transcriptions", body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        try:
            conn.request(method, path, body=body,
                         headers=headers or {"Content-Type": "application/json"})
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def payload(self, **extra):
        return json.dumps({"model": "base",
                           "input_audio": {"format": "wav", "data": base64.b64encode(wav_bytes()).decode()},
                           **extra}).encode()

    def test_health_and_valid_transcription(self):
        status, health = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["model"], "base")
        status, body = self.request(body=self.payload())
        self.assertEqual((status, body["text"]), (200, "Guten Morgen."))
        self.assertEqual(self.options["task"], "transcribe")

    def test_rejects_origin_and_non_json_requests(self):
        status, body = self.request(body=self.payload(),
            headers={"Content-Type": "application/json", "Origin": "https://untrusted.invalid"})
        self.assertEqual(status, 403)
        status, body = self.request(body=b"not-json", headers={"Content-Type": "text/plain"})
        self.assertEqual(status, 415)

    def test_invalid_requests_are_fixed_errors(self):
        for payload in [b"not-json", b"[]", self.payload(model="download-something"),
                        b'{"model":"base","input_audio":{"format":"wav","data":"???"}}']:
            with self.subTest():
                status, body = self.request(body=payload)
                self.assertEqual(status, 400)
                self.assertEqual(body, {"error": "invalid_request"})

    def test_busy_model_does_not_queue_second_inference(self):
        self.server.inference_gate.acquire()
        try:
            status, body = self.request(body=self.payload())
            self.assertEqual((status, body), (503, {"error": "busy"}))
        finally:
            self.server.inference_gate.release()

    def test_model_loader_is_cpu_int8_and_offline(self):
        seen = {}
        def factory(path, **kwargs):
            seen.update(kwargs)
            return object()
        self.module.load_model(factory=factory)
        self.assertEqual(seen["device"], "cpu")
        self.assertEqual(seen["compute_type"], "int8")
        self.assertTrue(seen["local_files_only"])
