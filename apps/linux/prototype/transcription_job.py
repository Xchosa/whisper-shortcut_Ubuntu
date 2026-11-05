"""One cancellable background request; terminal outcomes are published once."""
import threading
from transcription_client import REQUEST_TIMEOUT, TranscriptionError, transcribe


class TranscriptionJob:
    def __init__(self, path, config, dispatch, done, *, transcriber=None, timeout=REQUEST_TIMEOUT):
        self.path = path
        self.config = config
        self.dispatch = dispatch
        self.done = done
        self.transcriber = transcriber or transcribe
        self.timeout = timeout
        self.cancelled = threading.Event()
        self._lock = threading.Lock()
        self._terminal = False
        self._connection = None
        self._timer = None
        self._worker = None

    @staticmethod
    def _close(connection):
        if connection:
            try:
                connection.close()
            except Exception:
                pass

    def start(self):
        with self._lock:
            if self._terminal or self._worker is not None:
                return
            self._timer = threading.Timer(self.timeout, self._expire)
            self._timer.daemon = True
            self._worker = threading.Thread(target=self._run, daemon=True)
            timer, worker = self._timer, self._worker
        timer.start()
        worker.start()

    def join(self, timeout=None):
        if self._worker:
            self._worker.join(timeout)

    def cancel(self):
        with self._lock:
            self._terminal = True
            self.cancelled.set()
            connection, timer = self._connection, self._timer
        if timer:
            timer.cancel()
        self._close(connection)

    def _attach(self, connection):
        with self._lock:
            terminal = self._terminal
            if not terminal:
                self._connection = connection
        if terminal:
            self._close(connection)
            raise TranscriptionError("cancelled")

    def _finish(self, text, error, *, stop=False):
        with self._lock:
            if self._terminal:
                return
            self._terminal = True
            if stop:
                self.cancelled.set()
            connection, timer = self._connection, self._timer
        if timer:
            timer.cancel()
        if stop:
            self._close(connection)
        self.dispatch(lambda: self.done(self, text, error))

    def _expire(self):
        self._finish(None, "timeout", stop=True)

    def _run(self):
        if self.cancelled.is_set():
            return
        try:
            text = self.transcriber(self.path, self.config, self.cancelled, self._attach)
        except TranscriptionError as error:
            self._finish(None, error.code)
        except Exception:
            # Do not forward raw exceptions: HTTP libraries can include header values.
            self._finish(None, "network")
        else:
            self._finish(text, None)
