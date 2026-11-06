from pathlib import Path
import http.client
import socket
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from transcription_config import TranscriptionConfig
from transcription_client import TranscriptionError
from transcription_job import TranscriptionJob


class TranscriptionJobTests(unittest.TestCase):
    def make_job(self, transcriber, timeout=1):
        self.callbacks = []
        self.dispatched = threading.Event()
        self.completed = []
        def dispatch(callback):
            self.callbacks.append(callback)
            self.dispatched.set()
        job = TranscriptionJob(Path("unused.wav"), TranscriptionConfig("synthetic-key", "vendor/model"),
                               dispatch, lambda *args: self.completed.append(args),
                               transcriber=transcriber, timeout=timeout)
        self.addCleanup(job.cancel)
        return job

    def test_success_is_dispatched_once_with_job_identity(self):
        job = self.make_job(lambda *args: "result")
        job.start()
        self.assertTrue(self.dispatched.wait(1))
        self.assertEqual(self.completed, [])
        self.callbacks[0]()
        self.assertEqual(self.completed, [(job, "result", None)])

    def test_cancel_before_start_never_invokes_transcriber(self):
        called = threading.Event()
        job = self.make_job(lambda *args: called.set())
        job.cancel()
        job.start()
        self.assertFalse(called.is_set())
        self.assertEqual(self.callbacks, [])

    def test_cancel_closes_connection_and_discards_late_result(self):
        entered = threading.Event()
        release = threading.Event()
        closed = threading.Event()
        connection = type("Connection", (), {"close": lambda self: closed.set()})()
        def transcriber(path, config, cancelled, attach):
            attach(connection)
            entered.set()
            release.wait(1)
            return "late"
        job = self.make_job(transcriber)
        job.start()
        self.assertTrue(entered.wait(1))
        job.cancel()
        release.set()
        job.join(1)
        self.assertTrue(closed.wait(1))
        self.assertEqual(self.callbacks, [])

    def test_deadline_publishes_timeout_once_and_ignores_late_completion(self):
        release = threading.Event()
        job = self.make_job(lambda *args: (release.wait(1), "late")[1], timeout=0.03)
        job.start()
        self.assertTrue(self.dispatched.wait(1))
        release.set()
        job.join(1)
        self.assertEqual(len(self.callbacks), 1)
        self.callbacks[0]()
        self.assertEqual(self.completed, [(job, None, "timeout")])

    def test_errors_only_publish_fixed_code(self):
        for error, code in [(TranscriptionError("credits"), "credits"),
                            (RuntimeError("private-token"), "network")]:
            def fail(*args):
                raise error
            job = self.make_job(fail)
            job.start()
            self.assertTrue(self.dispatched.wait(1))
            self.callbacks[0]()
            self.assertEqual(self.completed, [(job, None, code)])

    def stalled_http_response(self):
        blocked = threading.Event()
        body_phase = threading.Event()
        class ObservedSocket(socket.socket):
            def recv_into(self, *args, **kwargs):
                if body_phase.is_set():
                    blocked.set()  # BufferedReader owns its lock at this boundary.
                return super().recv_into(*args, **kwargs)
        client, peer = socket.socketpair()
        observed = ObservedSocket(fileno=client.detach())
        observed.settimeout(2)
        connection = http.client.HTTPConnection("unused.invalid")
        connection.sock = observed
        connection.request("GET", "/synthetic-test")
        peer.recv(4096)
        peer.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\nx")
        response = connection.getresponse()
        body_phase.set()
        return connection, response, peer, blocked

    def test_cancel_does_not_wait_for_real_http_reader_lock(self):
        connection, response, peer, blocked = self.stalled_http_response()
        def transcriber(path, config, cancelled, attach):
            attach(connection)
            return response.read().decode()
        job = self.make_job(transcriber)
        returned = threading.Event()
        closer = threading.Thread(target=lambda: (job.cancel(), returned.set()), daemon=True)
        try:
            job.start()
            self.assertTrue(blocked.wait(1))
            closer.start()
            prompt = returned.wait(0.2)
        finally:
            peer.close()
            job.join(1)
            if closer.ident:
                closer.join(1)
            connection.close()
        self.assertTrue(prompt, "Cancel must not wait for HTTPResponse's reader lock")
        self.assertEqual(self.callbacks, [])

    def test_deadline_dispatches_before_blocking_http_cleanup(self):
        connection, response, peer, blocked = self.stalled_http_response()
        def transcriber(path, config, cancelled, attach):
            attach(connection)
            return response.read().decode()
        job = self.make_job(transcriber, timeout=0.05)
        try:
            job.start()
            self.assertTrue(blocked.wait(1))
            prompt = self.dispatched.wait(0.3)
        finally:
            peer.close()
            job.join(1)
            connection.close()
        self.assertTrue(prompt, "Deadline publication must not wait for transport cleanup")
        self.callbacks[0]()
        self.assertEqual(self.completed, [(job, None, "timeout")])
