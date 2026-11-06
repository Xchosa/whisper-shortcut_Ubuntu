# Ubuntu Transcript History Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for native execution, TDD and one independent final review.

**Goal:** Automatically retain transcripts with timestamps, reopen/copy/export/delete history, and keep failed recordings across restarts.

**Architecture:** A private XDG SQLite store owns transcript metadata and recording files. GTK keeps its existing recorder/job adapters; a separate history panel displays paginated summaries. Save text transactionally before audio cleanup; export snapshots on a worker with atomic file replacement.

**Tech Stack:** Python 3.12 sqlite3/pathlib, existing GTK4/GStreamer, stdlib worker thread.

**Spec:** Approved multiplatform design's SQLite/data-retention rules and user's “genau richtig, mach weiter” approval of the proposed history/export/retry slice.

## Global constraints

- Continue native execution without repeating scope approval. No model/provider, container or Mac runtime change.
- Default data root: XDG_DATA_HOME/whispershortcut, otherwise ~/.local/share/whispershortcut. Explicit absolute WHISPER_SHORTCUT_DATA_DIR supports isolated development/testing.
- Private app/audio directories 0700; database/audio files 0600. Do not log transcript/audio/key content or write user data into Git.
- Schema version 1. Refuse unknown future schemas without modifying their contents.
- Retain completed-but-untranscribed, failed and interrupted audio until explicit deletion or successful transcript save. Do not promise repair of unfinished WAV headers or five-second meeting recovery.
- Save transcript before deleting successful audio. Cleanup failure must not lose the saved text.
- Recover stale recording/transcribing metadata as interrupted on primary-app startup. Only the primary GTK instance initializes/reconciles history.
- Paginate 100 summary rows; fetch full text only on open. Never silently prune user history/audio.
- Small SQLite operations are synchronous with a 100 ms lock timeout; large export writes use a worker. Fail visibly rather than silently falling back to temporary-only storage.
- Export UTF-8 text to an explicitly chosen local path, atomically; preserve existing file on pre-replace failure. Confirm deletion with a specific entry selected.
- Preserve job identity checks, single-operation guards and cancellation. English UI plus German translation.

## Review focus

1. Restart/failed persistence and orphan audio: store tests, real restart fixture.
2. Database failure must retain text/audio and block unsafe transitions: store/UI failure tests.
3. Delete/export must target the intended immutable entry/text snapshot: selected-ID and export snapshot tests.
4. Unknown schema, traversal, symlinks, permissions and SQL-like text must preserve unrelated data: store tests.
5. Active operations and late callbacks cannot overwrite/delete other history: UI lifecycle tests.

## Task 1: Durable store and export

Files: create apps/linux/prototype/history_store.py and tests/test_history_store.py.

Interfaces: HistoryStore(root=None); create_recording()->Entry; audio_path(id)->Path; get(id)->Entry|None; list_entries(limit=100,offset=0)->list[Summary]; mark_ready/transcribing/failed/cancelled; save_transcript(id,text,provider,model)->bool audio_cleaned; delete(id); discard_recording(id). export_text(text,path) performs atomic UTF-8 output.

- [ ] Test reopen, timestamps/order/pagination, successful save+audio cleanup, failed/cancelled retry persistence, interrupted/orphan recovery.
- [ ] Test unknown schemas, locked DB, injected SQL-like text, safe IDs/symlinks, private permissions, failed cleanup and deletion/export failure retention. Watch RED before implementation.
- [ ] Implement SQLite version 1 with bound parameters, private paths and ordered transactions; no dependencies.
- [ ] Run full Linux suite and commit.

## Task 2: Recorder and job retention lifecycle

Files: modify desktop_demo.py and tests/test_demo_lifecycle.py.

- [ ] Add RED tests for durable capture allocation, save-before-cleanup, persistence failure, failed/cancelled retry, new recording preserving older audio, and startup restoration.
- [ ] Allocate a managed recording before capture; mark ready after finalized EOS. Preserve capture errors as interrupted/failed; explicit cancellation can discard unfinished capture.
- [ ] Save successful results before releasing audio; retain copy/export access and block losing an unsaved result on storage error. Provide Retry save.
- [ ] Initialize history only during primary activation; secondary command instances must not mark a live request interrupted.
- [ ] Keep copy/job identity/recording guards and run the full suite; commit.

## Task 3: History panel, export and deletion

Files: create history_panel.py; modify desktop_demo.py and po/de.po.

- [ ] Add history summaries, newer/older paging, explicit Open selected, Delete selected, Retry save and Export displayed text.
- [ ] Show local timestamps/statuses; restore the latest saved/retained entry on startup. Open is idle-only and does not auto-transcribe.
- [ ] Native save dialog captures text before async completion; export on worker, then deliver only to the matching operation.
- [ ] Confirm entry deletion and recheck active-operation state on dialog completion. Saved text and audio deletion remain distinct, explicit actions.
- [ ] Test guards/snapshots/failure paths; run English/German real GTK checks in isolated data roots. Commit.

## Task 4: End-to-end validation and delivery

- [ ] Use synthetic/private-to-test-root content only: create/save, exit, reopen, copy/export/delete, and failed-audio retry. Do not touch user's existing data.
- [ ] Verify permission/schema/privacy checks, full headless suite, compile/shell/whitespace and safe startup.
- [ ] Independent final code review; fix Important/Critical findings RED→GREEN and rerun checks.
- [ ] Update current README/data documentation, user-confirmed local speech evidence and complete verbatim validation.
- [ ] Commit explicit files, push branch and open draft PR. Do not merge/release or interrupt a recording.

## Decisions and limits

SQLite replaces JSON-per-transcript to keep updates/order/versioning in one transaction. Audio stays in separate files so failed clips are reusable without database blobs. Filesystem deletion and DB commits cannot form one transaction: begin write ownership before destructive work, retain metadata on unlink failure, and reconcile successful/orphan files on startup. Export is an explicit plaintext file chosen by the user. Full production packaging, chat, TTS and long meeting recovery stay later work.
