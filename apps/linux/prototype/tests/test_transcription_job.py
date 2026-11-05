from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from transcription_config import TranscriptionConfig
from openrouter_transcription import TranscriptionError
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
        self.assertTrue(closed.is_set())
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
