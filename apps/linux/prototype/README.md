# Ubuntu transcription prototype

Record locally, explicitly transcribe through a small CPU container, then display
and copy the transcript. This is a development prototype, not full Mac parity.

## Start on Ubuntu 24.04 / GNOME

```bash
bash scripts/linux/start-local-transcription.sh
bash scripts/linux/run-prototype.sh
# German UI, independent of installed system locales:
LANGUAGE=de bash scripts/linux/run-prototype.sh
```

The first command builds the model image and waits for health. Initial build
requires Internet for Python packages and public model weights. Subsequent model
loads use the pinned weights inside the image with Hugging Face offline mode;
audio inference uses the local CPU and requires no API key. The container has a
normal Docker bridge (not an egress firewall), and publishes only
`127.0.0.1:8765`. The GUI handles the microphone; no audio device or personal
folder is mounted into the container.

1. Select a microphone source and click **Record microphone**.
2. Click **Stop and finalize** and wait until the recording is saved.
3. Click **Transcribe recording (local CPU)**.
4. Read the **Transcript** field; **Copy transcript** copies it explicitly.

No transcription starts on launch, recording Stop, or playback. During
transcription, Cancel stops the UI operation, attempts to close the connection,
and retains the WAV for retry. The model may finish its already-started CPU work
before becoming available for another request. No automatic cloud fallback or
request retry is performed. Use **Delete recording** when idle to delete audio.

The small multilingual `base` model supports testing German/English; recording
quality and recognition accuracy still need evaluation on your own speech. It
uses faster-whisper 1.2.1 / CPU INT8, with PyAV 16.0.1 pinned for compatibility.
The Docker build decodes a synthetic WAV so incompatible decoder updates fail
before deployment. Model revision is pinned in the Dockerfile.

## Current limits and privacy

- WAV only, at most five minutes and 20 MiB. Longer meetings need a later chunking
  implementation; this prototype rejects them rather than truncating.
- Transcripts exist in the window only. Copy text before quitting; history and
  crash recovery are not implemented.
- A new recording replaces the previous test audio and clears its old text.
  Cancelled/failed transcription preserves audio while the window is running.
- Normal Quit removes private temporary audio. A process crash can leave test
  files in the OS temporary directory. Never kill a recording to refresh code.
- The local service processes audio in memory, logs neither content nor requests,
  and receives no OpenRouter key. Service access is limited to host loopback;
  processes on the same computer can still access it.

## Configuration

Local mode works without an env file. Optional development settings:

```dotenv
TRANSCRIPTION_PROVIDER=local
LOCAL_TRANSCRIPTION_URL=http://127.0.0.1:8765
LOCAL_TRANSCRIPTION_MODEL=base
```

The run script resolves `env/.env` in the main checkout even from a worktree;
`WHISPER_SHORTCUT_ENV_FILE` can select another file. Actual process variables
win over file values. This parser supports simple `KEY=value`, quotes, comments
and `export`; it never sources shell code or expands variables. Real files stay
ignored. `env/.env.example` contains placeholders only.

OpenRouter is an **explicit optional alternative**, not live-validated here:

```dotenv
TRANSCRIPTION_PROVIDER=openrouter
OPENROUTER_API_KEY=your_actual_key
OPENROUTER_TRANSCRIPTION_MODEL=openai/whisper-large-v3-turbo
OPENROUTER_GENERATION_MODEL=openrouter/free
```

Cloud mode sends audio to OpenRouter and may incur charges. The generation model
is never used for audio. Changing between local/cloud while the app is open
updates the displayed provider and requires a fresh Transcribe click before any
request. Production keyring settings are future work; env is development input.
No real credential is printed or copied into the worktree/container.

## Dependencies and checks

Use `/usr/bin/python3` (Ubuntu Python 3.12). The GUI needs distro GI libraries:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-gstreamer-1.0 \
  gir1.2-gst-plugins-base-1.0 gir1.2-secret-1 gstreamer1.0-tools \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good
```

Package installation is explicit, not performed by the scripts. Docker Compose
is required for local inference. The probe/headless tests need only stdlib Python;
tests fake the model and never download weights or make external API requests.

```bash
bash scripts/linux/probe-desktop.sh --json
bash scripts/linux/test.sh
bash scripts/linux/run-prototype.sh --smoke-test
```

The smoke check refuses to replace an existing instance. Quit normally before a
separate smoke run. It renders its own window without starting microphone/cloud
operations and writes a temporary screenshot. English/German labels use a narrow
singular PO reader for the prototype; production will use compiled gettext.

## Other desktop controls

System/combined capture and playback remain available. Test monitor sources,
headphones, silence and device loss separately; a microphone-only result does
not establish complete meeting support. The disposable keyring button tests
only a synthetic value, not production credentials. Wait for cleanup before Quit.

GNOME on the tested machine lacks the GlobalShortcuts portal. After dictation
works, create a custom shortcut manually in GNOME Settings, bound to:

```text
bash /absolute/path/to/repo/scripts/linux/run-prototype.sh --toggle-recording
```

It targets one application instance and waits for microphone discovery on cold
start. It starts/stops recording, not automatic cloud transcription or typing.
Clipboard/manual paste is the supported baseline on Wayland.

## Stop the local service

When no transcription is in progress:

```bash
docker compose -f compose.local.yaml stop transcription
```

Do not stop unrelated Docker projects. Build/run commands use the separate
`whispershortcut-local-stt` Compose project.
