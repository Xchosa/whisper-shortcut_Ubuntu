"""Bounded PCM sections, one cancellable local inference at a time; no GTK calls."""
from functools import partial
from pathlib import Path
import queue
import tempfile
import threading
import wave
from transcription_client import transcribe
from transcription_job import TranscriptionJob

RATE = 16000
CHUNK_BYTES = RATE * 2 * 5
MAX_PCM_BYTES = RATE * 2 * 300


class LiveSession:
    def __init__(self, config, dispatch, callback, *, transcriber=None):
        if config.provider != 'local':
            raise ValueError('Live dictation requires local inference')
        self.config, self.dispatch, self.callback = config, dispatch, callback
        self.transcriber = transcriber or partial(transcribe, allow_empty=True)
        self._lock = threading.RLock()
        self._queue = queue.Queue(maxsize=61)
        self._buffer = bytearray()
        self._total = 0
        self._accepting = True
        self._terminal = False
        self._cancelled = threading.Event()
        self._halted = threading.Event()
        self._job = None
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def _publish(self, text=None, error=None, done=False):
        with self._lock:
            if self._terminal or self._cancelled.is_set():
                return
            if done:
                self._terminal = True
                self._accepting = False
            def deliver():
                if not self._cancelled.is_set():
                    self.callback(self, text, error, done)
                return False
            self.dispatch(deliver)

    def feed(self, pcm):
        with self._lock:
            if not self._accepting or self._halted.is_set():
                return
            available = MAX_PCM_BYTES - self._total
            limited = len(pcm) >= available
            pcm = pcm[:available]
            self._total += len(pcm)
            self._buffer.extend(pcm)
            while len(self._buffer) >= CHUNK_BYTES:
                self._queue.put_nowait(bytes(self._buffer[:CHUNK_BYTES]))
                del self._buffer[:CHUNK_BYTES]
            if limited:
                self.finish()  # Normal limit completion: drain, never cancel accepted sections.
            return limited

    def finish(self):
        with self._lock:
            if not self._accepting:
                return
            self._accepting = False
            if self._buffer:
                self._queue.put_nowait(bytes(self._buffer))
                self._buffer.clear()
            self._queue.put_nowait(None)

    def _halt(self):
        self._halted.set()
        if self._job:
            self._job.cancel()

    def cancel(self):
        with self._lock:
            self._cancelled.set()
            self._accepting = False
            self._buffer.clear()
            self._halt()

    def join(self, timeout=None):
        self._worker.join(timeout)

    def _run(self):
        try:
            with tempfile.TemporaryDirectory(prefix='whisper-live-') as directory:
                path = Path(directory) / 'section.wav'
                path.touch(mode=0o600)
                while not self._halted.is_set():
                    try:
                        pcm = self._queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if pcm is None:
                        self._publish(done=True)
                        return
                    if len(pcm) % 2:
                        self._publish(error='invalid_audio', done=True)
                        return
                    with wave.open(str(path), 'wb') as audio:
                        audio.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
                        audio.writeframes(pcm)
                    finished = threading.Event()
                    outcome = []
                    def result(job, text, error):
                        outcome[:] = [text, error]
                        finished.set()
                    with self._lock:
                        if self._halted.is_set():
                            return
                        self._job = TranscriptionJob(path, self.config, lambda callback: callback(),
                                                      result, transcriber=self.transcriber)
                        self._job.start()
                    while not finished.wait(0.1):
                        if self._halted.is_set():
                            return
                    if outcome[1]:
                        self._publish(error=outcome[1], done=True)
                        return
                    if outcome[0]:
                        self._publish(text=outcome[0])
        except Exception:
            # Temporary files, resource exhaustion and unexpected errors never expose content.
            self._publish(error='local_service', done=True)
