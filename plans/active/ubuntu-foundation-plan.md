# Ubuntu Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the fork's development workflow safe on Ubuntu and validate the desktop integrations needed by its four initial features.

**Architecture:** Keep the working macOS application in place while removing active dependencies on the original maintainer's agent infrastructure. Build a clearly labeled desktop prototype, not a production application, to validate GTK4, audio, clipboard and shortcuts before choosing the final Linux adapters. Detailed feature implementation plans follow the measured prototype results.

**Tech Stack:** Existing Swift/Xcode application; Python 3.12, PyGObject/GTK4, GStreamer, libsecret, D-Bus desktop portals; GitHub Actions.

**Spec:** `plans/active/ubuntu-multiplatform-design.md`, approved by the user on 2026-11-04 and merged in PR #1 (`a31877b6`).

## Execution status (2026-11-04)

Tasks 1–3 are committed and verified. Task 4 prototype and English/German window
checks are implemented; manual audio, keyring, clipboard and shortcut validation
await user results. Task 5 CI/checks are implemented; final adapter adoption stays
conditional on Task 4. Task 6 is deferred because no authorized Mac runtime is
available. See docs/development/ubuntu-desktop-prototype.md for actual evidence.

## Global Constraints

- "Never stop an active recording to rebuild, restart, or update an application."
- "The first usable Ubuntu release includes dictation, chat, read-aloud, and meeting transcription."
- "Use cloud APIs initially."
- "All UI copy has English and German translations, retaining the existing language policy."
- "Never store keys in ordinary settings, transcripts, or logs, and do not silently fall back to plaintext when the keyring is locked or unavailable."
- "Treat automatic insertion into other applications as optional."
- "Stage the Linux app alongside the existing layout if Mac CI is unavailable; defer the Mac move until it can be verified." Ubuntu checks never count as Mac verification.
- Preserve LICENSE, attribution and history. Do not create permanent OS branches or an empty `shared/` abstraction.
- This phase contains no live provider calls, model-ID choices, OAuth, telemetry or releases.
- Ubuntu target: 24.04, GNOME/Wayland; system Python is `/usr/bin/python3` (3.12 measured locally).
- Gate final GTK/audio adoption on the prototype. Missing dependencies or session permissions are recorded as blocked checks, not failures of the selected technology and not passing checks.

## Review Focus

1. Linux agent hooks must not invoke Mac process-management commands: Task 2 inspects settings and runs platform guards with fake command sentinels.
2. A missing or old portal must result in a documented shortcut fallback: Task 4 records interface versions and tests the fallback from another focused app.
3. Headphones, missing monitor sources and disconnected devices must not yield a falsely successful meeting recording: Task 4 listens back to both tracks and records failures explicitly.
4. Closing the GTK window must not silently break clipboard or shortcut activation: Task 4 tests background lifetime and single-instance behavior.
5. Prototype output must not leak audio or credentials into Git/CI artifacts: Tasks 3 and 5 check redaction and use ignored temporary storage.

## Phase boundaries

This is the executable plan for foundation work only. Production feature plans
must be written after the evidence report settles desktop interfaces. Do not
invent final provider interfaces before reading current provider documentation.
The approved four-feature scope is retained in the continuation map below.

## Task 1: Record the dependency inventory

**Files:** Create `docs/development/fork-tooling-inventory.md`.

**Interfaces:** Consumes tracked files and actual references; produces a path-by-path keep/remove/adapt table, with callers and reasons. No executable changes.

- [x] Inventory with `git ls-files .agents .claude .cursor scripts plans .github` and `rg -n --hidden --glob '!.git/**' --glob '!.claude/worktrees/**' 'agent-loops|implementer|review-growth|ensure-app-running|\.agents/skills|\.cursor/commands' .`.
- [x] Record every tracked agent setting/symlink and scheduled entry point. List script sources, macOS CI callers, and in-app consumers before marking anything removable. Distinguish runtime use of project skills from original-owner automation.
- [x] Keep original ledgers and gate definitions unchanged; label historical automation as inactive in the inventory. No grading or weakening of an existing loop's gates is part of this migration.
- [x] Enumerate the Mac relocation set: `WhisperShortcut/`, `WhisperShortcutTests/`, `WhisperShortcut.xcodeproj/`, both `.xctestplan` files and export-options plist. List dependent scripts, lockfile ignore exceptions, README bundling and workflow paths.
- [x] Verify each removal candidate has no retained caller. Treat documentation references as references to update, not proof of executable dependency. `git diff --check` must exit 0.
- [x] Commit only the new inventory: `docs: inventory fork tooling and platform dependencies`.

