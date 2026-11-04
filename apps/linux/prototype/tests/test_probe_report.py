import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import desktop_probe


class ProbeReportTests(unittest.TestCase):
    def test_report_schema(self):
        report = desktop_probe.collect_report()
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(set(report), {"schema_version", "platform", "session_type",
                                      "desktop", "dependencies", "capabilities"})
        for group in ("dependencies", "capabilities"):
            for entry in report[group].values():
                self.assertIn(entry["status"],
                              {"available", "unavailable", "blocked", "untested"})
                self.assertIsInstance(entry["reason"], str)

    def test_missing_dependency_is_unavailable(self):
        with patch("desktop_probe.subprocess.run", side_effect=FileNotFoundError):
            report = desktop_probe.collect_report()
        self.assertEqual(report["dependencies"]["gtk"]["status"], "unavailable")
        self.assertEqual(report["capabilities"]["microphone"]["status"], "unavailable")

    def test_missing_session_bus_is_blocked(self):
        with patch.dict(os.environ, {}, clear=True):
            report = desktop_probe.collect_report()
        self.assertEqual(report["capabilities"]["global_shortcuts"]["status"], "blocked")
        self.assertEqual(report["capabilities"]["keyring"]["status"], "blocked")

    def test_report_contains_no_environment_values_or_device_identifiers(self):
        sensitive = "private-home-device-token-transcript"
        with patch.dict(os.environ, {"HOME": sensitive, "OPENAI_API_KEY": sensitive,
                                     "XDG_CURRENT_DESKTOP": sensitive,
                                     "XDG_SESSION_TYPE": sensitive,
                                     "DBUS_SESSION_BUS_ADDRESS": sensitive}):
            with patch("desktop_probe.subprocess.run",
                       return_value=subprocess.CompletedProcess([], 1, sensitive, sensitive)):
                text = json.dumps(desktop_probe.collect_report())
        self.assertNotIn(sensitive, text)
        self.assertNotIn("OPENAI_API_KEY", text)

    def test_timeout_is_handled_without_raw_exception(self):
        with patch("desktop_probe.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("private command", 5)):
            report = desktop_probe.collect_report()
        self.assertNotIn("private command", json.dumps(report))
        self.assertEqual(report["dependencies"]["gtk"]["status"], "blocked")

    def test_cli_json_does_not_claim_functional_success(self):
        output = io.StringIO()
        with patch("desktop_probe.collect_report", return_value={"schema_version": 1}):
            with contextlib.redirect_stdout(output):
                self.assertEqual(desktop_probe.main(["--json"]), 0)
        self.assertEqual(json.loads(output.getvalue()), {"schema_version": 1})

    def test_installed_dependencies_do_not_prove_audio_or_shortcuts(self):
        xml = '<node><interface name="org.freedesktop.portal.GlobalShortcuts"/></node>'
        def fake_run(command, **kwargs):
            if "--xml" in command:
                return subprocess.CompletedProcess(command, 0, xml, "")
            return subprocess.CompletedProcess(command, 0, "1", "")
        with patch.dict(os.environ, {"DBUS_SESSION_BUS_ADDRESS": "test"}):
            with patch("desktop_probe.subprocess.run", side_effect=fake_run):
                report = desktop_probe.collect_report()
        self.assertEqual(report["capabilities"]["global_shortcuts"]["status"], "untested")
        self.assertEqual(report["capabilities"]["microphone"]["status"], "untested")
