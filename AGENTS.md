# WhisperShortcut fork — contributor guide

This fork maintains macOS and Ubuntu applications in one repository. This file
is the canonical project guide; editor settings and optional skills defer to it.

## Layout and scope

- macOS currently remains in `WhisperShortcut/`, `WhisperShortcutTests/` and
  `WhisperShortcut.xcodeproj/`. Move it to `apps/macos/` only with Mac verification.
- Ubuntu integration prototype: `apps/linux/prototype/`. It is not the full app.
- Platform scripts: `scripts/linux/`; existing root scripts are macOS tooling.
- Approved design and plan: `plans/active/ubuntu-multiplatform-design.md` and
  `plans/active/ubuntu-foundation-plan.md`.
- Dependency inventory: `docs/development/fork-tooling-inventory.md`.

## Build, run and verify

- Linux: `bash scripts/linux/probe-desktop.sh --json`,
  `bash scripts/linux/run-prototype.sh`, `bash scripts/linux/test.sh`.
  See `docs/development/platform-commands.md` for dependencies and current status.
- macOS only: `bash scripts/rebuild-and-restart.sh` builds and relaunches;
  `bash scripts/run-tests.sh --hermetic` runs offline tests. Preserve the
  meeting guard and worktree sidecars. Ubuntu cannot verify Xcode builds.
- Never stop an active recording to rebuild/restart/update. Ask the user to stop
  recording first if a required restart would interrupt it.
- Run relevant checks yourself; quote actual test output and report exit status.
  Do not pipe status-deciding commands through output filters. Missing desktop
  services and platform-blocked checks are unverified, never passing.
- Keep desktop integration tests separate from headless unit tests; installed
  libraries or portal interfaces do not prove working audio or shortcuts.

## Engineering and privacy

- Keep UI, use cases and platform adapters separate. Keep work small and readable.
- Keep GTK work on its main loop and blocking I/O off it. Support cancellation,
  deadlines, cleanup, and one capture at a time. Do not assume X11 automation
  works under Wayland. Clipboard/manual paste is the baseline.
- Never start recording without explicit user action. Do not write keys, audio,
  chat or transcripts to Git or diagnostic logs. Use Secret Service for Linux
  credentials, with no plaintext fallback; use XDG application data locations.
- UI source language is English; include German translations for changed copy.
  Internal logs and code identifiers stay English.
- Mac state flows through AppState; Mac instrumentation uses DebugLogger.
  Linux uses structured Python logging with content/credential redaction.
- Read current official provider documentation before changing provider calls or
  model IDs. There are no live provider calls in the desktop prototype.
- Explain significant design choices and give concise technical learnings after
  meaningful implementation or debugging; do not interrupt routine work to teach.

## Git and delivery

- Use short-lived feature branches and isolated worktrees. Never switch the
  user's main checkout, stash/reset others' work, or stage paths you did not edit.
- Stage explicit paths; never `git add .`, `git add -A` or `git commit -a`.
- Commit verified changes, push your feature branch and open a PR when authorized
  by the task. Do not merge, tag or release as part of ordinary implementation.
- Keep shared instruction changes in a separate commit and disclose them.
- Changes to signing, app identity, telemetry or update endpoints require explicit
  scope. Do not silently rewrite the existing Mac runtime identity.

## Optional historical tooling

Original-maintainer scheduled jobs, model policies, release sessions and ledgers
are not part of this fork's workflow. Scheduled entry points refuse execution;
release CI is manual and disabled unless intentionally configured. Never install
host jobs, send reports, spend provider credentials or enable releases merely
because an inherited skill says so. Existing ledger/gate content is historical
and must not be weakened or regraded by migration work.

Retained `.agents/skills/` and `.cursor/commands/` are optional playbooks, mostly
for the Mac app. Apply only relevant technical guidance; this guide and the
user's instructions take precedence over inherited owner-specific commands.
Personal agent settings belong outside Git. No specific AI model or external
agent session is required to work on this fork.
