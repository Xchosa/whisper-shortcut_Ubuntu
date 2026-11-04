# Ubuntu foundation draft handover

Branch: `feat/ubuntu-foundation`, based on merged plan `98a0a653`.
Code review covered `98a0a653..dd99a915`; fix commit `f12e7a27` addresses both
Important findings with regression tests. Final HEAD is reported in the PR.

## GitHub authentication

The first HTTPS push was rejected because the GitHub CLI token lacked `workflow`
scope for CI changes. The login now includes that scope, verified with
`gh auth status`. Use the existing GitHub CLI credential helper for HTTPS pushes;
no SSH setup or token exposure is required. Manual desktop validation remains
pending, so the foundation is delivered as a draft PR.

## Delivered

Tooling inventory; canonical platform-aware AGENTS.md and editor pointers;
removed automatic Mac relaunch hook and original-owner model mandates; guarded
14 inherited scheduled/install/merge entry points; disabled automatic release
triggers and gated manual jobs; redacted capability probe; opt-in bilingual
GTK/audio/keyring desktop prototype; Linux CI alongside unchanged Mac jobs.
Instruction changes are isolated in commit `0b75f8e3`. Ledger/gate definitions,
Mac runtime code, identities and distribution variants are unchanged.

## Evidence and boundaries

See [full verbatim validation output](ubuntu-foundation-validation.txt) and
[desktop evidence](ubuntu-desktop-prototype.md). Independent review used
`gpt-6-astra`. Deferred-capture cancellation and playback-error audio preservation
were reproduced before fixes, then verified by the full headless suite.

Tasks 1–3 are verified. Task 4 has runtime checks pending; Task 5 CI is implemented
but final adapter adoption remains conditional. Task 6 Mac move is deferred.
Keep this PR a draft until the desktop evidence needed for adoption is available.
No merge or release is performed by this work. No additional scope approval is
needed to finish those tests; actual user interaction/results are missing.

If the prototype is still open from before the fixes, stop/cancel any capture
and use its Quit button. Reopen using the command in its README. Never kill a
recording to refresh code. The running old process cannot load edited Python
methods automatically. The isolated corrected-code smoke window never captured.

## Rulings made and costs

1. Defer Mac relocation until authorized Mac verification; target structure stays incomplete.
2. Retain dependency-linked historical tooling/skills/ledgers while detaching hooks and guarding entry points; residual historical files remain until a verified cleanup.
3. Record manual desktop checks as pending and continue independent CI; production adapter adoption remains blocked.
4. Use GStreamer discovery and a narrow singular PO reader rather than installing missing pactl/msgfmt; production gettext must replace the temporary reader.
5. Audio quality, headphones, silence and device-loss behavior require listening tests; hardware integration faults may remain.
6. Same-process reopen does not prove cross-app clipboard or recording shortcuts; those workflows remain unaccepted.
7. Keyring storage/unlock cancellation/cleanup needs an explicit runtime test; credential persistence is unproven.
8. Portal registration on supported desktops is deferred; the measured GNOME target uses a manual fallback, and other desktops need testing.
9. Mac build/runtime compatibility cannot be established here; unchanged source layout reduces risk but does not replace Mac checks.
10. Production recovery/providers/chat/synthesis/meeting acceptance belongs to subsequent plans; this foundation remains a prototype, not the usable four-feature release.

Deferred minors: none. The execution ledger/worktree is retained because manual
validation remains open.

### Technical Learnings

Cancellation must revoke queued intent as well as running work. Cleanup must
distinguish incomplete output from valid input. API presence does not establish
working desktop integration.

### Why It Works

The capture request is consumed once only while idle and is invalidated by
Cancel/Stop/Close. Playback errors retain the WAV; failed captures discard only
incomplete output. Headless tests reproduce these transitions without GI/audio.

### Engineering Trade-offs

Separate native apps preserve the working Mac implementation but duplicate some
logic. A disposable prototype settles platform adapters before production code.
Keeping historical dependencies costs repository space while avoiding broken Mac paths.

### Common Pitfalls

Treating a successful import or silent WAV as a functional recording; using X11
assumptions on Wayland; restarting a process while it records; deleting valid
input during error cleanup; reporting Ubuntu tests as Mac verification.

### What I Should Remember

Test asynchronous orderings, not just happy paths. Keep platform proof separate
from unit-test proof. A successful prototype is evidence, not feature parity.
