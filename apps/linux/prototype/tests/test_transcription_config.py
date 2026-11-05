from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from transcription_config import ConfigError, load_config


class TranscriptionConfigTests(unittest.TestCase):
    def config_file(self, directory, content):
        path = Path(directory) / ".env"
        path.write_text(content)
        return path

    def test_reads_separate_transcription_model_and_hides_key(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "openrouter"}, clear=True):
            path = self.config_file(directory,
                'OPENROUTER_API_KEY=synthetic-private-key\n'
                'OPENROUTER_GENERATION_MODEL=openrouter/free\n'
                'OPENROUTER_TRANSCRIPTION_MODEL=openai/whisper-large-v3-turbo\n')
            config = load_config(path)
        self.assertEqual(config.api_key, "synthetic-private-key")
        self.assertEqual(config.model, "openai/whisper-large-v3-turbo")
        self.assertNotIn("synthetic-private-key", repr(config))

    def test_process_environment_takes_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.config_file(directory,
                'OPENROUTER_API_KEY=file-key\nOPENROUTER_TRANSCRIPTION_MODEL=vendor/file\n')
            with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "openrouter", "OPENROUTER_API_KEY": "process-key",
                                         "OPENROUTER_TRANSCRIPTION_MODEL": "vendor/process"}, clear=True):
                config = load_config(path)
        self.assertEqual(config.api_key, "process-key")
        self.assertEqual(config.model, "vendor/process")

    def test_supports_quotes_export_and_comments(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "openrouter"}, clear=True):
            path = self.config_file(directory,
                "export OPENROUTER_API_KEY='quoted-key' # comment\n"
                'OPENROUTER_TRANSCRIPTION_MODEL="vendor/model"\n')
            config = load_config(path)
        self.assertEqual(config.api_key, "quoted-key")

    def test_generation_model_is_not_used_for_transcription(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "openrouter", "OPENROUTER_API_KEY": "key",
                                     "OPENROUTER_GENERATION_MODEL": "openrouter/free"}, clear=True):
            with self.assertRaises(ConfigError) as error:
                load_config(Path("/nonexistent/test-config"))
        self.assertEqual(error.exception.code, "missing_model")

    def test_missing_config_key_and_model_report_fixed_errors(self):
        cases = [({}, "missing_key"), ({"OPENROUTER_API_KEY": "key"}, "missing_model")]
        for env, expected in cases:
            with self.subTest(expected=expected), patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "openrouter", **env}, clear=True):
                with self.assertRaises(ConfigError) as error:
                    load_config(Path("/nonexistent/test-config"))
                self.assertEqual(error.exception.code, expected)

    def test_invalid_config_does_not_echo_secret_or_execute_shell(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "openrouter"}, clear=True):
            marker = Path(directory) / "must-not-exist"
            path = self.config_file(directory,
                f'OPENROUTER_API_KEY=$(touch {marker})\n'
                'OPENROUTER_TRANSCRIPTION_MODEL=vendor/model\n')
            with self.assertRaises(ConfigError) as error:
                load_config(path)
            self.assertNotIn(str(marker), str(error.exception))
            self.assertFalse(marker.exists())

    def test_rejects_header_injection_and_invalid_model(self):
        for env in [{"OPENROUTER_API_KEY": "key\r\nInjected: private",
                     "OPENROUTER_TRANSCRIPTION_MODEL": "vendor/model"},
                    {"OPENROUTER_API_KEY": "key",
                     "OPENROUTER_TRANSCRIPTION_MODEL": "https://private/path"}]:
            with self.subTest(), patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "openrouter", **env}, clear=True):
                with self.assertRaises(ConfigError) as error:
                    load_config(Path("/nonexistent/test-config"))
                self.assertNotIn("private", str(error.exception))

    def test_rejects_oversized_env_without_echoing_content(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "openrouter"}, clear=True):
            path = self.config_file(directory, "x" * 65537)
            with self.assertRaises(ConfigError):
                load_config(path)
