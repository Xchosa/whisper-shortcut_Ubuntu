"""Bounded WAV-to-text request; never logs credentials, provider bodies or audio."""
import base64
import http.client
import io
import json
from pathlib import Path
import socket
import wave

MAX_AUDIO_BYTES = 20 * 1024 * 1024
MAX_AUDIO_SECONDS = 300
MAX_RESPONSE_BYTES = 1024 * 1024
REQUEST_TIMEOUT = 65


class TranscriptionError(Exception):
    MESSAGES = {
        "missing_audio": "No completed recording is available.",
        "invalid_audio": "The recording is not a valid non-empty WAV file.",
        "audio_too_large": "The recording exceeds the prototype's 20 MB audio limit.",
        "audio_too_long": "Use a recording of at most five minutes for this prototype.",
        "credentials": "OpenRouter rejected the API key. Check your local configuration.",
        "credits": "OpenRouter requires available credit for this transcription.",
        "rate_limit": "OpenRouter is rate limiting requests. Try again later.",
        "provider": "OpenRouter rejected the audio or model, or the provider is unavailable.",
        "network": "The transcription connection failed. Your recording is kept for retry.",
        "timeout": "Transcription timed out. Your recording is kept for retry.",
        "response": "OpenRouter returned an invalid or empty transcript.",
        "cancelled": "Transcription cancelled. Your recording is kept for retry.",
    }

    def __init__(self, code):
        self.code = code if code in self.MESSAGES else "network"
        self.message = self.MESSAGES[self.code]
        super().__init__(self.message)


def check_cancelled(cancelled):
    if cancelled.is_set():
        raise TranscriptionError("cancelled")


def read_audio(path: Path, cancelled) -> bytes:
    check_cancelled(cancelled)
    try:
        with path.open("rb") as audio_file:
            audio = audio_file.read(MAX_AUDIO_BYTES + 1)
    except OSError:
        raise TranscriptionError("missing_audio") from None
    if len(audio) > MAX_AUDIO_BYTES:
        raise TranscriptionError("audio_too_large")
    check_cancelled(cancelled)
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            frames = wav.getnframes()
            if not frames or not wav.getframerate():
                raise TranscriptionError("invalid_audio")
            if frames / wav.getframerate() > MAX_AUDIO_SECONDS:
                raise TranscriptionError("audio_too_long")
            expected = frames * wav.getnchannels() * wav.getsampwidth()
            if expected > MAX_AUDIO_BYTES or len(wav.readframes(frames)) != expected:
                raise TranscriptionError("invalid_audio")
    except (wave.Error, EOFError, ValueError):
        raise TranscriptionError("invalid_audio") from None
    return audio


def transcribe(path, config, cancelled, attach_connection,
               *, connection_factory=http.client.HTTPSConnection) -> str:
    audio = read_audio(path, cancelled)
    body = json.dumps({
        "model": config.model,
        "input_audio": {"data": base64.b64encode(audio).decode("ascii"), "format": "wav"},
    }).encode("utf-8")
    check_cancelled(cancelled)
    connection = None
    try:
        connection = connection_factory("openrouter.ai", timeout=REQUEST_TIMEOUT)
        # HTTPConnection normally reopens itself on request(). After cancellation
        # closes the socket, that behavior could start a fresh unwanted upload.
        connection.auto_open = False
        attach_connection(connection)
        check_cancelled(cancelled)
        connection.connect()
        check_cancelled(cancelled)
        connection.request("POST", "/api/v1/audio/transcriptions", body=body, headers={
            "Authorization": "Bearer " + config.api_key,
            "Content-Type": "application/json",
        })
        response = connection.getresponse()
        check_cancelled(cancelled)
        if not 200 <= response.status < 300:
            # Provider messages can echo user input or credentials: never forward the body.
            code = {401: "credentials", 403: "credentials",
                    402: "credits", 429: "rate_limit"}.get(response.status, "provider")
            raise TranscriptionError(code)
        content = bytearray()
        while True:
            check_cancelled(cancelled)
            chunk = response.read(min(8192, MAX_RESPONSE_BYTES - len(content) + 1))
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > MAX_RESPONSE_BYTES:
                raise TranscriptionError("response")
        check_cancelled(cancelled)
        try:
            payload = json.loads(content)
        except (ValueError, UnicodeError):
            raise TranscriptionError("response") from None
        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise TranscriptionError("response")
        return text.strip()
    except TranscriptionError:
        raise
    except (socket.timeout, TimeoutError):
        check_cancelled(cancelled)
        raise TranscriptionError("timeout") from None
    except (OSError, http.client.HTTPException):
        check_cancelled(cancelled)
        raise TranscriptionError("network") from None
    finally:
        if connection:
            try:
                connection.close()
            except OSError:
                pass