## Task 2: Make active contributor instructions platform-aware

**Files:** Modify `AGENTS.md`, `.cursor/rules/index.mdc`, `.cursor/rules/plan-vs-build-models.mdc`, `.cursor/CODEMAP.md`, `.cursor/CONTEXT-CONVENTIONS.md`, `.claude/settings.json`, `.github/workflows/release.yml`, `plans/active/ubuntu-multiplatform-design.md`; create `docs/development/platform-commands.md`; remove inventoried obsolete maintainer-only skill/command entry points only after their callers are detached.

**Interfaces:** Produces one canonical fork-owned contributor guide; editor aliases refer to it; original Mac development commands continue to resolve. Does not change either distribution's runtime identity or loop gate definitions.

- [x] Mark the design approved, recording the user's approval date and merged PR. Do not rewrite the approved scope.
- [x] Replace contributor rules with concise build/run/test routing, privacy, recording protection, explicit-path Git staging, and platform verification requirements. Remove owner-specific model mandates, external session handovers and mandatory loop/queue participation from the fork's active instructions. Keep user mentoring requirements.
- [x] Reduce Cursor rules to a pointer to canonical rules and any necessary editor metadata; remove the obsolete model-tier rule. Adapt the code map to identify current Mac paths and the prototype path. Retain `CLAUDE.md` and valid aliases only when useful.
- [x] Remove the unconditional `ensure-app-running.sh` Stop hook and inherited release permissions from tracked Claude settings. Do not modify personal settings or credentials.
- [x] Remove automatic tag-push release triggers; leave manual release dispatch guarded with a repository variable `FORK_RELEASES_ENABLED == 'true'` on every job that publishes, uploads, signs, promotes or mutates releases. Document that the variable remains unset. Do not enable it. Keep secret-free Mac verification CI.
- [x] Detach obsolete scheduled launch/install entry points identified in Task 1 from the active workflow. Do not uninstall host jobs, delete active worktrees, or bulk-delete `.agents`; adapt or retain application-relevant skills. Inactive historical scripts/ledgers can stay until the Mac path migration safely archives them.
- [x] Validate JSON settings with `/usr/bin/python3 -m json.tool .claude/settings.json`; inspect symlink targets with `git ls-files -s .claude CLAUDE.md`; verify no retained active rule requires an external deployment session or original-owner model selection. Check the workflow's trigger/job changes directly and record the diff.
- [x] Run `git diff --check`. Commit the instruction/automation changes separately: `chore: adapt fork tooling for macOS and Ubuntu`.

## Task 3: Add a reproducible desktop capability probe

**Files:** Create `scripts/linux/probe-desktop.sh`, `scripts/linux/test.sh`, `apps/linux/prototype/README.md`, `apps/linux/prototype/desktop_probe.py`, `apps/linux/prototype/tests/test_probe_report.py`; modify `.gitignore` for prototype outputs.

**Interfaces:** `desktop_probe.py --json` produces a versioned, redacted JSON report on stdout; exit 0 means the report was generated, not that every capability passed. Report fields: `schema_version: 1`, `platform`, `session_type`, `desktop`, `dependencies` and `capabilities`; each capability contains `status` (`available`, `unavailable`, `blocked`, `untested`) and `reason`. The shell wrapper forwards arguments and status. No recording or GUI launch without an explicit command.

- [x] Write `test_report_schema`, `test_missing_dependency_is_unavailable`, `test_missing_session_bus_is_blocked`, and `test_report_contains_no_environment_values_or_device_identifiers`. Assertions pin schema version 1, status values, and absence of home paths, credentials, transcript content and full environment dumps.
- [x] Run `/usr/bin/python3 -m unittest discover -s apps/linux/prototype/tests -v`; confirm failures before implementing the report functions.
- [x] Implement `collect_report() -> dict` and `main(argv: list[str] | None = None) -> int` using only standard Python for headless reporting. Probe GI/GTK/GStreamer/libsecret availability without importing a missing module at module load time; bound external command execution to 5 seconds and handle nonzero statuses explicitly.
- [x] Report portal interfaces/versions through the current session bus when reachable. Separate tool presence, interface presence and manually demonstrated functionality; never infer shortcut/audio success merely from installed packages.
- [x] Document Ubuntu package installation as an explicit setup step using distro packages for GI and media components. Do not silently run apt, use sudo or replace system Python. Keep recordings/reports outside Git (temporary directory or ignored prototype output directory).
- [x] Make `scripts/linux/test.sh` run unittest discovery and preserve the real exit status. Run it and the JSON probe, inspect the full report, then commit: `feat: add Ubuntu desktop capability probe`.

## Task 4: Validate GTK, audio, secrets and shortcuts interactively

**Files:** Create `apps/linux/prototype/desktop_demo.py`, `apps/linux/prototype/po/de.po`, `scripts/linux/run-prototype.sh`, `docs/development/ubuntu-desktop-prototype.md`; extend the prototype README.

**Interfaces:** `desktop_demo.py` uses GTK's single-instance application ID `io.github.Xchosa.WhisperShortcut.Prototype`; `--toggle-recording` requests an action on that instance. Explicit window controls initiate microphone or microphone-plus-system tests, playback, clipboard copy and shortcut registration. This is disposable prototype code, not an endorsed final public application ID/API.

- [ ] Use current official GTK/PyGObject, GStreamer, libsecret and portal documentation. List exact installed package/plugin versions and consulted documentation in the report. Do not assume ScreenCast provides system-audio capture.
- [ ] Implement a minimal GTK4 window with English/German labels and explicit user-triggered recording. Keep processing off the GTK main loop; store prototype audio only in temporary storage. Stop read-aloud/playback before starting capture; permit only one capture at a time.
- [ ] Test microphone start/stop/cancel and playback. For system capture, enumerate available monitor/loopback sources, record microphone and system audio independently before testing a mix, and listen to prove both sources are present. Capture only after explicit user action; if interactive access/approval is required, leave that check pending and ask the user for that specific action.
- [ ] Test silence, missing device, disconnection and headphones. Record exact symptoms, commands and outcomes. Never label a silent recording successful or ask for privileged input injection to bypass Wayland restrictions.
- [ ] Test a synthetic, disposable libsecret value with asynchronous store/read/delete. Remove the test item in cleanup. Test cancellation of unlock; never query real provider keys or print secret values. Report locked/unavailable service as a handled condition.
- [ ] Try portal shortcut registration, including cancellation/denial. If unavailable, document GNOME Settings custom-shortcut setup invoking the single-instance action. Activate from another focused application and confirm a second process does not create a second recorder.
- [ ] Copy a harmless known string, close the main window, paste into another application, and verify background action activation. Provide explicit Quit that finalizes capture. Record which lifetime strategy worked; do not assume clipboard survives application exit.
- [ ] Write an evidence table with observed result, expected result, status and limitation for every check. Evidence must cover at least GTK launch, responsive UI, microphone, system audio, combined audio, clipboard lifetime, shortcuts, single instance and keyring behavior.
- [ ] End with a measured GTK/audio decision: adopt if the required integrations work, or identify concrete blockers and fallback experiments. Update the design only to record findings; obtain user direction for a material scope/toolkit change. Commit: `docs: record Ubuntu desktop integration prototype results` (include prototype files explicitly).

## Task 5: Establish Linux checks and the next implementation boundary

**Files:** Modify `.github/workflows/ci.yml`, `docs/development/platform-commands.md`; create `docs/architecture/linux-foundation.md`.

**Interfaces:** Linux CI runs the deterministic probe tests on Ubuntu 24.04, without desktop/session secrets. Mac CI retains its original two-variant coverage and root paths until Task 6 can be verified. No recording, desktop access or provider requests in CI.

- [ ] Add an Ubuntu 24.04 job that runs `bash scripts/linux/test.sh`. Do not skip missing imports silently; unit tests mock missing services deliberately and do not require GI. An unavailable desktop integration is not a CI success signal.
- [ ] Document exact probe/demo/test commands, optional OS dependencies, cloud-first scope and known limitations. Include English/German translation workflow and temporary audio cleanup.
- [ ] Run `bash scripts/linux/test.sh`, `/usr/bin/python3 -m compileall -q apps/linux/prototype`, `bash -n scripts/linux/probe-desktop.sh scripts/linux/run-prototype.sh scripts/linux/test.sh`, and `git diff --check`; all must exit 0. Verify no recordings, generated bytecode or secret values are staged.
- [ ] Record accepted adapters and operation/lifecycle policy in the architecture document, using actual Task 4 results. Do not represent unresolved system audio as meeting support.
- [ ] Commit: `ci: check Ubuntu foundation alongside macOS`.

