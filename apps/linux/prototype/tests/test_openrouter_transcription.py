import base64
import http.client
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from transcription_config import TranscriptionConfig
from openrouter_transcription import TranscriptionError, transcribe


def wav_bytes(frames=160, rate=16000):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * frames)
    return output.getvalue()


class Response:
    def __init__(self, status=200, body=None):
        self.status = status
        self.body = io.BytesIO(body if body is not None else b'{"text":"Guten Morgen."}')

    def read(self, size):
        return self.body.read(size)


class Connection:
    def __init__(self, response=None):
        self.response = response or Response()
        self.requests = []
        self.closed = False

    def connect(self):
        pass

    def request(self, method, path, body, headers):
        self.requests.append((method, path, body, headers))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class OpenRouterTranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "sample.wav"
        self.path.write_bytes(wav_bytes())
        self.config = TranscriptionConfig("synthetic-private-key", "openai/whisper-large-v3-turbo")
        self.cancelled = threading.Event()

    def call(self, connection, attach=None):
        self.factory_calls = []
        def factory(host, timeout):
            self.factory_calls.append((host, timeout))
            return connection
        return transcribe(self.path, self.config, self.cancelled,
                          attach or (lambda connection: None), connection_factory=factory)

    def test_sends_wav_to_fixed_https_endpoint_and_returns_text(self):
        connection = Connection()
        self.assertEqual(self.call(connection), "Guten Morgen.")
        method, path, body, headers = connection.requests[0]
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/api/v1/audio/transcriptions")
        self.assertEqual(self.factory_calls[0][0], "openrouter.ai")
        self.assertEqual(headers["Authorization"], "Bearer synthetic-private-key")
        payload = json.loads(body)
        self.assertEqual(payload["model"], self.config.model)
        self.assertEqual(payload["input_audio"]["format"], "wav")
        self.assertEqual(base64.b64decode(payload["input_audio"]["data"]), self.path.read_bytes())
        self.assertTrue(connection.closed)

    def test_http_errors_are_redacted_and_not_retried(self):
        for status, code in [(401,"credentials"), (403,"credentials"), (402,"credits"),
                             (429,"rate_limit"), (500,"provider"), (302,"provider")]:
            with self.subTest(status=status):
                connection = Connection(Response(status, b'{"error":"synthetic-private-key"}'))
                with self.assertRaises(TranscriptionError) as error:
                    self.call(connection)
                self.assertEqual(error.exception.code, code)
                self.assertNotIn("synthetic-private-key", str(error.exception))
                self.assertEqual(len(connection.requests), 1)
                self.assertTrue(connection.closed)

    def test_rejects_invalid_empty_or_oversized_response(self):
        for body in [b"not-json", b"{}", b'{"text":""}', b'{"text":null}', b'["wrong-shape"]']:
            with self.subTest(body=body):
                with self.assertRaises(TranscriptionError) as error:
                    self.call(Connection(Response(body=body)))
                self.assertEqual(error.exception.code, "response")
        with patch("openrouter_transcription.MAX_RESPONSE_BYTES", 16):
            with self.assertRaises(TranscriptionError):
                self.call(Connection(Response(body=b" " * 17)))

    def test_missing_or_invalid_audio_never_opens_connection(self):
        for content in [b"", b"not a WAV"]:
            self.path.write_bytes(content)
            with self.assertRaises(TranscriptionError) as error:
                self.call(Connection())
            self.assertEqual(error.exception.code, "invalid_audio")
            self.assertEqual(self.factory_calls, [])
        self.path.unlink()
        with self.assertRaises(TranscriptionError) as error:
            self.call(Connection())
        self.assertEqual(error.exception.code, "missing_audio")

    def test_rejects_audio_size_and_duration_before_request(self):
        with patch("openrouter_transcription.MAX_AUDIO_BYTES", 32):
            with self.assertRaises(TranscriptionError) as error:
                self.call(Connection())
            self.assertEqual(error.exception.code, "audio_too_large")
        self.path.write_bytes(wav_bytes(frames=301, rate=1))
        with self.assertRaises(TranscriptionError) as error:
            self.call(Connection())
        self.assertEqual(error.exception.code, "audio_too_long")
        self.assertEqual(self.factory_calls, [])

    def test_cancel_before_request_prevents_upload(self):
        self.cancelled.set()
        with self.assertRaises(TranscriptionError) as error:
            self.call(Connection())
        self.assertEqual(error.exception.code, "cancelled")
        self.assertEqual(self.factory_calls, [])

    def test_cancel_after_connection_attaches_prevents_upload_and_closes(self):
        connection = Connection()
        with self.assertRaises(TranscriptionError):
            self.call(connection, lambda connection: self.cancelled.set())
        self.assertEqual(connection.requests, [])
        self.assertTrue(connection.closed)

    def test_network_errors_and_timeout_are_fixed_messages(self):
        for failure, code in [(socket.timeout("private-token"), "timeout"),
                              (OSError("private-token"), "network")]:
            connection = Connection()
            connection.getresponse = lambda: (_ for _ in ()).throw(failure)
            with self.subTest(code=code):
                with self.assertRaises(TranscriptionError) as error:
                    self.call(connection)
                self.assertEqual(error.exception.code, code)
                self.assertNotIn("private-token", str(error.exception))
                self.assertTrue(connection.closed)

    def test_cancelled_connection_cannot_automatically_reconnect_and_upload(self):
        cancelled = self.cancelled
        sent = []
        class Socket:
            def sendall(self, data):
                sent.append(data)
            def close(self):
                pass
        class ClosingConnection(http.client.HTTPConnection):
            def connect(self):
                self.sock = Socket()
            def request(self, *args, **kwargs):
                # Cancel lands after the client's last cancellation check.
                cancelled.set()
                self.close()
                super().request(*args, **kwargs)
            def getresponse(self):
                return Response()
        with self.assertRaises(TranscriptionError):
            self.call(ClosingConnection("unused.invalid"))
        self.assertEqual(sent, [], "HTTPConnection must not reopen after cancellation")

