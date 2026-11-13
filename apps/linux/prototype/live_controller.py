"""Main-loop editor/history lifecycle. Audio work lives in LiveSession."""
from history_store import HistoryError
from live_session import LiveSession
from transcription_client import TranscriptionError


class LiveController:
    def __init__(self, app, dispatch, schedule):
        self.app, self.dispatch, self.schedule = app, dispatch, schedule
        self.session = None
        self.error = None
        self.done = False
        self.replacing = False
        self.dirty = False
        self._dirty_id = None
        self._scheduled = False

    @property
    def active(self):
        return self.session is not None

    def start(self, config):
        self.error, self.done = None, False
        self.session = LiveSession(config, self.dispatch, self.receive)
        return self.session

    def changed(self, buffer):
        if self.replacing:
            return
        self.app.transcript_text = buffer.get_text(*buffer.get_bounds(), True)
        if self.app.unsaved:
            entry_id, _, provider, model = self.app.unsaved
            self.app.unsaved = (entry_id, self.app.transcript_text, provider, model)
        self.dirty = True
        self._dirty_id = self.app.entry_id
        if not self._scheduled:
            self._scheduled = True
            self.schedule(500, self._checkpoint_timer)

    def _checkpoint_timer(self):
        self._scheduled = False
        self.checkpoint()
        return False

    def checkpoint(self):
        if not self.dirty:
            return True
        try:
            if self._dirty_id != self.app.entry_id:
                raise HistoryError('entry')
            if not self.app.history:
                raise HistoryError()
            if self._dirty_id is None:
                entry = self.app.history.create_text(self.app.transcript_text)
                self.app.entry_id = entry.id
                self._dirty_id = entry.id
                self.app.refresh_history()
            else:
                self.app.history.update_text(self._dirty_id, self.app.transcript_text)
            self.dirty = False
            return True
        except HistoryError as error:
            self.app.say(str(error))
            return False

    def discard_draft(self):
        self.dirty = False
        self._dirty_id = None

    def exported(self, snapshot):
        if self.app.transcript_text == snapshot:
            self.discard_draft()  # Explicit durable export can replace a failed history save.

    def receive(self, session, text, error, done):
        if self.session is not session:
            return
        if text:
            buffer = self.app.transcript_buffer
            separator = '\n' if self.app.transcript_text and not self.app.transcript_text.endswith('\n') else ''
            buffer.insert(buffer.get_end_iter(), separator + text)
        if error:
            self.error = error
            self.app.say(TranscriptionError(error).message)
        if done:
            self.done = True
            if self.app.state == 'transcribing':
                self._complete()
        return False

    def capture_stopped(self):
        self.app.state = 'transcribing'
        self.app.say('Finishing live transcription… You can keep editing.')
        if self.done:
            self._complete()
        else:
            self.session.finish()

    def _complete(self):
        config = self.session.config
        self.session = None
        self.app.state = 'idle'
        self.checkpoint()
        if self.error:
            self.app.persist_status('mark_failed', self.error)
            self.app.say(TranscriptionError(self.error).message)
        elif self.app.transcript_text.strip():
            self.app.unsaved = (self.app.entry_id, self.app.transcript_text, config.provider, config.model)
            self.app.retry_save()
        else:
            self.app.persist_status('mark_ready')
            self.app.say('No speech detected. Your recording is kept.')
        self.app.refresh_history()

    def cancel(self):
        session = self.session
        self.session = None  # Invalidate callbacks before closing a request.
        if session:
            session.cancel()
        self.app.state = 'idle'
        self.checkpoint()
        self.app.persist_status('mark_failed', 'cancelled')
        self.app.say('Live transcription cancelled. Edited text and recording are kept.')
