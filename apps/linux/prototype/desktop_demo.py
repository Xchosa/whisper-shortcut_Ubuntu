"""Disposable desktop demo: all capture, playback and keyring tests are opt-in."""
import ast
import locale
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import uuid

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Gst", "1.0")
gi.require_version("Secret", "1")
# Load Gsk explicitly so PyGObject can marshal snapshot node subclasses.
from gi.repository import Gdk, Gio, GLib, Gsk, Gst, Gtk, Secret
from transcription_config import ConfigError, load_config
from transcription_client import TranscriptionError
from transcription_job import TranscriptionJob

Gst.init(None)
APP_ID = "io.github.Xchosa.WhisperShortcut.Prototype"


def translate(message):
    """Prototype-only singular PO reader; production uses compiled gettext."""
    return TRANSLATIONS.get(message, message)


def translations():
    if not os.environ.get("LANGUAGE", locale.getlocale()[0] or "").startswith("de"):
        return {}
    catalog = {}
    key = None
    for line in (Path(__file__).parent / "po/de.po").read_text().splitlines():
        if line.startswith("msgid "):
            key = ast.literal_eval(line[6:])
        elif line.startswith("msgstr ") and key:
            catalog[key] = ast.literal_eval(line[7:])
    return catalog


TRANSLATIONS = translations()
_ = translate


