"""Live chunk ordering, bounded buffering and cancellation without GI/model downloads."""
import sys
from pathlib import Path
import threading
import time
import unittest
import wave
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_session import LiveSession, CHUNK_BYTES, MAX_PCM_BYTES
from transcription_config import LocalTranscriptionConfig
from transcription_client import TranscriptionError


class LiveSessionTests(unittest.TestCase):
    def session(self, transcriber):
        calls = []
        completed = threading.Event()
        def callback(session, text, error, done):
            calls.append((text, error, done))
            if done:
                completed.set()
        session = LiveSession(LocalTranscriptionConfig(), lambda callback: callback(), callback,
                              transcriber=transcriber)
        self.addCleanup(session.cancel)
        return session, calls, completed

    def test_order_and_short_tail_are_complete_private_wavs(self):
        lengths = []
        def transcriber(path, config, cancelled, attach):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with wave.open(str(path)) as audio:
                lengths.append(audio.getnframes() * 2)
            return str(len(lengths))
        session, calls, done = self.session(transcriber)
        session.feed(b'\x00\x01' * ((CHUNK_BYTES * 2 + 3200) // 2))
        session.finish()
        self.assertTrue(done.wait(3))
        self.assertEqual(lengths, [CHUNK_BYTES, CHUNK_BYTES, 3200])
        self.assertEqual([text for text, error, finished in calls if text], ['1', '2', '3'])
        self.assertEqual(calls[-1], (None, None, True))

    def test_silence_is_not_a_terminal_error(self):
        session, calls, done = self.session(lambda *args: '')
        session.feed(b'\0' * CHUNK_BYTES)
        session.finish()
        self.assertTrue(done.wait(3))
        self.assertEqual(calls[-1], (None, None, True))
        self.assertFalse(any(error for text, error, finished in calls))

    def test_failure_is_fixed_and_stops_later_chunks(self):
        def fail(*args):
            raise TranscriptionError('local_unavailable')
        session, calls, done = self.session(fail)
        session.feed(b'\0' * (CHUNK_BYTES * 2))
        session.finish()
        self.assertTrue(done.wait(3))
        self.assertEqual(calls, [(None, 'local_unavailable', True)])

    def test_cancel_discards_queued_and_late_results(self):
        entered, release = threading.Event(), threading.Event()
        def slow(*args):
            entered.set()
            release.wait(2)
            return 'late'
        session, calls, done = self.session(slow)
        session.feed(b'\0' * CHUNK_BYTES)
        self.assertTrue(entered.wait(2))
        session.cancel()
        release.set()
        session.join(2)
        self.assertEqual(calls, [])

    def test_limit_drains_previously_accepted_audio_despite_late_stop(self):
        entered, release = threading.Event(), threading.Event()
        lengths = []
        def delayed(path, *args):
            entered.set()
            release.wait(2)
            with wave.open(str(path)) as wav:
                lengths.append(wav.getnframes() * 2)
            return 'fixture'
        session, calls, done = self.session(delayed)
        session.feed(b'\0' * CHUNK_BYTES)
        self.assertTrue(entered.wait(2))
        session.feed(b'\0' * (MAX_PCM_BYTES - CHUNK_BYTES + 320))
        release.set()
        session.finish()
        self.assertTrue(done.wait(5))
        self.assertEqual(sum(lengths), MAX_PCM_BYTES)
        self.assertFalse(any(error for text,error,finished in calls))
        self.assertEqual(calls[-1], (None, None, True))

    def test_cloud_is_rejected_before_worker_start(self):
        with self.assertRaises(ValueError):
            LiveSession(type('Cloud', (), {'provider': 'openrouter'})(), lambda f: f(), lambda *args: None)
