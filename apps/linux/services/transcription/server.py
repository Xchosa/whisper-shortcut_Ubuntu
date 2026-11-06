"""Small private JSON STT service. Audio is processed in memory, never logged."""
import base64
import binascii
import io
import json
import logging
import os
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL_NAME = "base"
MAX_REQUEST_BYTES = 30 * 1024 * 1024
MAX_AUDIO_BYTES = 20 * 1024 * 1024
MAX_SECONDS = 300


def decode_request(payload):
    if not isinstance(payload, dict) or payload.get("model") != MODEL_NAME:
        raise ValueError()
    audio = payload.get("input_audio")
    if not isinstance(audio, dict) or audio.get("format") != "wav":
        raise ValueError()
    data = base64.b64decode(audio.get("data", ""), validate=True)
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise ValueError()
    with wave.open(io.BytesIO(data), "rb") as wav:
        frames = wav.getnframes()
        if not frames or frames / wav.getframerate() > MAX_SECONDS:
            raise ValueError()
        expected = frames * wav.getnchannels() * wav.getsampwidth()
        if expected > MAX_AUDIO_BYTES or len(wav.readframes(frames)) != expected:
            raise ValueError()
    return data


def load_model(factory=None):
    if factory is None:
        from faster_whisper import WhisperModel
        factory = WhisperModel
    return factory("/models/base", device="cpu", compute_type="int8",
                   cpu_threads=4, num_workers=1, local_files_only=True)


def make_server(model, host="0.0.0.0", port=8000):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            # Default request logging is unnecessary and may expose query/input values.
            pass

        def reply(self, status, payload):
            content = json.dumps(payload).encode("utf-8")
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            if self.path != "/health":
                self.reply(404, {"error": "not_found"})
                return
            self.reply(200, {"status": "ready", "model": MODEL_NAME})

        def do_POST(self):
            self.connection.settimeout(15)
            if self.path != "/v1/audio/transcriptions":
                self.reply(404, {"error": "not_found"})
                return
            if self.headers.get("Origin"):
                self.reply(403, {"error": "origin_not_allowed"})
                return
            if self.headers.get_content_type() != "application/json":
                self.reply(415, {"error": "json_required"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_REQUEST_BYTES or self.headers.get("Transfer-Encoding"):
                    raise ValueError()
            except ValueError:
                self.reply(400, {"error": "invalid_request"})
                return
            if not self.server.inference_gate.acquire(blocking=False):
                self.reply(503, {"error": "busy"})
                return
            try:
                try:
                    content = self.rfile.read(length)
                    if len(content) != length:
                        raise ValueError()
                    data = decode_request(json.loads(content))
                except (ValueError, TypeError, binascii.Error, wave.Error, EOFError, OSError):
                    self.reply(400, {"error": "invalid_request"})
                    return
                # Iterate the generator while holding the gate: inference is lazy.
                segments, info = model.transcribe(
                    io.BytesIO(data), task="transcribe", beam_size=1,
                    vad_filter=True, condition_on_previous_text=False, temperature=0)
                text = "".join(segment.text for segment in segments).strip()
                if len(text.encode("utf-8")) > 1024 * 1024:
                    raise ValueError()
                self.reply(200, {"text": text, "language": info.language, "model": MODEL_NAME})
            except Exception:
                self.reply(500, {"error": "transcription_failed"})
            finally:
                self.server.inference_gate.release()

    server = ThreadingHTTPServer((host, port), Handler)
    server.inference_gate = threading.Semaphore(1)
    return server


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        model = load_model()
    except Exception:
        logging.error("Local model could not load; rebuild the transcription image.")
        raise SystemExit(1) from None
    logging.info("Local CPU transcription model ready.")
    with make_server(model) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
