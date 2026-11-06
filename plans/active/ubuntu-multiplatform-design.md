# macOS and Ubuntu repository design

Status: APPROVED — user approval on 2026-11-04; merged in PR #1. Foundation implementation plan: `plans/active/ubuntu-foundation-plan.md`.
Date: 2026-11-04

## Intent and agreed scope

Maintain separate native macOS and Ubuntu applications in one repository. Use
short-lived feature branches rather than permanent operating-system branches.
The first usable Ubuntu release includes dictation, chat, read-aloud, and meeting
transcription. Implement these incrementally, with dictation first. Preserve the
existing macOS application and AGPL licensing and attribution.

The user selected this repository approach and accepted the proposed defaults.
The technology choices and detailed acceptance criteria below are engineering
proposals, not claims of additional user approval.

## Current constraints

- The existing app is an Xcode project, not a portable Swift package. UI, audio,
  permissions, shortcuts, credentials, and local inference depend on Apple APIs.
- The development machine is Ubuntu 24.04 with GNOME on Wayland. It cannot run
  Xcode builds or establish that the macOS app still works.
- Existing build scripts, CI paths, bundled documentation, skills, and release
  workflows assume the original root layout and maintainer's infrastructure.
- Preserve historical commits. Moving files does not remove their Git history.
- Never stop an active recording to rebuild, restart, or update an application.

## Approaches considered

1. One repository with native platform applications (selected): clear platform
   ownership, one issue/history location, and opportunities to share contracts.
   Costs include duplicated implementations and maintaining two build systems.
2. Separate Ubuntu repository: simpler local scope, but adds synchronization and
   makes upstream behavior comparisons harder.
3. Rewrite both apps around a shared runtime/UI: potentially more shared code,
   but replaces a working Mac application and greatly expands the initial task.

## Target layout

```text
apps/
  macos/                  # Swift sources, Xcode project, test plans and tests
  linux/                  # Linux package, UI, services and tests
docs/
  architecture/
  development/
scripts/
  macos/
  linux/
AGENTS.md
README.md
LICENSE
```

Create `shared/` only when both applications consume concrete assets, fixtures,
or specifications. Do not introduce an empty shared framework. Keep repository
CI in `.github/workflows/`. A small `.agents/skills/` may remain for genuinely
project-specific workflows; it is development tooling, not application code.

Migrate in separate commits: fork instructions and automation cleanup; macOS
path moves plus their dependent references; Linux foundation; individual Linux
features. Temporary root wrappers may keep existing Mac commands usable during
the transition. Never claim that file moves preserve runtime behavior without
running Mac verification. Stage the Linux app alongside the existing layout if
Mac CI is unavailable; defer the Mac move until it can be verified.

## Linux architecture (proposed)

Use Python with GTK4 through PyGObject as the initial candidate for an
Ubuntu-focused native UI. A bounded integration prototype must validate the
choice before a production scaffold or dependency lock is committed. A failed
prototype triggers a revised design, not silent changes of toolkit.

Separate application use cases from adapters for recording/playback, providers,
clipboard, shortcuts, credential storage and persistence. Keep modules small;
do not create a generic plugin framework. UI updates run on GTK's main loop;
networking and expensive processing must not block it. Operations have explicit
state, cancellation, deadlines, and cleanup. Provider-specific details stay out
of widgets. Use structured Python logging with secret/content redaction.

First-version compatibility rules: one audio capture at a time; dictation cannot
overlap a meeting; read-aloud cannot overlap capture and must stop before capture
starts. Chat remains available during recording. Closing the main window keeps
an explicitly enabled background service alive for shortcuts; Quit is distinct,
warns about active recording, and finalizes data before exit. Use a single app
instance so shortcut activation cannot start competing audio sessions. All UI
copy has English and German translations, retaining the existing language policy.

Use cloud APIs initially. Implement one validated provider path for each use
case before expanding provider coverage. Choose provider IDs and request formats
from current official documentation during implementation, not this document.
Offline inference, Dictate Prompt, calendar/email/Trello tools, MCP, speaker
diarization, and exact Mac feature parity are outside this initial milestone.

Use the desktop Secret Service via libsecret for provider keys. Never store keys
in ordinary settings, transcripts, or logs, and do not silently fall back to
plaintext when the keyring is locked or unavailable. Use XDG locations for
configuration, persistent application state and disposable caches. Create a
distinct fork application identity before introducing OAuth, updates or telemetry.

Persist chat and transcript metadata in a versioned SQLite database; keep audio
as separate files only while necessary. Save settings as a small versioned file.
Migration errors must preserve original data. Default to retaining transcripts
and deleting temporary audio after successful processing; provide explicit
failure recovery and user-controlled deletion. Raw transcript/chat logging and
telemetry are off by default. Recording controls explain cloud processing before
first use; capture starts only by explicit user action.

## Desktop integration prototype

Validate on this machine, recording outcomes rather than assuming support:

- GTK window launch, main-loop responsiveness and clipboard ownership, including
  behavior after closing the main window.
- Microphone recording and playback with device selection, visible errors and
  clean stop/cancel. Evaluate GStreamer as the audio adapter.
- Query available portal interfaces and versions; test shortcut registration and
  activation while another application has focus. If unavailable, test a GNOME
  user-configured shortcut invoking the app's single-instance command endpoint.
- Validate system playback capture through available audio devices/monitor
  sources and permissions. A screenshot/screencast portal alone does not prove
  that meeting audio can be captured. Test microphone and system sound together,
  headphones, silence, disconnection and prevention of duplicate audio/feedback.
