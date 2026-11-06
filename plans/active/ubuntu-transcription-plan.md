# Ubuntu Local-First Transcription Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for native implementation and a fresh whole-branch review. Track checkbox steps and preserve the execution ledger.

**Goal:** Let the user-validated Ubuntu recorder transcribe locally through a separate CPU container and display/copy the result; retain the completed OpenRouter adapter as an explicit alternative.

**Architecture:** Extend the desktop prototype with small standard-library modules for development configuration, HTTPS transcription and a cancellable background job. GTK owns display state and rejects stale job results. This is the next bounded slice of the approved cloud-first dictation design, not production meetings or a full application rewrite.

**Tech Stack:** Python 3.12, existing GTK4/GStreamer, stdlib HTTPS/JSON/threading/unittest.

**Spec:** plans/active/ubuntu-multiplatform-design.md; user confirmed recordings work and explicitly requested proceeding with the configured OpenRouter environment on 2026-11-05.

## Scope update — 2026-11-05

User requested: “probier erst mit einer localen variante es auch zu loesen, also einen extra container”. Local transcription now takes priority over the original cloud-first development slice. Implement a dedicated faster-whisper 1.2.1 container with multilingual base, CPU INT8, a model pinned to revision ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66, and host binding 127.0.0.1:8765. No automatic cloud fallback and no OpenRouter live request. The API's availability has not been tested; do not claim it failed.

Default TRANSCRIPTION_PROVIDER=local. Optional local URL/model settings; remote mode requires explicit TRANSCRIPTION_PROVIDER=openrouter plus its existing key/model. Do not change the user's real env file. Runtime model loads are offline; build downloads packages/weights. Use a build context limited to service files, without credentials, and host-loopback-only port publication. Docker Desktop did not publish the port on an internal network; runtime model loading is offline through local_files_only and HF_HUB_OFFLINE, not an egress firewall.

## Global constraints

- Use the existing native execution preference. The user's “mache weiter, env is geaendert” authorizes this slice; no repeated scope approval.
- Read env/.env as development input only. Never copy/commit the real file, print keys, source it as shell code, or fall back to GENERATION_MODEL for audio.
- Keep OPENROUTER_API_KEY and OPENROUTER_TRANSCRIPTION_MODEL separate for explicit cloud mode; local mode needs neither. The public local model revision and faster-whisper version were checked against primary sources.
- No request on launch, Stop, or playback. The explicit Transcribe recording button identifies the selected local/cloud provider.
- Keep all network/file processing off the GTK loop. Cancel/timeout invalidate queued callbacks, attempt to close the connection and preserve the completed recording for retry.
- Reject oversized/invalid WAV and recordings longer than five minutes. Long-meeting segmentation is a later slice; do not silently truncate.
- UI remains English with German translations. No automatic clipboard writes or transcript logging.
- No new third-party Python dependency. No Mac runtime or workflow edits.

## Review focus

1. Malicious/malformed env lines must never execute code or expose credentials: Task 1.
2. HTTP errors, redirects, malformed/large/empty responses must yield fixed redacted errors: Task 2.
3. Cancel before upload, timeout and callbacks delivered after cancellation/new jobs must not update UI or clipboard: Tasks 2–3.
4. New recording/playback/delete/quit while transcribing must preserve audio and respect state: Task 3.
5. Worktree launch must use the user's main-checkout env without copying secrets: Tasks 1/3/4.

## Task 1: Development configuration

Files: create apps/linux/prototype/transcription_config.py and tests/test_transcription_config.py; create env/.env.example containing placeholders only.

Produces load_config(env_file: Path | None = None) -> TranscriptionConfig, with api_key excluded from repr, explicit model and fixed ConfigError messages.

- [x] Test simple/quoted/export assignments, process-env precedence, missing file/key/model, invalid syntax, no shell interpolation/execution and secret-free repr/errors. Watch failure before implementation.
- [x] Implement a bounded simple KEY=value parser; only process-environment or explicit/local development env input. Reject control characters in keys/model and invalid model slugs.
- [x] Run the full Linux suite and commit configuration independently.