## Task 6: Relocate the Mac app only with platform verification

**Files:** The Task 1 relocation manifest; `scripts/macos/`; temporary wrappers at `scripts/rebuild-and-restart.sh`, `scripts/run-tests.sh`; `.github/workflows/ci.yml`; `.gitignore`; `package.json`; `README.md`; retained Mac tooling and docs.

**Interfaces:** Public compatibility commands keep their flags and exit statuses. The Xcode project stays alongside its source/test directories inside `apps/macos/`. Shared developer commands choose the host OS before running platform-specific code.

- [ ] If Mac CI cannot be run or an authorized Mac smoke test is unavailable, record this task as deferred and continue Linux production work alongside the existing Mac root. No simulated Mac success.
- [ ] When available, write a focused relocation plan from the manifest before executing the move. Include scheme/test-plan references, package cache/lockfile paths, README sync, export options, signing scripts and original worktree-sidecar behavior.
- [ ] Use `git mv` and explicit path lists. Root compatibility wrappers must resolve the repository path independently of caller cwd, forward `"$@"`, and `exec` the proper platform command. On Linux, unsupported Mac commands return a clear diagnostic without invoking macOS tools.
- [ ] Verify wrapper forwarding and cwd independence with fake command sentinels; verify the Linux guard never invokes `osascript`, `security`, `open`, `pkill` or `xcodebuild`.
- [ ] Run Mac hermetic tests and compile both direct and App Store schemes. Run authorized Mac rebuild/relaunch and smoke test with meeting protection. Quote actual test output and record exit statuses.
- [ ] Commit the verified move separately from README/agent cleanup. Keep the approved target layout documented until the move is complete.

## Continuation map: production feature plans

These are subsequent plan boundaries, not implementation permission to skip the
prototype or invent unspecified provider adapters. Prepare each plan against the
measured architecture before writing its production code.

1. **Linux shell and dictation:** `apps/linux/pyproject.toml`, `src/whisper_shortcut/`, tests, desktop entry and repeatable setup/run/test scripts. App identity, GTK shell, bilingual UI, operation coordination, background/single-instance behavior, XDG settings, libsecret credentials, recording, provider transcription and clipboard. Tests cover missing/locked keyring, denied microphone, network deadlines, cancel/restart races and no stale clipboard writes. Check current provider/model documentation first.
2. **Chat:** versioned SQLite sessions, messages, streaming turn updates and cancellation. Tests cover restart persistence, interrupted replies, malformed/partial stream events, provider errors without losing input, deletion and migration failure preserving the original database. Chat remains usable during capture.
3. **Read-aloud:** explicit pasted/entered text, cloud synthesis, playback and prompt cancellation. Tests cover empty input, failed synthesis, output-device loss and stopping playback before any recording starts. No implicit selection capture.
4. **Meeting transcription:** microphone plus validated system source, visible elapsed recording state, recoverable segments at most five seconds long, ordered post-stop provider-sized chunks, partial progress, per-chunk retry, export and deletion. A forced process-crash test must lose at most the unfinished final five seconds. Preserve audio needed for recovery until successful transcription or explicit deletion; never silently label microphone-only capture as complete meeting support.
5. **Final integration:** actual GNOME/Wayland end-to-end walkthrough for all four features, bilingual copy check, deletion/recovery/cancellation verification, network-content/log audit, development installation and desktop launch. Confirm no inherited telemetry/update/release endpoint is enabled. Packaging and automatic releases remain separate decisions.

## Plan self-review

- Scope: foundation tasks cover agent cleanup, release safety, capability gates and CI. The continuation map carries every four-feature acceptance requirement and the five-second recovery target into subsequent plans.
- Boundaries: the prototype is explicitly temporary; no production toolkit lock or provider IDs are selected before evidence.
- Interface consistency: scripts use `/usr/bin/python3`; report schema and CLI exits distinguish measured availability from test success; GUI activation uses one prototype app ID.
- Review focus: each listed failure condition has an explicit validation step in its owning task.
- Platform honesty: Mac relocation is deferred unless both CI and authorized runtime verification are available.

## Execution preference

Recommend native execution in this session for Tasks 1–5: the inventory and
prototype findings drive the next task, so keeping those decisions in one
context avoids duplicated investigation. Independent whole-change review follows
implementation. User review of this plan and execution-method selection are the
remaining workflow step; no additional product-scope decisions are requested.
