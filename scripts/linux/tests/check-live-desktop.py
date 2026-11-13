"""Opt-in GTK/GStreamer/local-container check with an explicitly provided test WAV.

Use a public/synthetic fixture, never a microphone. No audio or transcript is logged.
Usage: /usr/bin/python3 scripts/linux/tests/check-live-desktop.py /tmp/test.wav
"""
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

if len(sys.argv) != 2 or not Path(sys.argv[1]).is_file():
    raise SystemExit('Provide a public/synthetic WAV test fixture.')
fixture = str(Path(sys.argv[1]).resolve())
temporary = tempfile.TemporaryDirectory(prefix='whisper-live-desktop-')
os.environ['WHISPER_SHORTCUT_DATA_DIR'] = str(Path(temporary.name) / 'data')
os.environ['WHISPER_SHORTCUT_ENV_FILE'] = str(Path(temporary.name) / 'no-env')
os.environ['TRANSCRIPTION_PROVIDER'] = 'local'
os.environ['LOCAL_TRANSCRIPTION_URL'] = 'http://127.0.0.1:8765'
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'apps/linux/prototype'))
import desktop_demo as d
from history_store import HistoryStore

d.APP_ID += '.LiveValidation'
app = d.Demo()
app.find_sources = lambda: None
errors = []
edited = False
results = 0
recording_seen = False
heartbeats = 0
finished = False


def heartbeat():
    global heartbeats
    heartbeats += 1
    return not finished


def receive(session, text, error, done):
    global edited, results, recording_seen
    app.live.original_receive(session, text, error, done)
    if text:
        results += 1
        if not edited:
            recording_seen = app.state == 'recording'
            # Simulate correcting the first result, with the cursor inside that correction.
            app.transcript_buffer.set_text('USER CORRECTION')
            app.transcript_buffer.place_cursor(app.transcript_buffer.get_iter_at_offset(4))
            edited = True
    if done:
        d.GLib.timeout_add(300, verify)
    return False


def start():
    try:
        app.test_paintable = d.Gtk.WidgetPaintable.new(app.window)
        def source(_):
            source = d.Gst.ElementFactory.make('filesrc')
            source.set_property('location', fixture)
            parser = d.Gst.ElementFactory.make('wavparse')
            pacing = d.Gst.ElementFactory.make('identity')
            pacing.set_property('sync', True)
            container = d.Gst.Bin.new(None)
            for element in (source, parser, pacing):
                container.add(element)
            assert source.link(parser) and parser.link(pacing)
            container.add_pad(d.Gst.GhostPad.new('src', pacing.get_static_pad('src')))
            return container
        app.devices = [SimpleNamespace(create_element=source)]
        app.microphone.set_model(d.Gtk.StringList.new(['Synthetic fixture']))
        app.microphone.set_selected(0)
        app.live.original_receive = app.live.receive
        app.live.receive = receive
        app.start_capture('microphone')
        assert app.state == 'recording', app.status.get_text()
        d.GLib.timeout_add_seconds(10, stop)
    except Exception as error:
        fail(type(error).__name__ + ' at line ' + str(error.__traceback__.tb_lineno))
    return False


def stop():
    if app.state == 'recording':
        app.stop()
    return False


def fail(reason):
    global finished
    print('State:', app.state, 'results:', results, 'during_capture:', recording_seen, 'live_error:', app.live.error)
    errors.append(reason)
    finished = True
    app.release_pipeline()
    if app.live.active:
        app.live.cancel()
    print('Live desktop validation failed: ' + reason)
    app.quit()
    return False


def verify():
    global finished
    try:
        assert app.state == 'idle' and not app.live.active
        assert results >= 2 and recording_seen
        assert app.transcript_text.startswith('USER CORRECTION\n')
        assert app.transcript_buffer.get_iter_at_mark(app.transcript_buffer.get_insert()).get_offset() == 4
        assert heartbeats >= 20
        entry = app.history.get(app.entry_id)
        assert entry.status == 'completed' and entry.text == app.transcript_text
        assert not app.history.audio_path(entry.id).exists()
        reopened = HistoryStore(app.history.root)
        assert reopened.get(entry.id).text == app.transcript_text
        app.window.present()
        app.window.queue_draw()
        app.test_paintable = d.Gtk.WidgetPaintable.new(app.window)
        d.GLib.timeout_add(600, screenshot)
    except Exception as error:
        fail(type(error).__name__ + ' at line ' + str(error.__traceback__.tb_lineno))
    return False


def screenshot():
    global finished
    try:
        snapshot = d.Gtk.Snapshot()
        app.test_paintable.snapshot(snapshot, app.window.get_width(), app.window.get_height())
        node = snapshot.to_node()
        assert node is not None
        texture = app.window.get_renderer().render_texture(node, None)
        assert texture.save_to_png('/tmp/whisper-live-desktop.png')
        print('Live GTK/GStreamer/local model: text during capture, correction preserved, ordered append, cursor retained, Stop drain, audio cleanup and restart persistence passed.')
        finished = True
        app.quit()
    except Exception as error:
        fail(type(error).__name__ + ' at line ' + str(error.__traceback__.tb_lineno))
    return False


d.GLib.timeout_add(100, heartbeat)
d.GLib.timeout_add(1200, start)
d.GLib.timeout_add_seconds(45, lambda: fail('deadline') if not finished else False)
status = app.run(['live-validation'])
temporary.cleanup()
raise SystemExit(status or bool(errors))