class Demo(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.add_main_option("toggle-recording", 0, GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, "Activate the recording action", None)
        self.add_main_option("smoke-test", 0, GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, "Check window rendering without capture", None)
        self.window = None
        self.pipeline = None
        self.bus = None
        self.bus_handler = None
        self.state = "idle"
        self.stop_timeout = None
        self.audio_path = None
        self.started_at = None
        self.devices = []
        self.background_held = False
        self.scratch = tempfile.TemporaryDirectory(prefix="whisper-prototype-")
        self.smoke = False
        self.exit_code = 0
        self.keyring_cancel = None
        self.pending_quit = False
        self.pending_toggle = False
        self.transcription_task = None
        self.transcript_text = ""
        self.visible_provider = "local"

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()
        smoke = options.contains("smoke-test")
        if smoke and self.window is not None:
            command_line.set_exit_status(2)
            return 2
        self.smoke = smoke
        self.activate()
        if options.contains("toggle-recording"):
            if self.state == "recording":
                self.stop()
            elif self.state == "idle":
                if self.devices:
                    self.start_capture("microphone")
                else:
                    self.pending_toggle = not self.pending_toggle
        return 0

    def do_activate(self):
        if self.window:
            self.window.present()
            return
        self.window = Gtk.ApplicationWindow(application=self, title=_("WhisperShortcut — Transcription prototype"))
        self.window.set_default_size(700, 820)
        self.window.connect("close-request", self.close_window)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_top=20, margin_bottom=20, margin_start=20, margin_end=20)
        page = Gtk.ScrolledWindow()
        page.set_child(box)
        self.window.set_child(page)
        warning = Gtk.Label(label=_("Transcription uses the local container by default. OpenRouter requires explicit cloud configuration. Nothing is transcribed until you click Transcribe."),
                            wrap=True, xalign=0)
        box.append(warning)
        self.status = Gtk.Label(label=_("Idle"), wrap=True, xalign=0)
        box.append(self.status)
        box.append(Gtk.Label(label=_("Transcript"), xalign=0))
        transcript = Gtk.TextView(editable=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        transcript.set_tooltip_text(_("Transcript history is not saved. Copy your text before quitting."))
        self.transcript_buffer = transcript.get_buffer()
        transcript_scroll = Gtk.ScrolledWindow(min_content_height=140)
        transcript_scroll.set_child(transcript)
        box.append(transcript_scroll)
        self.microphone = Gtk.DropDown.new_from_strings([_("Finding audio sources…")])
        self.microphone.set_tooltip_text(_("Microphone source"))
        box.append(self.microphone)
        # A monitor source is intentionally explicit; no silent mic-only fallback.
        self.monitor = Gtk.Entry(placeholder_text=_("System monitor source (default: @DEFAULT_MONITOR@)"))
        self.monitor.set_text("@DEFAULT_MONITOR@")
        box.append(self.monitor)
        for label, callback in [
            ("Record microphone", lambda *_: self.start_capture("microphone")),
            ("Record system audio", lambda *_: self.start_capture("system")),
            ("Record microphone + system audio", lambda *_: self.start_capture("combined")),
            ("Stop and finalize", lambda *_: self.stop()),
            ("Cancel operation", lambda *_: self.cancel()),
            ("Play last recording", lambda *_: self.play()),
            ("Delete recording", lambda *_: self.delete_recording()),
            ("Transcribe recording", lambda *_: self.transcribe_recording()),
            ("Copy transcript", lambda *_: self.copy_transcript()),
            ("Copy harmless test text", lambda *_: self.window.get_clipboard().set("WhisperShortcut clipboard test")),
            ("Shortcut setup", lambda *_: self.shortcut_help()),
            ("Test disposable keyring value", lambda *_: self.keyring_test()),
            ("Cancel keyring test", lambda *_: self.cancel_keyring()),
            ("Quit", lambda *_: self.request_quit()),
        ]:
            button = Gtk.Button(label=_(label))
            if label == "Transcribe recording":
                self.transcribe_button = button
            button.connect("clicked", callback)
            box.append(button)
        self.background = Gtk.CheckButton(label=_("Keep running when the window closes"))
        self.background.connect("toggled", self.background_changed)
        box.append(self.background)
        try:
            self.show_provider(load_config())
        except ConfigError as error:
            self.say(str(error))
        self.window.present()
        GLib.timeout_add(250, self.tick)
        if self.smoke:
            GLib.timeout_add(1200, self.smoke_check)
        else:
            threading.Thread(target=self.find_sources, daemon=True).start()

    def say(self, message):
        self.status.set_text(_(message))

    def find_sources(self):
        monitor = Gst.DeviceMonitor.new()
        try:
            monitor.set_property("show-all", True)
            monitor.add_filter("Audio/Source", None)
            monitor.start()
            devices = monitor.get_devices()
            GLib.idle_add(self.set_sources, devices)
        except Exception:
            GLib.idle_add(self.say, "Audio source discovery failed.")
        finally:
            monitor.stop()

    def set_sources(self, devices):
        authorized = self.pending_toggle and self.state == "idle"
        self.pending_toggle = False
        self.devices = devices
        names = [device.get_display_name() for device in devices]
        self.microphone.set_model(Gtk.StringList.new(names or [_("No microphone sources found")]))
        if not devices:
            self.say("No microphone sources found")
        elif authorized:
            self.start_capture("microphone")

    def background_changed(self, button):
        if button.get_active() and not self.background_held:
            self.hold()
            self.background_held = True
        elif not button.get_active() and self.background_held:
            self.release()
            self.background_held = False

    def close_window(self, *_):
        self.pending_toggle = False
        if self.state == "transcribing":
            self.say("Cancel transcription before closing.")
            return True
        if self.state in {"recording", "stopping"}:
            self.say("Stop or cancel recording before closing.")
            return True
        if self.background.get_active():
            self.window.set_visible(False)
        else:
            self.request_quit()
        return True

    def start_capture(self, mode):
        self.pending_toggle = False
        if self.state not in {"idle", "playing"}:
            self.say("Another recording is active.")
            return
        if self.state == "playing":
            self.cancel(delete_audio=False)
        index = self.microphone.get_selected()
        if mode != "system" and index >= len(self.devices):
            self.say("No microphone sources found")
            return
        self.transcript_text = ""
        self.transcript_buffer.set_text("")
        self.delete_audio()
        self.audio_path = Path(self.scratch.name) / (uuid.uuid4().hex + ".wav")
        self.audio_path.touch(mode=0o600)
        try:
            pipeline = Gst.parse_launch(
                "audiomixer name=mix ! audioconvert ! audioresample ! "
                "audio/x-raw,format=S16LE,rate=16000,channels=1 ! wavenc ! filesink name=output")
            self.pipeline = pipeline
            pipeline.get_by_name("output").set_property("location", str(self.audio_path))
            sources = []
            if mode != "system":
                sources.append(self.devices[index].create_element(None))
            if mode != "microphone":
                source = Gst.ElementFactory.make("pulsesrc", None)
                if source is None:
                    raise RuntimeError("PulseAudio source plugin unavailable")
                source.set_property("device", self.monitor.get_text().strip() or "@DEFAULT_MONITOR@")
                sources.append(source)
            for source in sources:
                if source is None:
                    raise RuntimeError("Audio source unavailable")
                chain = [source, Gst.ElementFactory.make("queue"),
                         Gst.ElementFactory.make("audioconvert"),
                         Gst.ElementFactory.make("audioresample")]
                for element in chain:
                    if element is None:
                        raise RuntimeError("Audio plugin unavailable")
                    pipeline.add(element)
                for before, after in zip(chain, chain[1:]):
                    if not before.link(after):
                        raise RuntimeError("Audio link failed")
                if not chain[-1].link(pipeline.get_by_name("mix")):
                    raise RuntimeError("Audio mixer link failed")
            self.watch_pipeline()
            self.state = "recording"
            self.started_at = time.monotonic()
            if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError("Audio start failed")
            self.say("Recording — use Stop to finalize or Cancel to delete.")
        except Exception:
            self.cancel(delete_audio=True)
            self.say("Audio capture failed. Check source, permissions and device availability.")

    def watch_pipeline(self):
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus_handler = self.bus.connect("message", self.message)

    def message(self, bus, message):
        if message.type == Gst.MessageType.ERROR:
            # Playback uses an already-valid recording; an output failure must
            # preserve it for retry. Failed captures are incomplete disposable output.
            self.cancel(delete_audio=self.state != "playing")
            self.say("Audio operation failed. Check device availability.")
        elif message.type == Gst.MessageType.EOS:
            was_capture = self.state == "stopping"
            self.release_pipeline()
            self.state = "idle"
            self.say("Recording saved locally. Listen back to verify both content and sources."
                     if was_capture else "Playback finished.")
            if self.pending_quit:
                self.quit()

    def tick(self):
        if self.state == "recording":
            self.status.set_text(_("Recording — seconds elapsed: {seconds}").format(
                seconds=int(time.monotonic() - self.started_at)))
        return True

    def stop(self):
        self.pending_toggle = False
        if self.state == "transcribing":
            self.cancel_transcription()
            return
        if self.state == "recording":
            self.state = "stopping"
            self.say("Finalizing recording…")
            self.stop_timeout = GLib.timeout_add_seconds(10, self.stop_failed)
            self.pipeline.send_event(Gst.Event.new_eos())
        elif self.state == "playing":
            self.cancel(delete_audio=False)

    def stop_failed(self):
        self.stop_timeout = None
        self.cancel()
        self.pending_quit = False
        self.say("Audio finalization timed out; incomplete test audio was deleted.")
        return False

    def release_pipeline(self):
        if self.stop_timeout:
            GLib.source_remove(self.stop_timeout)
            self.stop_timeout = None
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        if self.bus:
            if self.bus_handler:
                self.bus.disconnect(self.bus_handler)
            self.bus.remove_signal_watch()
        self.pipeline = self.bus = self.bus_handler = None

    def delete_audio(self):
        if self.audio_path:
            self.audio_path.unlink(missing_ok=True)
            self.audio_path = None

    def cancel(self, delete_audio=None):
        self.pending_toggle = False
        if self.state == "transcribing":
            self.cancel_transcription()
            return
        if delete_audio is None:
            delete_audio = self.state in {"recording", "stopping"}
        self.release_pipeline()
        self.state = "idle"
        if delete_audio:
            self.delete_audio()
        self.say("Idle")

    def delete_recording(self):
        if self.state != "idle":
            self.say("Stop or cancel the active operation before deleting the recording.")
            return
        self.delete_audio()
        self.say("Recording deleted.")

    def show_provider(self, config):
        self.visible_provider = config.provider
        label = ("Transcribe recording (local CPU)" if config.provider == "local"
                 else "Transcribe recording (OpenRouter cloud)")
        self.transcribe_button.set_label(_(label))

    def transcribe_recording(self):
        if self.state != "idle":
            self.say("Another operation is active.")
            return
        if not self.audio_path or not self.audio_path.exists():
            self.say("No completed recording is available.")
            return
        try:
            config = load_config()
        except ConfigError as error:
            self.say(str(error))
            return
        if config.provider != self.visible_provider:
            self.show_provider(config)
            self.say("Provider changed. Review the displayed provider, then press Transcribe again.")
            return
        job = TranscriptionJob(self.audio_path, config,
                               lambda callback: GLib.idle_add(callback),
                               self.finish_transcription)
        self.transcription_task = job
        self.state = "transcribing"
        self.say("Transcribing locally…" if config.provider == "local" else "Transcribing with OpenRouter…")
        try:
            job.start()
        except Exception:
            self.cancel_transcription()
            self.say("Transcription could not start. Your recording is kept for retry.")

    def finish_transcription(self, job, text, error):
        if self.transcription_task is not job or self.state != "transcribing":
            return
        self.transcription_task = None
        self.state = "idle"
        if error:
            self.say(TranscriptionError(error).message)
            return
        if not isinstance(text, str) or not text.strip():
            self.say(TranscriptionError("response").message)
            return
        self.transcript_text = text
        self.transcript_buffer.set_text(text)
        self.say("Transcription complete. Use Copy transcript to copy it.")

    def cancel_transcription(self):
        job = self.transcription_task
        self.transcription_task = None  # Invalidate queued callbacks before closing transport.
        if job:
            job.cancel()
        self.state = "idle"
        self.say("Transcription cancelled. Your recording is kept for retry.")

    def copy_transcript(self):
        if not self.transcript_text:
            self.say("No transcript is available.")
            return
        self.window.get_clipboard().set(self.transcript_text)
        self.say("Transcript copied.")

    def play(self):
        if self.state != "idle":
            self.say("Stop recording or playback first.")
            return
        if not self.audio_path or not self.audio_path.exists():
            self.say("No test recording available.")
            return
        try:
            self.pipeline = Gst.ElementFactory.make("playbin")
            self.pipeline.set_property("uri", self.audio_path.as_uri())
            self.watch_pipeline()
            self.state = "playing"
            if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError("Playback failed")
        except Exception:
            self.cancel(delete_audio=False)
            self.say("Audio operation failed. Check device availability.")

    def shortcut_help(self):
        self.say("On GNOME: Settings → Keyboard → Custom Shortcuts. Bind the documented command ending in --toggle-recording. Do not register it until microphone recording works.")

    def keyring_test(self):
        if self.keyring_cancel:
            self.say("Keyring test already running.")
            return
        self.keyring_cancel = Gio.Cancellable()
        schema = Secret.Schema.new(APP_ID, Secret.SchemaFlags.NONE,
                                   {"test": Secret.SchemaAttributeType.STRING})
        attributes = {"test": uuid.uuid4().hex}
        verified = False
        value = uuid.uuid4().hex  # synthetic only; never prints or reads real credentials
        self.say("Testing a disposable keyring value…")

        def clear():
            # Separate cancellable: cleanup must still work after user cancellation.
            Secret.password_clear(schema, attributes, None, cleared)

        def cleared(source, result, *unused):
            try:
                removed = Secret.password_clear_finish(result)
                self.say(("Keyring test passed; disposable value removed." if verified else
                          "Keyring test cancelled or failed; disposable item cleanup finished.")
                         if removed else "Keyring cleanup failed; remove the prototype test item manually.")
            except GLib.Error:
                self.say("Keyring cleanup failed; remove the prototype test item manually.")
            self.keyring_cancel = None

        def looked_up(source, result, *unused):
            nonlocal verified
            try:
                verified = Secret.password_lookup_finish(result) == value
                self.say("Disposable value matched." if verified else "Keyring verification failed.")
            except GLib.Error:
                self.say("Keyring test cancelled or unavailable.")
            finally:
                clear()

        def stored(source, result, *unused):
            try:
                if not Secret.password_store_finish(result):
                    raise RuntimeError("Store failed")
                Secret.password_lookup(schema, attributes, self.keyring_cancel, looked_up)
            except (GLib.Error, RuntimeError):
                # Cancellation can race successful storage; always attempt exact-item cleanup.
                clear()

        Secret.password_store(schema, attributes, Secret.COLLECTION_DEFAULT,
                              "WhisperShortcut prototype test", value,
                              self.keyring_cancel, stored)

    def cancel_keyring(self):
        if self.keyring_cancel:
            self.keyring_cancel.cancel()
            self.say("Cancelling keyring test; cleanup will follow.")

    def request_quit(self):
        self.pending_toggle = False
        if self.state == "transcribing":
            self.say("Cancel transcription before quitting.")
            return
        if self.keyring_cancel:
            self.cancel_keyring()
            self.say("Wait for keyring cleanup before quitting.")
            return
        if self.state in {"recording", "stopping"}:
            self.say("Stop or cancel recording before quitting.")
            return
        self.quit()

    def smoke_check(self):
        try:
            paintable = Gtk.WidgetPaintable.new(self.window)
            snapshot = Gtk.Snapshot()
            paintable.snapshot(snapshot, self.window.get_width(), self.window.get_height())
            node = snapshot.to_node()
            texture = self.window.get_renderer().render_texture(node, None)
            if not texture.save_to_png("/tmp/whisper-prototype-smoke.png"):
                raise RuntimeError("Screenshot failed")
            print("GTK window rendered; main-loop timer fired; no recording started.")
        except Exception as error:
            # Exception type only; avoid raw paths, device names and input.
            print("GTK smoke check failed: " + type(error).__name__, file=sys.stderr)
            self.exit_code = 1
        self.quit()
        return False

    def do_shutdown(self):
        self.pending_toggle = False
        if self.transcription_task:
            self.cancel_transcription()
        self.release_pipeline()
        self.scratch.cleanup()
        Gtk.Application.do_shutdown(self)


if __name__ == "__main__":
    app = Demo()
    status = app.run(sys.argv)
    raise SystemExit(status or app.exit_code)
