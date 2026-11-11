# Ubuntu transcript history handover

Implemented on `feat/ubuntu-history`, based on `fcd13c01`, verified 2026-11-11.

The Ubuntu prototype now saves timestamped transcripts locally, restores the
latest entry at startup, opens older text or retained audio, explicitly copies
text, exports UTF-8 text, and confirms targeted deletion. Failed/untranscribed
recordings survive restart and new captures. Local CPU transcription was already
confirmed usable by the user; this change does not change the provider/model.

## Try it before merging

From the main checkout, with the previous prototype closed normally:

```bash
LANGUAGE=de bash .claude/worktrees/ubuntu-history/scripts/linux/run-prototype.sh
```

Record a short sentence, Stop and finalize, then Transcribe. Quit normally and
reopen: the latest result should return. Choose a history row and Open selected;
use Copy transcript or Export transcript. To retry a failed recording, open its
entry and click Transcribe. Delete selected asks for confirmation.

Normal data lives at `$XDG_DATA_HOME/whispershortcut`, or
`~/.local/share/whispershortcut`: private directories (0700), SQLite and WAV files
(0600). These files are plaintext. Successful transcript commit happens before
its audio is removed. There is no automatic pruning. Cancel transcription keeps
audio; cancelling an active capture explicitly discards unfinished audio.

Export captures the currently displayed text, independently of the dropdown.
A worker writes a private temporary UTF-8 file, flushes/fsyncs it, then atomically
replaces the chosen destination. The app rejects exports into its own data root.
Export does not erase separately exported files when a history entry is deleted.

## Validation and review

Full command output is quoted verbatim in [ubuntu-history-validation.txt](ubuntu-history-validation.txt).
84 tests pass: 1 historical-tooling guard plus 83 prototype tests. Storage tests
cover reopen, SQL-like data, permissions, unknown schemas, unsafe paths, actual
SQLite locking, failed writes/cleanup/deletion, retained audio and atomic export.
Lifecycle tests cover save failure protection, retries, stale jobs, immutable
export/deletion snapshots, operation guards, capture retention and visible errors.

Real GTK checks on the current Ubuntu desktop used isolated synthetic data roots,
no microphones/cloud requests/private history. English and German UI rendered;
startup restore, opening text/audio, UTF-8 export, targeted deletion and native
dialog construction passed. Headless tests exercise dialog callbacks using fakes;
interactive file-picker navigation is still a manual check.

An independent `gpt-6-astra` reviewer found two Important issues: Cancel released
an active export's operation guard; failed audio deletion was hidden by Idle.
Both were reproduced with failing regression tests and fixed. The same pass also
preserved EOS storage errors and protected the database from export replacement.
No second review was requested. The screenshot harness initially bound its
paintable before GTK created the window; it now binds after activation and allows
an asynchronous redraw. No product recording was interrupted.

## Limits

This remains a prototype: WAV up to five minutes/20 MiB, no long-meeting chunking,
chat, TTS or installer. SQLite calls run on GTK with a 100 ms lock timeout; a slow
filesystem may still delay metadata work. Retained incomplete WAVs may need repair
and may not transcribe. Export provides atomic replacement, not an entire-directory
power-loss guarantee. Local files are not encrypted or forensically erased.
Mac runtime/build variants are untouched; Xcode execution is unavailable on Ubuntu.

### Technical Learnings

SQLite transactions, explicit file ownership and immutable callback snapshots
protect different parts of the recording lifecycle. OS permissions protect local
access; they are separate from encryption.

### Why It Works

Text is committed before deleting successful audio. Failed persistence retains
both the visible result and recording. Entry IDs and operation guards prevent
late callbacks from changing another recording.

### Engineering Trade-offs

SQLite avoids a new dependency and makes metadata updates atomic. Audio remains
outside the database for retry; filesystem removal and a DB transaction cannot
be one transaction, so startup reconciliation handles leftovers.

### Common Pitfalls

Do not announce success after a failed cleanup, release a guard while a worker
still runs, or assume a retained incomplete WAV is valid audio. Creating a GTK
paintable before its widget exists can produce an empty screenshot indefinitely.

### What I Should Remember

Persist before cleanup. Preserve failure evidence. Capture immutable identities
for asynchronous work, and report the actual outcome to the user.
