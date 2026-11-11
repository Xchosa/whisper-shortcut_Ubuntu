import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from history_store import HistoryError, HistoryStore, export_text


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "history"
        self.store = HistoryStore(self.root)

    def ready(self, data=b"synthetic test audio"):
        entry = self.store.create_recording()
        self.store.audio_path(entry.id).write_bytes(data)
        self.store.mark_ready(entry.id)
        return entry

    def test_transcript_survives_reopen_and_audio_is_removed_after_save(self):
        entry = self.ready()
        cleaned = self.store.save_transcript(entry.id, "Usable German: Grüße!", "local", "base")
        self.assertTrue(cleaned)
        reopened = HistoryStore(self.root)
        saved = reopened.get(entry.id)
        self.assertEqual(saved.text, "Usable German: Grüße!")
        self.assertEqual(saved.created_at, entry.created_at)
        self.assertEqual(saved.status, "completed")
        self.assertEqual((saved.provider, saved.model), ("local", "base"))
        self.assertFalse(reopened.audio_path(entry.id).exists())
        self.assertNotIn("Usable German", repr(saved))

    def test_failed_and_cancelled_audio_survives_restart_and_new_recording(self):
        first = self.ready()
        self.store.mark_transcribing(first.id)
        self.store.mark_failed(first.id, "local_unavailable")
        second = self.ready()
        self.store.mark_transcribing(second.id)
        self.store.mark_cancelled(second.id)
        reopened = HistoryStore(self.root)
        self.assertEqual(reopened.get(first.id).status, "failed")
        self.assertEqual(reopened.get(second.id).status, "ready")
        self.assertEqual(reopened.audio_path(first.id).read_bytes(), b"synthetic test audio")

    def test_interrupted_and_orphan_recordings_are_retained(self):
        entry = self.ready()
        self.store.mark_transcribing(entry.id)
        orphan_id = "a" * 32
        self.store.audio_path(orphan_id).write_bytes(b"orphan audio")
        reopened = HistoryStore(self.root)
        self.assertEqual(reopened.get(entry.id).status, "interrupted")
        self.assertEqual(reopened.get(orphan_id).status, "interrupted")
        self.assertTrue(reopened.audio_path(orphan_id).exists())

    def test_private_directories_and_files(self):
        entry = self.ready()
        for path in (self.root, self.root / "recordings"):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
        for path in (self.root / "history.sqlite3", self.store.audio_path(entry.id)):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_order_and_pagination_use_summaries_only(self):
        entries = [self.ready() for _ in range(4)]
        for entry in entries:
            self.store.save_transcript(entry.id, "x" * 1000, "local", "base")
        page = self.store.list_entries(limit=2, offset=0)
        self.assertEqual([x.id for x in page], [entries[3].id, entries[2].id])
        self.assertLessEqual(len(page[0].preview), 120)
        self.assertEqual(len(self.store.list_entries(limit=2, offset=2)), 2)

    def test_sql_like_text_is_saved_as_data(self):
        entry = self.ready()
        text = "'); DROP TABLE entries; --"
        self.store.save_transcript(entry.id, text, "local", "base")
        self.assertEqual(self.store.get(entry.id).text, text)
        self.assertEqual(len(self.store.list_entries()), 1)

    def test_unknown_schema_is_not_modified(self):
        path = self.root / "history.sqlite3"
        with sqlite3.connect(path) as db:
            db.execute("PRAGMA user_version=99")
        before = path.read_bytes()
        with self.assertRaises(HistoryError):
            HistoryStore(self.root)
        self.assertEqual(path.read_bytes(), before)

    def test_database_write_failure_never_deletes_audio(self):
        entry = self.ready()
        with patch("history_store.sqlite3.connect", side_effect=sqlite3.OperationalError("private text")):
            with self.assertRaises(HistoryError) as error:
                self.store.save_transcript(entry.id, "keep me", "local", "base")
        self.assertTrue(self.store.audio_path(entry.id).exists())
        self.assertNotIn("private text", str(error.exception))

    def test_cleanup_failure_does_not_rollback_saved_transcript(self):
        entry = self.ready()
        with patch.object(Path, "unlink", side_effect=PermissionError):
            self.assertFalse(self.store.save_transcript(entry.id, "saved", "local", "base"))
        self.assertEqual(self.store.get(entry.id).text, "saved")
        self.assertTrue(self.store.audio_path(entry.id).exists())
        HistoryStore(self.root)
        self.assertFalse(self.store.audio_path(entry.id).exists())

    def test_delete_failure_preserves_entry_and_delete_is_targeted(self):
        first, second = self.ready(), self.ready()
        with patch.object(Path, "unlink", side_effect=PermissionError):
            with self.assertRaises(HistoryError):
                self.store.delete(first.id)
        self.assertIsNotNone(self.store.get(first.id))
        self.store.delete(first.id)
        self.assertIsNone(self.store.get(first.id))
        self.assertTrue(self.store.audio_path(second.id).exists())

    def test_active_recording_needs_explicit_discard(self):
        entry = self.store.create_recording()
        with self.assertRaises(HistoryError):
            self.store.delete(entry.id)
        self.store.discard_recording(entry.id)
        self.assertIsNone(self.store.get(entry.id))

    def test_rejects_traversal_and_symlinked_audio(self):
        with self.assertRaises(HistoryError):
            self.store.audio_path("../outside")
        entry = self.ready()
        outside = Path(self.directory.name) / "outside"
        outside.write_bytes(b"unrelated")
        path = self.store.audio_path(entry.id)
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaises(HistoryError):
            self.store.delete(entry.id)
        self.assertEqual(outside.read_bytes(), b"unrelated")

    def test_xdg_path_and_relative_override_are_safe(self):
        with patch.dict(os.environ, {"XDG_DATA_HOME": self.directory.name}, clear=True):
            self.assertEqual(HistoryStore().root, Path(self.directory.name) / "whispershortcut")
        with patch.dict(os.environ, {"WHISPER_SHORTCUT_DATA_DIR": "relative"}, clear=True):
            with self.assertRaises(HistoryError):
                HistoryStore()

    def test_export_is_utf8_and_preserves_existing_file_on_failure(self):
        target = Path(self.directory.name) / "export.txt"
        target.write_text("old")
        with patch("history_store.os.replace", side_effect=OSError):
            with self.assertRaises(HistoryError):
                export_text("new Grüße", target)
        self.assertEqual(target.read_text(), "old")
        export_text("new Grüße", target)
        self.assertEqual(target.read_text(encoding="utf-8"), "new Grüße")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)


class LockedStoreTests(unittest.TestCase):
    def test_real_database_lock_retains_audio_and_returns_fixed_error(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "private")
            entry = store.create_recording()
            path = store.audio_path(entry.id)
            path.write_bytes(b"synthetic")
            lock = sqlite3.connect(store.database)
            try:
                lock.execute("BEGIN IMMEDIATE")
                with self.assertRaises(HistoryError) as caught:
                    store.save_transcript(entry.id, "synthetic text", "local", "base")
                self.assertEqual(caught.exception.code, "storage")
                self.assertTrue(path.exists())
            finally:
                lock.rollback()
                lock.close()
            store.save_transcript(entry.id, "synthetic text", "local", "base")
            self.assertFalse(path.exists())
