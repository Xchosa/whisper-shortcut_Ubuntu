# Linux foundation and adoption gates

The approved design is in plans/active/ubuntu-multiplatform-design.md. The current
Linux directory contains an integration prototype, not the released app.

## Boundaries established

- One repository, separate native apps. Preserve the Mac root until verified
  relocation; add Linux independently. No empty shared runtime.
- GTK4/PyGObject window rendering is demonstrated on Ubuntu 24.04/Wayland.
  GStreamer audio, Secret Service credentials, clipboard and single-instance
  shortcut activation remain candidates pending functional evidence.
- Use asynchronous service APIs, worker-side discovery and GTK main-loop UI
  updates. One audio capture at a time; stop playback before capture.
- Background running is opt-in. Close hides only when enabled; Quit is explicit.
  Recording must stop/cancel before window close or exit.
- The absent GlobalShortcuts interface requires the documented GNOME custom
  shortcut fallback. No automatic keystroke injection or privileged input tool.
- No provider, model ID, API key, telemetry, update endpoint or production data
  schema is selected by the prototype. No packages are silently installed.

## Verification boundary

Headless tests exercise probe reporting/redaction/timeouts and historical job
guards. GUI smoke tests establish rendering/main-loop behavior only. Real
recording/listening, keyring cancellation, cross-app clipboard and shortcut
activation are separate checks listed in the prototype evidence report.

Do not lock production adapters or label meeting capture usable before those
checks pass. Missing system capture requires a concrete blocker report, never
an implicit microphone-only substitute. Future production plans cover provider
limits, cancellation races, SQLite persistence and five-second recovery.

## Next step

Finish the manual evidence table, then prepare the production shell/dictation
plan against demonstrated adapters. Chat, read-aloud and meeting transcription
remain part of the first usable release and follow the foundation plan's
continuation map.
