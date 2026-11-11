"""Opt-in real GTK integration check using isolated synthetic history only."""
import os
import sys
import tempfile
from pathlib import Path
temporary = tempfile.TemporaryDirectory(prefix='whisper-history-gtk-')
root = Path(temporary.name)
os.environ['WHISPER_SHORTCUT_DATA_DIR'] = str(root / 'data')
os.environ['WHISPER_SHORTCUT_ENV_FILE'] = str(root / 'no-env')
os.environ['TRANSCRIPTION_PROVIDER'] = 'local'
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'apps/linux/prototype'))
import desktop_demo as d
from history_store import HistoryStore, export_text
store = HistoryStore()
a = store.create_recording()
store.mark_ready(a.id)
store.save_transcript(a.id, 'Synthetic history fixture – Grüße', 'local', 'base')
b = store.create_recording()
store.audio_path(b.id).write_bytes(b'synthetic retained clip')
store.mark_failed(b.id, 'timeout')
d.APP_ID += '.HistoryValidation'
app = d.Demo()
app.find_sources = lambda: None
errors = []

def check():
    try:
        app.test_paintable = d.Gtk.WidgetPaintable.new(app.window)
        assert app.history is not None
        assert app.entry_id == b.id
        assert app.state == 'idle' and app.pipeline is None
        app.open_history(a.id)
        assert app.transcript_text == 'Synthetic history fixture – Grüße'
        assert app.audio_path is None
        export_text(app.transcript_text, root / 'export.txt')
        assert (root / 'export.txt').read_text() == app.transcript_text
        app.open_history(b.id)
        assert app.audio_path.exists()
        d.Gtk.FileDialog(title='test', initial_name='transcript.txt')
        d.Gtk.AlertDialog(message='test', buttons=['Keep', 'Delete'], default_button=0, cancel_button=0)
        app.open_history(a.id)
        app.history.delete(a.id)
        assert app.history.get(a.id) is None
        assert app.history.audio_path(b.id).exists()
        print('GTK history: startup restore, open text/audio, UTF-8 export, targeted delete and native dialog construction passed.')
    except Exception as e:
        errors.append(type(e).__name__)
        print('GTK validation failed: ' + type(e).__name__)
    finally:
        d.GLib.timeout_add(600, screenshot)
    return False
attempts = 0

def screenshot():
    global attempts
    attempts += 1
    try:
        snapshot = d.Gtk.Snapshot()
        app.test_paintable.snapshot(snapshot, app.window.get_width(), app.window.get_height())
        node = snapshot.to_node()
        if node is None and attempts < 10:
            app.window.queue_draw()
            return True
        if node is None:
            raise RuntimeError('No rendered node')
        texture = app.window.get_renderer().render_texture(node, None)
        assert texture.save_to_png('/tmp/whisper-history-desktop.png')
        print('GTK window rendered; main-loop timer fired; no recording started.')
    except Exception as error:
        errors.append(type(error).__name__)
        print('GTK screenshot failed: ' + type(error).__name__)
    app.quit()
    return False
d.GLib.timeout_add(1800, check)
status = app.run(['history-validation'])
temporary.cleanup()
raise SystemExit(status or app.exit_code or bool(errors))
