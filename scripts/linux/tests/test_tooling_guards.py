"""Safety regression: historical jobs must not mutate the host or publish."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
ENTRY_POINTS = [
    "scripts/agent-loops-job.sh", "scripts/growth-review-job.sh",
    "scripts/usage-review-job.sh", "scripts/model-audit-job.sh",
    "scripts/model-lineup-check.sh", "scripts/stable-promote-job.sh",
    "scripts/implementer/install-implementer.sh",
    "scripts/implementer/install-tick.sh",
    "scripts/implementer/install-night-awake.sh",
    "scripts/implementer/tick.sh", "scripts/implementer/run-implementer.sh",
    "scripts/implementer/release-merges.sh",
    "scripts/merge-train/install.sh", "scripts/merge-train/train.sh",
]


class ToolingGuardsTests(unittest.TestCase):
    def test_historical_jobs_refuse_before_host_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "called"
            for command in ("uname", "osascript", "security", "open", "pkill",
                            "xcodebuild", "launchctl", "gh", "git", "claude",
                            "cursor-agent", "mkdir", "date", "dirname", "sleep"):
                sentinel = Path(directory) / command
                sentinel.write_text('#!/bin/sh\nprintf called >> "$GUARD_MARKER"\nexit 99\n')
                sentinel.chmod(0o755)
            env = {"PATH": directory, "HOME": directory, "GUARD_MARKER": str(marker)}
            for relative in ENTRY_POINTS:
                with self.subTest(script=relative):
                    result = subprocess.run(
                        ["/bin/bash", str(ROOT / relative)], cwd=directory,
                        env=env, capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("disabled in this fork", result.stderr)
                    self.assertFalse(marker.exists(), "host command was executed")
