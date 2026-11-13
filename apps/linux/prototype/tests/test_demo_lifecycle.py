"""Exercise real demo methods without importing GI or opening desktop services."""
import ast
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from transcription_client import TranscriptionError
from history_store import HistoryStore, HistoryError
from capture_pipeline import capture_description


def demo_type():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "desktop_demo.py").read_text())
    original = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Demo")
    names = {"cancel", "delete_audio", "stop", "set_sources", "message",
             "do_command_line", "close_window", "transcribe_recording",
             "finish_transcription", "cancel_transcription", "copy_transcript", "delete_recording",
             "can_leave_text", "persist_status", "retry_save", "open_history",
             "export_transcript", "confirm_delete_history", "start_capture", "set_displayed_text"}
    # Execute these exact methods, isolating only GTK's inheritance/import boundary.
    original.bases = []
    original.body = [node for node in original.body if isinstance(node, ast.FunctionDef) and node.name in names]
    module = ast.Module(body=[original], type_ignores=[])
    namespace = {
        "_": lambda message: message,
        "Gtk": SimpleNamespace(StringList=SimpleNamespace(new=lambda names: names)),
        "Gst": SimpleNamespace(MessageType=SimpleNamespace(ERROR="error", EOS="eos")),
        "TranscriptionError": TranscriptionError,
        "HistoryError": HistoryError,
        "capture_description": capture_description,
    }
    exec(compile(module, "<real desktop demo methods>", "exec"), namespace)
    namespace["Demo"]._namespace = namespace
    return namespace["Demo"]


class DemoLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.demo = demo_type()()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.demo.history = HistoryStore(Path(self.directory.name) / "data")
        self.demo.entry_id = None
        self.demo.unsaved = None
        self.demo.refresh_history = lambda: None
        self.demo.confirm_delete_history = lambda entry_id: self.demo.history.delete(entry_id)
        self.demo.state = "idle"
        self.demo.pending_toggle = True
        self.demo.audio_path = None
        self.demo.transcription_task = None
        self.demo.transcript_text = ""
        self.demo.live = SimpleNamespace(active=False, replacing=False, checkpoint=lambda: True,
            discard_draft=lambda: None, exported=lambda snapshot: None)
        self.demo.live_checkbox = SimpleNamespace(get_active=lambda: False)
        self.displayed = []
        self.copied = []
        self.demo.transcript_buffer = SimpleNamespace(set_text=self.displayed.append)
        self.demo.devices = []
        self.demo.window = SimpleNamespace(set_visible=lambda visible: None,
            get_clipboard=lambda: SimpleNamespace(set=self.copied.append))
        self.demo.background = SimpleNamespace(get_active=lambda: True)
        self.demo.microphone = SimpleNamespace(set_model=lambda model: None)
        self.demo.release_pipeline = lambda: None
        self.demo.say = lambda message: None
        self.demo.activate = lambda: None
        self.started = []
        self.demo.start_capture = self.started.append
        self.device = SimpleNamespace(get_display_name=lambda: "Synthetic source")

    def test_cancel_revokes_capture_waiting_for_discovery(self):
        self.demo.cancel()
        self.demo.set_sources([self.device])
        self.assertEqual(self.started, [])

    def test_stop_revokes_capture_waiting_for_discovery(self):
        self.demo.stop()
        self.demo.set_sources([self.device])
        self.assertEqual(self.started, [])

    def test_close_revokes_capture_waiting_for_discovery(self):
        self.demo.close_window()
        self.demo.set_sources([self.device])
        self.assertEqual(self.started, [])

    def test_deferred_capture_is_not_consumed_during_another_operation(self):
        self.demo.state = "recording"
        self.demo.set_sources([self.device])
        self.assertEqual(self.started, [])

    def test_authorized_deferred_capture_is_consumed_once(self):
        self.demo.set_sources([self.device])
        self.demo.set_sources([self.device])
        self.assertEqual(self.started, ["microphone"])
        self.assertFalse(self.demo.pending_toggle)

    def test_repeated_shortcut_revokes_request_before_discovery(self):
        options = SimpleNamespace(contains=lambda key: key == "toggle-recording")
        command = SimpleNamespace(get_options_dict=lambda: options)
        self.demo.do_command_line(command)
        self.demo.set_sources([self.device])
        self.assertEqual(self.started, [])

    def test_playback_error_preserves_valid_audio_for_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "valid.wav"
            path.write_bytes(b"synthetic test content")
            self.demo.audio_path = path
            self.demo.state = "playing"
            self.demo.message(None, SimpleNamespace(type="error"))
            self.assertTrue(path.exists())
            self.assertEqual(self.demo.state, "idle")

    def test_capture_error_retains_managed_incomplete_audio(self):
        entry = self.recording()
        self.demo.state = "recording"
        self.demo.message(None, SimpleNamespace(type="error"))
        self.assertTrue(self.demo.audio_path.exists())
        self.assertEqual(self.demo.history.get(entry.id).status, "failed")
        self.assertEqual(self.demo.state, "idle")

    def test_cancel_transcription_preserves_recording_and_rejects_late_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "valid.wav"
            path.write_bytes(b"synthetic")
            self.demo.audio_path = path
            cancelled = []
            job = SimpleNamespace(cancel=lambda: cancelled.append(True))
            self.demo.transcription_task = job
            self.demo.state = "transcribing"
            self.demo.cancel()
            self.demo.finish_transcription(job, "late private text", None)
            self.assertTrue(path.exists())
            self.assertEqual(cancelled, [True])
            self.assertEqual(self.demo.state, "idle")
            self.assertEqual(self.displayed, [])
            self.assertEqual(self.copied, [])

    def test_stale_result_cannot_overwrite_new_job(self):
        current = object()
        self.demo.transcription_task = current
        self.demo.state = "transcribing"
        self.demo.finish_transcription(object(), "stale", None)
        self.assertIs(self.demo.transcription_task, current)
        self.assertEqual(self.demo.state, "transcribing")
        self.assertEqual(self.displayed, [])

    def test_success_displays_text_but_only_explicit_copy_changes_clipboard(self):
        self.recording()
        job = SimpleNamespace(config=SimpleNamespace(provider="local", model="base"))
        self.demo.transcription_task = job
        self.demo.state = "transcribing"
        self.demo.finish_transcription(job, "Recognized words.", None)
        self.assertEqual(self.demo.transcript_text, "Recognized words.")
        self.assertEqual(self.displayed, ["Recognized words."])
        self.assertEqual(self.copied, [])
        self.demo.copy_transcript()
        self.assertEqual(self.copied, ["Recognized words."])

    def test_transcription_errors_preserve_recording_for_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "valid.wav"
            path.write_bytes(b"synthetic")
            self.demo.audio_path = path
            job = object()
            self.demo.transcription_task = job
            self.demo.state = "transcribing"
            self.demo.finish_transcription(job, None, "local_unavailable")
            self.assertTrue(path.exists())
            self.assertEqual(self.demo.state, "idle")

    def test_recording_or_playback_blocks_transcription_before_loading_credentials(self):
        for state in ("recording", "stopping", "playing", "transcribing"):
            self.demo.state = state
            self.demo.transcribe_recording()
            self.assertEqual(self.demo.state, state)

    def test_close_while_transcribing_is_refused(self):
        self.demo.state = "transcribing"
        self.demo.background.get_active = lambda: (_ for _ in ()).throw(
            AssertionError("must not hide while transcribing"))
        self.assertTrue(self.demo.close_window())

    def test_cancel_when_idle_preserves_completed_recording(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "valid.wav"
            path.write_bytes(b"synthetic")
            self.demo.audio_path = path
            self.demo.cancel()
            self.assertTrue(path.exists())

    def test_deleting_recording_requires_idle_state(self):
        entry = self.recording()
        path = self.demo.audio_path
        self.demo.state = "transcribing"
        self.demo.delete_recording()
        self.assertTrue(path.exists())
        self.demo.state = "idle"
        self.demo.delete_recording()
        self.assertFalse(path.exists())
        self.assertIsNone(self.demo.history.get(entry.id))

    def recording(self):
        entry = self.demo.history.create_recording()
        self.demo.history.mark_ready(entry.id)
        self.demo.entry_id = entry.id
        self.demo.audio_path = self.demo.history.audio_path(entry.id)
        self.demo.audio_path.write_bytes(b"synthetic")
        return entry

    def test_success_is_saved_before_audio_is_removed(self):
        entry = self.recording()
        path = self.demo.audio_path
        job = SimpleNamespace(config=SimpleNamespace(provider="local", model="base"))
        self.demo.transcription_task = job
        self.demo.state = "transcribing"
        self.demo.finish_transcription(job, "Durable test text", None)
        self.assertEqual(self.demo.history.get(entry.id).text, "Durable test text")
        self.assertFalse(path.exists())
        self.assertIsNone(self.demo.unsaved)

    def test_storage_failure_preserves_result_and_blocks_switch_until_retry(self):
        entry = self.recording()
        job = SimpleNamespace(config=SimpleNamespace(provider="local", model="base"))
        self.demo.transcription_task = job
        self.demo.state = "transcribing"
        with patch.object(self.demo.history, "save_transcript", side_effect=HistoryError()):
            self.demo.finish_transcription(job, "Unsaved synthetic text", None)
        self.assertEqual(self.demo.transcript_text, "Unsaved synthetic text")
        self.assertTrue(self.demo.audio_path.exists())
        self.assertFalse(self.demo.can_leave_text())
        second = self.demo.history.create_recording()
        self.demo.open_history(second.id)
        self.assertEqual(self.demo.entry_id, entry.id)
        self.demo.retry_save()
        self.assertTrue(self.demo.can_leave_text())
        self.assertEqual(self.demo.history.get(entry.id).text, "Unsaved synthetic text")

    def test_open_retained_audio_and_saved_text_after_restart(self):
        failed = self.recording()
        failed_path = self.demo.audio_path
        self.demo.history.mark_failed(failed.id, "timeout")
        saved = self.recording()
        self.demo.history.save_transcript(saved.id, "Restart fixture", "local", "base")
        self.demo.history = HistoryStore(Path(self.directory.name) / "data")
        self.demo.open_history(saved.id)
        self.assertEqual(self.demo.transcript_text, "Restart fixture")
        self.assertIsNone(self.demo.audio_path)
        self.demo.open_history(failed.id)
        self.assertEqual(self.demo.audio_path, failed_path)
        self.assertTrue(failed_path.exists())

    def test_cancel_persists_retryable_status(self):
        entry = self.recording()
        self.demo.history.mark_transcribing(entry.id)
        self.demo.transcription_task = SimpleNamespace(cancel=lambda: None)
        self.demo.state = "transcribing"
        self.demo.cancel_transcription()
        self.assertEqual(self.demo.history.get(entry.id).status, "ready")
        self.assertTrue(self.demo.audio_path.exists())

    def test_eos_persists_finalized_capture(self):
        entry = self.recording()
        self.demo.state = "stopping"
        self.demo.pending_quit = False
        self.demo.message(None, SimpleNamespace(type="eos"))
        self.assertEqual(self.demo.history.get(entry.id).status, "ready")

    def test_new_capture_preserves_older_failed_recording(self):
        older = self.recording()
        path = self.demo.audio_path
        self.demo.history.mark_failed(older.id, "timeout")
        self.demo.devices = [self.device]
        self.demo.microphone.get_selected = lambda: 0
        # Missing Gst.parse_launch simulates setup failure after durable allocation.
        type(self.demo).start_capture(self.demo, "microphone")
        self.assertNotEqual(self.demo.entry_id, older.id)
        self.assertTrue(path.exists())
        self.assertEqual(self.demo.history.get(older.id).status, "failed")
        self.assertEqual(self.demo.history.get(self.demo.entry_id).status, "failed")

    def test_delete_confirmation_uses_original_id_and_rechecks_busy_state(self):
        first = self.recording()
        callbacks = []
        dialog = SimpleNamespace(choose=lambda window, cancellable, callback: callbacks.append(callback),
                                 choose_finish=lambda result: 1)
        self.demo._namespace["Gtk"].AlertDialog = lambda **kwargs: dialog
        self.demo._namespace["GLib"] = SimpleNamespace(Error=RuntimeError)
        type(self.demo).confirm_delete_history(self.demo, first.id)
        second = self.recording()
        callbacks.pop()(dialog, object())
        self.assertIsNone(self.demo.history.get(first.id))
        self.assertIsNotNone(self.demo.history.get(second.id))
        self.assertEqual(self.demo.entry_id, second.id)
        type(self.demo).confirm_delete_history(self.demo, second.id)
        self.demo.state = "recording"
        callbacks.pop()(dialog, object())
        self.assertIsNotNone(self.demo.history.get(second.id))

    def test_export_uses_snapshot_and_failure_keeps_unsaved_guard(self):
        self.recording()
        self.demo.transcript_text = "original snapshot"
        self.demo.unsaved = (self.demo.entry_id, "original snapshot", "local", "base")
        callbacks = []
        target = Path(self.directory.name) / "export.txt"
        dialog = SimpleNamespace(save=lambda window, cancellable, callback: callbacks.append(callback),
            save_finish=lambda result: SimpleNamespace(get_path=lambda: str(target)))
        namespace = self.demo._namespace
        namespace["Gtk"].FileDialog = lambda **kwargs: dialog
        namespace["Path"] = Path
        namespace["GLib"] = SimpleNamespace(Error=RuntimeError, idle_add=lambda callback,*args: callback(*args))
        namespace["threading"] = SimpleNamespace(Thread=lambda target,daemon: SimpleNamespace(start=target))
        from history_store import export_text
        namespace["export_text"] = export_text
        self.demo.export_transcript()
        self.demo.transcript_text = "later mutation"
        callbacks.pop()(dialog, object())
        self.assertEqual(target.read_text(), "original snapshot")
        self.assertIsNone(self.demo.unsaved)
        self.demo.unsaved = (self.demo.entry_id, "later mutation", "local", "base")
        namespace["export_text"] = lambda *args: (_ for _ in ()).throw(HistoryError("export"))
        self.demo.export_transcript()
        callbacks.pop()(dialog, object())
        self.assertFalse(self.demo.can_leave_text())
        self.assertEqual(target.read_text(), "original snapshot")
        self.assertEqual(self.demo.state, "idle")

    def test_cancel_cannot_unlock_an_export_in_progress(self):
        self.demo.state = "exporting"
        self.demo.cancel()
        self.assertEqual(self.demo.state, "exporting")

    def test_export_cannot_replace_its_own_database(self):
        self.recording()
        self.demo.transcript_text = "synthetic export"
        original = self.demo.history.database.read_bytes()
        callbacks = []
        dialog = SimpleNamespace(save=lambda window, cancellable, callback: callbacks.append(callback),
            save_finish=lambda result: SimpleNamespace(get_path=lambda: str(self.demo.history.database)))
        namespace = self.demo._namespace
        namespace["Gtk"].FileDialog = lambda **kwargs: dialog
        namespace["Path"] = Path
        namespace["GLib"] = SimpleNamespace(Error=RuntimeError, idle_add=lambda callback,*args: callback(*args))
        namespace["threading"] = SimpleNamespace(Thread=lambda target,daemon: SimpleNamespace(start=target))
        from history_store import export_text
        namespace["export_text"] = export_text
        self.demo.export_transcript()
        callbacks.pop()(dialog, object())
        self.assertEqual(self.demo.history.database.read_bytes(), original)
        self.assertEqual(self.demo.state, "idle")

    def test_failed_capture_cancel_does_not_claim_deletion_succeeded(self):
        entry = self.recording()
        path = self.demo.audio_path
        messages = []
        self.demo.say = messages.append
        self.demo.state = "recording"
        with patch.object(self.demo.history, "discard_recording", side_effect=HistoryError()):
            self.demo.cancel()
        self.assertTrue(path.exists())
        self.assertIsNotNone(self.demo.history.get(entry.id))
        self.assertIn("storage", messages[-1].lower())

    def test_failed_finalization_metadata_does_not_claim_save_succeeded(self):
        self.recording()
        messages = []
        self.demo.say = messages.append
        self.demo.state = "stopping"
        self.demo.pending_quit = False
        with patch.object(self.demo.history, "mark_ready", side_effect=HistoryError()):
            self.demo.message(None, SimpleNamespace(type="eos"))
        self.assertIn("storage", messages[-1].lower())

    def test_batch_completion_does_not_replace_text_typed_while_waiting(self):
        entry = self.recording()
        current = ['typed correction']
        self.demo.transcript_text = current[0]
        self.demo.transcript_buffer = SimpleNamespace(
            get_end_iter=lambda: len(current[0]),
            insert=lambda end,text: current.__setitem__(0, current[0][:end] + text + current[0][end:]),
            set_text=lambda text: current.__setitem__(0, text))
        job = SimpleNamespace(config=SimpleNamespace(provider='local', model='base'))
        self.demo.transcription_task = job
        self.demo.state = 'transcribing'
        self.demo.finish_transcription(job, 'recognized words', None)
        self.assertEqual(current[0], 'typed correction\nrecognized words')
        self.assertEqual(self.demo.history.get(entry.id).text, current[0])

    def test_cancel_manual_capture_preserves_typed_draft_and_does_not_lock_ui(self):
        from live_controller import LiveController
        from test_live_controller import Buffer
        entry = self.recording()
        self.demo.state = 'recording'
        self.demo.live = LiveController(self.demo, lambda callback: callback(), lambda ms,callback: 1)
        self.demo.transcript_buffer = Buffer()
        self.demo.transcript_buffer.changed = self.demo.live.changed
        self.demo.transcript_buffer.text = 'typed manual draft'
        self.demo.live.changed(self.demo.transcript_buffer)
        self.demo.cancel()
        self.assertIsNotNone(self.demo.history.get(entry.id))
        self.assertEqual(self.demo.history.get(entry.id).text, 'typed manual draft')
        self.assertTrue(self.demo.can_leave_text())

    def test_stop_during_live_drain_cancels_live_session_and_ignores_late_output(self):
        from live_controller import LiveController
        entry = self.recording()
        self.demo.live = LiveController(self.demo, lambda callback: callback(), lambda ms,callback: 1)
        cancelled = []
        session = SimpleNamespace(cancel=lambda: cancelled.append(True))
        self.demo.live.session = session
        self.demo.state = 'transcribing'
        self.demo.stop()
        self.demo.live.receive(session, 'late output', None, True)
        self.assertEqual(cancelled, [True])
        self.assertEqual(self.demo.state, 'idle')
        self.assertEqual(self.demo.transcript_text, '')
        self.assertTrue(self.demo.history.audio_path(entry.id).exists())
