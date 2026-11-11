"""Private, versioned transcript metadata and retained recording ownership."""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import uuid

SCHEMA_VERSION = 1
MAX_TEXT_BYTES = 1024 * 1024


class HistoryError(Exception):
    MESSAGES = {
        "storage": "History storage is unavailable. Your existing data has not been replaced.",
        "schema": "This history database needs a newer app version. It has not been changed.",
        "entry": "The selected history entry is unavailable.",
        "busy": "Stop or cancel the active operation before changing history.",
        "export": "The text export failed. Your transcript remains available.",
    }

    def __init__(self, code="storage"):
        self.code = code
        super().__init__(self.MESSAGES.get(code, self.MESSAGES["storage"]))


@dataclass(frozen=True)
class Entry:
    id: str
    created_at: str
    status: str
    text: str = field(repr=False)
    provider: str
    model: str
    last_error: str


@dataclass(frozen=True)
class Summary:
    id: str
    created_at: str
    status: str
    preview: str = field(repr=False)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class HistoryStore:
    def __init__(self, root=None):
        if root is None:
            override = os.environ.get("WHISPER_SHORTCUT_DATA_DIR")
            if override:
                root = Path(override)
                if not root.is_absolute():
                    raise HistoryError()
            else:
                base = Path(os.environ.get("XDG_DATA_HOME", ""))
                if not base.is_absolute():
                    base = Path.home() / ".local/share"
                root = base / "whispershortcut"
        self.root = Path(root)
        self.recordings = self.root / "recordings"
        self.database = self.root / "history.sqlite3"
        try:
            for directory in (self.root, self.recordings):
                if directory.is_symlink():
                    raise HistoryError()
                directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                directory.chmod(0o700)
            if self.database.is_symlink():
                raise HistoryError()
            descriptor = os.open(self.database, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            os.close(descriptor)
            self.database.chmod(0o600)
            self._initialize()
            self._recover()
        except OSError:
            raise HistoryError() from None

    @contextmanager
    def _connection(self):
        connection = None
        try:
            if self.database.is_symlink():
                raise HistoryError()
            connection = sqlite3.connect(self.database, timeout=0.1)
            connection.row_factory = sqlite3.Row
            with connection:
                yield connection
        except (sqlite3.Error, OSError):
            raise HistoryError() from None
        finally:
            if connection is not None:
                connection.close()

    def _initialize(self):
        with self._connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version == SCHEMA_VERSION:
                return
            if version != 0 or db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                raise HistoryError("schema")
            db.execute("""CREATE TABLE entries (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN
                    ('recording','ready','transcribing','completed','failed','interrupted')),
                transcript TEXT NOT NULL DEFAULT '', provider TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '', last_error TEXT NOT NULL DEFAULT ''
            )""")
            db.execute("PRAGMA user_version=1")

    def audio_path(self, entry_id):
        if not isinstance(entry_id, str) or not re.fullmatch(r"[0-9a-f]{32}", entry_id):
            raise HistoryError("entry")
        path = self.recordings / (entry_id + ".wav")
        if self.recordings.is_symlink() or path.is_symlink():
            raise HistoryError()
        return path

    def _recover(self):
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""UPDATE entries SET status='interrupted', updated_at=?
                          WHERE status IN ('recording','transcribing')""", (now(),))
            for path in self.recordings.glob("*.wav"):
                entry_id = path.stem
                if path.is_symlink() or not re.fullmatch(r"[0-9a-f]{32}", entry_id):
                    continue
                row = db.execute("SELECT status FROM entries WHERE id=?", (entry_id,)).fetchone()
                if row is None:
                    created = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
                    db.execute("INSERT INTO entries(id,created_at,updated_at,status) VALUES(?,?,?,'interrupted')",
                               (entry_id, created, now()))
                elif row["status"] == "completed":
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass  # Text is safe; explicit deletion/startup can retry audio cleanup.

    def create_recording(self):
        entry_id = uuid.uuid4().hex
        path = self.audio_path(entry_id)
        created = False
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            created = True
            os.close(descriptor)
            with self._connection() as db:
                stamp = now()
                db.execute("INSERT INTO entries(id,created_at,updated_at,status) VALUES(?,?,?,'recording')",
                           (entry_id, stamp, stamp))
            return self.get(entry_id)
        except (OSError, HistoryError):
            if created:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise HistoryError() from None

    def get(self, entry_id):
        self.audio_path(entry_id)  # Validate identity and filesystem ownership.
        with self._connection() as db:
            row = db.execute("""SELECT id,created_at,status,transcript,provider,model,last_error
                                FROM entries WHERE id=?""", (entry_id,)).fetchone()
        return Entry(*row) if row else None

    def list_entries(self, limit=100, offset=0):
        if not 1 <= limit <= 100 or offset < 0:
            raise HistoryError()
        with self._connection() as db:
            rows = db.execute("""SELECT id,created_at,status,substr(transcript,1,120)
                                 FROM entries ORDER BY created_at DESC,rowid DESC LIMIT ? OFFSET ?""",
                              (limit, offset)).fetchall()
        return [Summary(*row) for row in rows]

    def _status(self, entry_id, status, error=""):
        self.audio_path(entry_id)
        with self._connection() as db:
            changed = db.execute("""UPDATE entries SET status=?,last_error=?,updated_at=?
                                    WHERE id=? AND status!='completed'""",
                                 (status, error, now(), entry_id)).rowcount
            if not changed:
                raise HistoryError("entry")

    def mark_ready(self, entry_id):
        self._status(entry_id, "ready")

    def mark_transcribing(self, entry_id):
        self._status(entry_id, "transcribing")

    def mark_failed(self, entry_id, code):
        if not re.fullmatch(r"[a-z_]{1,40}", code):
            raise HistoryError()
        self._status(entry_id, "failed", code)

    def mark_cancelled(self, entry_id):
        self._status(entry_id, "ready")

    def save_transcript(self, entry_id, text, provider, model):
        path = self.audio_path(entry_id)
        if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise HistoryError()
        with self._connection() as db:
            changed = db.execute("""UPDATE entries SET status='completed',transcript=?,
                provider=?,model=?,last_error='',updated_at=? WHERE id=? AND status!='completed'""",
                (text, provider, model, now(), entry_id)).rowcount
            if not changed:
                raise HistoryError("entry")
        # Never unlink before the successful transaction exits/commits.
        try:
            path.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def _remove(self, entry_id, allow_active):
        path = self.audio_path(entry_id)
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")  # Acquire write ownership before filesystem mutation.
            row = db.execute("SELECT status FROM entries WHERE id=?", (entry_id,)).fetchone()
            if row is None:
                raise HistoryError("entry")
            if not allow_active and row["status"] in {"recording", "transcribing"}:
                raise HistoryError("busy")
            path.unlink(missing_ok=True)
            db.execute("DELETE FROM entries WHERE id=?", (entry_id,))

    def delete(self, entry_id):
        self._remove(entry_id, allow_active=False)

    def discard_recording(self, entry_id):
        self._remove(entry_id, allow_active=True)


def export_text(text, path):
    path = Path(path)
    temporary = None
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=".whisper-export-", dir=path.parent)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError:
        raise HistoryError("export") from None
    finally:
        if temporary is not None:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass
