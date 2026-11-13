"""Real live editor controller with a small GTK buffer boundary fake."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_controller import LiveController
from history_store import HistoryStore, HistoryError
from transcription_config import LocalTranscriptionConfig


class Buffer:
    def __init__(self):
        self.text = ''
        self.insertions = []
    def set_text(self, text):
        self.text = text
        self.changed(self)
    def get_bounds(self):
        return 0, len(self.text)
    def get_text(self, start, end, hidden):
        return self.text[start:end]
    def get_end_iter(self):
        return len(self.text)
    def insert(self, end, text):
        self.insertions.append((end, text))
        self.text = self.text[:end] + text + self.text[end:]
        self.changed(self)


class LiveControllerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        store = HistoryStore(Path(temporary.name))
        entry = store.create_recording()
        self.messages = []
        self.app = SimpleNamespace(history=store, entry_id=entry.id, transcript_text='',
            transcript_buffer=Buffer(), state='recording', unsaved=None,
            say=self.messages.append, refresh_history=lambda: None,
            persist_status=lambda method,*args: getattr(store,method)(entry.id,*args),
            retry_save=lambda: store.save_transcript(*self.app.unsaved))
        self.controller = LiveController(self.app, lambda callback: callback(), lambda ms,callback: 1)
        self.app.transcript_buffer.changed = self.controller.changed
        self.session = SimpleNamespace(config=LocalTranscriptionConfig(), finish=lambda: None, cancel=lambda: None)
        self.controller.session = self.session

    def test_append_keeps_user_corrections_and_uses_end_insertion(self):
        self.controller.receive(self.session, 'first phrase', None, False)
        self.app.transcript_buffer.text = 'corrected phrase'
        self.controller.changed(self.app.transcript_buffer)
        self.controller.receive(self.session, 'new words', None, False)
        self.assertEqual(self.app.transcript_text, 'corrected phrase\nnew words')
        self.assertEqual(self.app.transcript_buffer.insertions[-1], (16, '\nnew words'))
        self.assertTrue(self.controller.checkpoint())
        self.assertEqual(self.app.history.get(self.app.entry_id).text, self.app.transcript_text)
        self.assertTrue(self.app.history.audio_path(self.app.entry_id).exists())

    def test_stale_session_cannot_change_edited_text(self):
        self.controller.receive(object(), 'stale', None, False)
        self.assertEqual(self.app.transcript_text, '')

    def test_storage_failure_retains_dirty_edits_for_retry(self):
        self.app.transcript_buffer.text = 'unsaved correction'
        self.controller.changed(self.app.transcript_buffer)
        with patch.object(self.app.history, 'update_text', side_effect=HistoryError()):
            self.assertFalse(self.controller.checkpoint())
        self.assertTrue(self.controller.dirty)
        self.assertTrue(self.controller.checkpoint())
        self.assertFalse(self.controller.dirty)

    def test_stop_saves_current_edited_buffer_and_then_removes_audio(self):
        self.controller.receive(self.session, 'original', None, False)
        self.app.transcript_buffer.text = 'user correction'
        self.controller.changed(self.app.transcript_buffer)
        self.controller.capture_stopped()
        self.controller.receive(self.session, None, None, True)
        self.assertEqual(self.app.history.get(self.app.entry_id).text, 'user correction')
        self.assertFalse(self.app.history.audio_path(self.app.entry_id).exists())
        self.assertEqual(self.app.state, 'idle')

    def test_live_error_and_cancel_preserve_partial_text_and_audio(self):
        self.controller.receive(self.session, 'partial draft', None, False)
        self.controller.receive(self.session, None, 'local_unavailable', True)
        self.assertEqual(self.app.state, 'recording')
        self.controller.capture_stopped()
        self.assertEqual(self.app.state, 'idle')
        self.assertEqual(self.app.history.get(self.app.entry_id).text, 'partial draft')
        self.assertTrue(self.app.history.audio_path(self.app.entry_id).exists())

    def test_cancel_invalidates_session_before_late_delivery(self):
        self.controller.receive(self.session, 'kept correction', None, False)
        self.controller.cancel()
        self.controller.receive(self.session, 'late result', None, True)
        self.assertEqual(self.app.transcript_text, 'kept correction')
        self.assertEqual(self.app.history.get(self.app.entry_id).text, 'kept correction')
        self.assertTrue(self.app.history.audio_path(self.app.entry_id).exists())

    def test_fresh_editor_tracks_text_and_creates_durable_manual_history(self):
        self.app.entry_id = None
        self.app.transcript_buffer.text = 'typed before recording'
        self.controller.changed(self.app.transcript_buffer)
        self.assertEqual(self.app.transcript_text, 'typed before recording')
        self.assertTrue(self.controller.dirty)
        self.assertTrue(self.controller.checkpoint())
        entry = self.app.history.get(self.app.entry_id)
        self.assertEqual(entry.text, 'typed before recording')
        self.assertEqual(entry.status, 'completed')
        self.assertFalse(self.app.history.audio_path(entry.id).exists())
