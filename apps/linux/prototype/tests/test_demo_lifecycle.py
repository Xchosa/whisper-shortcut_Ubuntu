"""Exercise real demo methods without importing GI or opening desktop services."""
import ast
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest


def demo_type():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "desktop_demo.py").read_text())
    original = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Demo")
    names = {"cancel", "delete_audio", "stop", "set_sources", "message",
             "do_command_line", "close_window"}
    # Execute these exact methods, isolating only GTK's inheritance/import boundary.
    original.bases = []
    original.body = [node for node in original.body if isinstance(node, ast.FunctionDef) and node.name in names]
    module = ast.Module(body=[original], type_ignores=[])
    namespace = {
        "_": lambda message: message,
        "Gtk": SimpleNamespace(StringList=SimpleNamespace(new=lambda names: names)),
        "Gst": SimpleNamespace(MessageType=SimpleNamespace(ERROR="error", EOS="eos")),
    }
    exec(compile(module, "<real desktop demo methods>", "exec"), namespace)
    return namespace["Demo"]


class DemoLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.demo = demo_type()()
        self.demo.state = "idle"
        self.demo.pending_toggle = True
        self.demo.audio_path = None
        self.demo.devices = []
        self.demo.window = SimpleNamespace(set_visible=lambda visible: None)
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

    def test_capture_error_deletes_incomplete_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "incomplete.wav"
            path.write_bytes(b"incomplete")
            self.demo.audio_path = path
            self.demo.state = "recording"
            self.demo.message(None, SimpleNamespace(type="error"))
            self.assertFalse(path.exists())
            self.assertIsNone(self.demo.audio_path)
            self.assertEqual(self.demo.state, "idle")
