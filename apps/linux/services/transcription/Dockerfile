FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1
WORKDIR /service
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "import io,wave; from faster_whisper.audio import decode_audio; data=io.BytesIO(); wav=wave.open(data,'wb'); wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(bytes(32000)); wav.close(); assert len(decode_audio(io.BytesIO(data.getvalue()))) == 16000"
# Weights are pinned and baked into the image; runtime needs no model download.
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-base', revision='ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66', local_dir='/models/base', allow_patterns=['model.bin','config.json','tokenizer.json','vocabulary.txt'])"
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
COPY server.py .
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).close()"
CMD ["python", "server.py"]
