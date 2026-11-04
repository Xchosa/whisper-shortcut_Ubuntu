# Fork tooling inventory

Measured at base `98a0a653`, Ubuntu foundation work, 2026-11-04.
The macOS application still lives at the repository root. This inventory is a
dependency map, not proof of macOS runtime compatibility.

## Active contributor configuration

| Path | Callers / consumers | Decision |
|---|---|---|
| `AGENTS.md` | Agents, `CLAUDE.md` symlink, in-app workspace context loader | Adapt: canonical fork rules; remove original owner's infrastructure requirements |
| `CLAUDE.md` | Claude and workspace context | Keep symlink to `AGENTS.md` |
| `.cursor/rules/index.mdc` | Cursor always-on rule; previous AGENTS reference | Adapt to canonical-guide pointer |
| `.cursor/rules/plan-vs-build-models.mdc` | Cursor always-on rule | Remove: original owner's model policy |
| `.cursor/CODEMAP.md` | Contributor navigation | Adapt: Mac root and Linux prototype locations |
| `.cursor/CONTEXT-CONVENTIONS.md` | Contributor tooling documentation | Adapt: one canonical guide and historical workflow boundary |
| `.claude/settings.json` | Claude permissions and Stop hook | Remove unconditional Mac relaunch hook and release permission |
| `.claude/commands`, `.claude/rules`, `.claude/skills` | Editor aliases | Keep valid symlinks; edit targets |
| `.cursor/commands/{release,submit-appstore}.md` | Explicit slash-command invocation | Gate as historical: no authority to release this fork |
| `.cursor/commands/{audit-llm-models,competitor-teardown,improve-context,review-code}.md` | Explicit slash commands | Keep; canonical guide takes precedence over inherited owner references |

## Skills

All 16 tracked skill directories remain because scheduled scripts and in-app
workspace context can load them; removal is not required to stop their automatic
execution. They are optional historical playbooks, not standing authority.

| Skill under `.agents/skills/` | Consumer / applicability |
|---|---|
| `analyze-chat-freeze` | Mac chat diagnostics; implementer prompts reference it |
| `analyze-user-interactions` | Usage-review prompt and Mac usage logs |
| `audit-llm-context` | Explicit instruction audit |
| `debugging-workflow` | Mac instrumentation |
| `gemini-system-prompt-best-practices` | Provider prompt editing |
| `implement-proposal` | `scripts/implementer/run-implementer.sh` |
| `llm-model-docs` | Provider documentation lookup |
| `push-after-rebuild` | Mac build-and-push playbook; platform guide overrides Linux applicability |
| `review-agent-loops` | `scripts/agent-loops-job.sh` |
| `review-growth` | `scripts/growth-review-job.sh` |
| `review-llm-state-of-the-art` | Explicit architecture review |
| `review-refactors` | Explicit Mac refactor review |
| `run-whisper-shortcut` | Explicit Mac GUI walkthrough; includes `driver.sh` |
| `validate-audio-verification` | Mac Smart Improvement diagnostics |
| `view-logs-via-bash` | Mac log viewing |

The application consumer is `WhisperShortcut/WorkspaceContextFiles.swift`
(`skillDirectories` includes `.agents/skills`, `.cursor/skills`,
`.claude/skills`). Thus blanket deletion is inappropriate.

## Scheduled automation and distribution

| Paths | Dependency / effect | Decision |
|---|---|---|
| `.github/workflows/ci.yml` | root `scripts/run-tests.sh --hermetic`, root Xcode project and package lock | Keep Mac jobs; add independent Linux job |
| `.github/workflows/release.yml` | signing secrets, export plist, `scripts/make-appcast.py`, GitHub releases | Remove automatic tag trigger; gate all jobs behind disabled repository variable |
| `scripts/{agent-loops,growth-review,usage-review,model-audit}-job.sh` | skills/commands, `loop-prompt.sh`, `loop-commit.sh`, mail/report scripts, implementer proposals | Retain historical bodies; refuse execution in this fork |
| `scripts/{model-lineup-check,stable-promote-job}.sh` and their `.plist` templates | launchd, upstream models/releases | Retain templates; refuse executable job entry points |
| `scripts/implementer/` | tick→groom/run/release-merges; install scripts write host LaunchAgents/config | Gate execution/install/merge entry points; retain helpers and gate definitions |
| `scripts/merge-train/` | installer writes LaunchAgent; train merges branches | Gate installer and train entry points |
| `scripts/{create-release,promote-stable,export-certificate}.sh`, `install.sh` | explicit release, upstream install, credentials | Preserve for Mac history; historical docs grant no fork release authority; never run during migration |
| `plans/{agent-loops,implementer-queue,improvement-ledger,instrumentation-gaps,loop-ledger,refactor-ledger}.md` | original automation state | Historical; retain content and falsifier/gate values unchanged |
| `plans/model-audits/`, `plans/loop-reviews/`, `plans/implementer-plans/` | original reports/briefs | Historical; not instructions to execute |
| `scripts/operator_mail.py`, `send-report-mail.py`, report scripts | historical job dependencies | Retain; no message sending authorized by migration |

No host LaunchAgent installation/uninstallation is performed. The checkout is a
Linux fork; existing jobs on other machines are outside its authority.

## Mac runtime/build dependencies: retain

- `scripts/rebuild-and-restart.sh`, `run-tests.sh`, `ensure-app-running.sh`
  source `scripts/lib/{daily-app,build-lock}.sh`; keep these together.
- `meeting-guard.sh`, `worktree-remove.sh` and sidecar behavior protect running
  recordings/binaries. Do not substitute process-killing shortcuts.
- `scripts/{logs,reset-restart,reset-restart-logs,copy-release-data-to-dev,sync-strings}.sh`
  support Mac development; keep until a verified platform-script relocation.
- Mac tests/build CI rely on root Xcode paths; no Mac source or build-path change
  is needed to add the Linux prototype.
- `WhisperShortcut/Docs/README.md` is bundled/synced from root README by the Mac
  rebuild script. A root README rewrite would therefore change application content.

## Mac relocation manifest (deferred)

Move these as a unit under `apps/macos/` only with Mac verification:

- `WhisperShortcut/`, `WhisperShortcutTests/`, `WhisperShortcut.xcodeproj/`.
- `WhisperShortcut-AppStore.xctestplan`, `WhisperShortcut-Hermetic.xctestplan`.
- `exportOptions-release.plist`.

References requiring updates: project.pbxproj and shared schemes/test-plan
relative paths; `.gitignore` package-lock exception; workflow cache hashes and
Xcode commands; scripts' PROJECT_DIR/MAIN_ROOT, export paths and bundled README
copy; `package.json`; developer docs/skills; .github release setup docs. Keep
platform scripts together under `scripts/macos/` with wrappers forwarding flags,
working-directory independence and original exit status. Preserve worktree
sidecars and meeting guards. Do not rewrite signing or runtime identity in a move.

## Evidence commands

`git ls-files .agents .claude .cursor scripts plans .github`;
`git ls-files -s .claude CLAUDE.md`; searches for
`source`, `.agents/skills`, `.cursor/commands`, `scripts/`, `agent-loops`,
`ensure-app-running`, `implementer` across scripts, workflows and source.
No retained dependency chain was removed. Only the model-tier rule is a deletion;
its executable consumer is the editor's automatic rule loader, not the app.