## Task 2: HTTPS adapter and background lifecycle

Files: create openrouter_transcription.py, transcription_job.py and their tests under apps/linux/prototype/.

Produces transcribe(path, config, cancelled, attach_connection) -> str; TranscriptionError.code/message; TranscriptionJob.start()/cancel() with dispatch(callback) and done(job,text,error).

- [x] Test real WAV validation, base64 JSON and Bearer request shape against an injected fake connection; no live requests in unit tests.
- [x] Test 401/402/403/429/5xx, redirects, invalid/empty JSON/text, response/audio size caps, five-minute duration cap, socket timeout, cancellation before request and connection cleanup. Errors must exclude provider body/key.
- [x] Test success, cancellation, queued-result suppression, deadline and background completion using deterministic events. Use a 65-second overall UI deadline and bounded socket operations.
- [x] Implement only the official fixed HTTPS endpoint https://openrouter.ai/api/v1/audio/transcriptions, with no redirects or automatic retries.
- [x] Run all Linux tests and commit.

## Task 3: Local CPU service and provider selection

Files: compose.local.yaml; apps/linux/services/transcription/{Dockerfile,requirements.txt,server.py,.dockerignore}; scripts/linux/start-local-transcription.sh; adapt transcription_config.py, transcription client/job imports and their tests.

- [x] Test default local mode without credentials, explicit cloud selection, loopback-only URL validation and local request shape before implementation.
- [x] Test the service with a fake model: request validation, health, model matching, WAV caps, serialized inference, origin/content-type checks and fixed errors. Tests must not download a model.
- [x] Build a JSON audio/text service using stdlib HTTP plus pinned faster-whisper. Bind only host loopback, run as a non-root user, enforce runtime offline model loading and keep audio in memory.
- [x] Reuse bounded WAV/JSON client logic for both providers, with no cloud Authorization header in local mode and no redirects/retries.
- [x] Run all Linux tests; commit container and local backend separately.

## Task 4: GTK transcription workflow

Files: modify desktop_demo.py, tests/test_demo_lifecycle.py, po/de.po and scripts/linux/run-prototype.sh.

- [x] Add headless regression tests for active-operation rejection, cancel preserving audio, stale result rejection and explicit copy only. Keep existing deferred-recording tests.
- [x] Add a read-only transcript area, provider-specific Transcribe recording and Copy transcript controls. Make content scrollable and disclose local container vs explicit cloud mode.
- [x] Integrate background jobs with GTK dispatch, identity-checked callbacks and a single active operation. Clear old text only when starting a new recording; preserve the recording on errors/cancel.
- [x] Resolve the development env in the main checkout via Git common dir in the run wrapper; explicit WHISPER_SHORTCUT_ENV_FILE/process env overrides remain possible. Never source the file.
- [x] Run full headless tests, shell/Python checks, English/German rendering, then commit.

## Task 5: Live validation, documentation and delivery

Files: update prototype README, platform commands, desktop evidence and design implementation status; add a validation report with verbatim output.

- [x] Start/restart only after confirming no recording is interrupted. User already confirmed the old window closed.
- [x] Build/start the separate container and validate a short public/synthetic speech fixture locally. Verify UI text display/copy with that fixture. Do not make a cloud request or upload existing personal recordings automatically.
- [x] Record actual provider outcomes, not inferred success. Verify no secret/audio/transcript artifacts are staged.
- [x] Independent whole-branch review; fix Important/Critical findings with regression tests; run full checks.
- [ ] Commit explicit files, push feature branch, create draft PR, report actual checks and remaining prototype limitations. Never merge or release.

## References verified

- https://openrouter.ai/blog/tutorials/transcription-on-openrouter/
- https://openrouter.ai/openai/whisper-large-v3-turbo

User-confirmed recording functionality is sufficient to implement this short-WAV
slice. System-audio mixing/headphone edge cases, keyring UI, production recovery,
chat and read-aloud remain separate work; this slice does not grade them complete.

Local implementation references: https://github.com/SYSTRAN/faster-whisper and https://huggingface.co/Systran/faster-whisper-base.