- Treat automatic insertion into other applications as optional. Clipboard plus
  manual paste is the supported baseline; do not assume X11 automation works on
  Wayland or require root privileges to synthesize keystrokes.

If system capture is unavailable, microphone-only recording is an explicitly
labeled fallback. It does not satisfy the full system-audio meeting acceptance
criterion. Document the blocker before calling the milestone complete.

## Feature acceptance criteria

### Dictation

Record/stop/cancel visibly; transcribe through a configured cloud provider; copy
the result with a clear success indication. Handle missing keys, denied audio,
network failure and cancellation without stale results. No new recording starts
while an incompatible operation is active. Global activation works through the
validated portal or documented GNOME shortcut fallback.

### Chat

Create/reopen/delete conversations, send messages, display incremental replies
when supported, and cancel a response. Preserve completed turns across restart;
mark interrupted responses. Report provider failures without losing user input.
Tools, attachments and automatic Mac-history import are deferred.

### Read-aloud

Read entered or explicitly pasted text, stop playback promptly, and recover from
provider/audio errors. Initial scope uses cloud speech; automatically reading
another application's selection is deferred. Playback must not accidentally feed
back into an active meeting capture.

### Meeting transcription

Record microphone and system sound using the validated adapter, with an obvious
recording indicator, elapsed time and explicit stop. Persist recoverable audio
segments and session metadata during capture, transcribe after stop, and allow
retry/export/delete. Survive interruption without silently losing the entire
meeting. Continuous live transcript streaming is deferred. Show retention and
cloud-processing behavior before recording.

Persist completed capture segments at intervals of at most five seconds; test
forced process termination with a target of losing at most the unfinished final
five seconds. This target covers application crashes, not a guarantee against
hardware/power failure. After stop, subdivide audio to the validated provider's
duration/size limits, preserve chronological order, report partial progress and
retry failed segments individually without retranscribing completed segments.

## Agent and automation cleanup

Replace inherited agent instructions with concise fork-owned rules: platform
commands, code locations, tests, privacy, recording protection and Git safety.
Remove original-owner model mandates, deployment-session dependencies, scheduled
loops and queues from the active workflow after tracing references. Preserve any
useful historical material under clearly labeled documentation rather than
presenting it as active work. User-level personal instructions live outside Git.

Review `.cursor`, `.claude`, `.agents`, `plans`, scheduled scripts and GitHub
workflows by dependency, not blanket deletion. Keep useful shared rules in one
canonical file; retain compatibility aliases only if they are actually used.
Each shared-instruction change is a separate disclosed commit. Never copy
personal keys, machine paths or local settings into the new structure.

Disable inherited automatic release triggers in the first cleanup commit and
keep automatic releases disabled for the fork until its identity, signing,
destinations and approval policy are intentionally configured. No inherited
telemetry, updater URL or original-maintainer endpoint is enabled by accident.
Do not silently rewrite original Mac distribution identity as part of a move.

## Verification and delivery

- First, static checks identify every moved path, including Xcode references,
  test plans, SPM lockfile exceptions, scripts, workflows and bundled README paths.
- Mac CI runs the existing hermetic test plan and compiles both distribution
  variants. An authorized Mac environment performs rebuild/relaunch and a smoke
  test; local Ubuntu checks cannot substitute for these.
- Ubuntu CI runs deterministic unit tests for use cases, persistence/recovery,
  cancellation and provider error handling. Mock provider calls by default;
  keep opt-in live checks separate and secrets out of CI logs.
- An actual GNOME/Wayland session verifies microphone, system audio, shortcuts,
  clipboard and playback. Headless tests alone cannot establish integration.
- Provide a repeatable Linux setup/run/test command and a desktop entry before
  considering the app usable. Start with a development install; choose a release
  package only after the desktop prototype. Flatpak/container packaging is not
  assumed to preserve host audio and shortcut behavior.
- Report commands and real exit statuses. Platform-blocked checks remain
  explicitly unverified. Never report unexecuted tests as passing.

## Implementation order and open gates

1. Review this design with the user.
2. Produce a concrete implementation plan and audit fork automation dependencies.
3. Validate Linux desktop integrations; settle GTK/audio adapters from evidence.
4. Clean instructions and split paths with Mac verification where available.
5. Implement and validate dictation, chat, read-aloud and meeting transcription
   in that order. Keep every feature independently reviewable and runnable.
6. Complete integration checks and document supported capabilities/limitations.

No further user input is needed to prepare the implementation plan. Technical
unknowns require experiments; only a material scope change or a demonstrated
blocker should trigger another product decision.

## Official references consulted

- PyGObject GTK4 tutorial: https://pygobject.gnome.org/tutorials/gtk4/introduction.html
- XDG desktop portals: https://flatpak.github.io/xdg-desktop-portal/docs/
- Global shortcuts: https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html
- libsecret: https://gnome.pages.gitlab.gnome.org/libsecret/

These document APIs, not proof that this desktop implements every interface.

## Explicit user update — 2026-11-05

The user requested a separate small local speech-model container before cloud
transcription. The next implemented slice therefore defaults to local CPU/base
with optional, explicitly selected OpenRouter. This changes development ordering,
not the agreed four-feature scope or the separate native-platform structure.
The recording prototype now displays/copies transcripts. Production history,
recovery, long-meeting segmentation, chat and read-aloud remain later work.
