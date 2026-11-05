"""Explicit development configuration. Values are data, never shell commands."""
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shlex

CONFIG_KEYS = {"OPENROUTER_API_KEY", "OPENROUTER_TRANSCRIPTION_MODEL"}
MAX_CONFIG_BYTES = 65536


class ConfigError(Exception):
    MESSAGES = {
        "missing_key": "Set OPENROUTER_API_KEY in env/.env or the process environment.",
        "missing_model": "Set OPENROUTER_TRANSCRIPTION_MODEL; the generation model is not used for audio.",
        "invalid_config": "The development configuration is invalid or unreadable. Check its KEY=value entries.",
    }

    def __init__(self, code):
        self.code = code
        super().__init__(self.MESSAGES.get(code, self.MESSAGES["invalid_config"]))


@dataclass(frozen=True)
class TranscriptionConfig:
    api_key: str = field(repr=False)
    model: str


def read_env_file(path: Path) -> dict[str, str]:
    try:
        with path.open("rb") as source:
            raw = source.read(MAX_CONFIG_BYTES + 1)
        if len(raw) > MAX_CONFIG_BYTES:
            raise ConfigError("invalid_config")
        text = raw.decode("utf-8")
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError):
        raise ConfigError("invalid_config") from None
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ConfigError("invalid_config")
        if key not in CONFIG_KEYS:
            continue
        try:
            parts = shlex.split(value, comments=True, posix=True)
        except ValueError:
            raise ConfigError("invalid_config") from None
        if len(parts) > 1:
            raise ConfigError("invalid_config")
        values[key] = parts[0] if parts else ""
    return values


def load_config(env_file: Path | None = None) -> TranscriptionConfig:
    if env_file is None:
        explicit = os.environ.get("WHISPER_SHORTCUT_ENV_FILE")
        env_file = Path(explicit) if explicit else Path(__file__).resolve().parents[3] / "env/.env"
    values = read_env_file(env_file)
    for key in CONFIG_KEYS:
        if key in os.environ:
            values[key] = os.environ[key]
    key = values.get("OPENROUTER_API_KEY", "")
    model = values.get("OPENROUTER_TRANSCRIPTION_MODEL", "")
    if not key:
        raise ConfigError("missing_key")
    if not model:
        raise ConfigError("missing_model")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,512}", key):
        raise ConfigError("invalid_config")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._:+-]*", model):
        raise ConfigError("invalid_config")
    return TranscriptionConfig(api_key=key, model=model)
