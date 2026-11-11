# Ubuntu Live Dictation Implementation Plan

> Use superpowers:executing-plans for native execution and one independent final review.

**Goal:** Edit recognized text while recording; subsequent local results only append.
**Architecture:** Capture PCM with GStreamer tee/appsink alongside full WAV; a bounded sequential live session transcribes complete five-second sections through existing cancellable jobs. A focused controller handles append/edit checkpointing and capture/drain lifecycle.
**Tech Stack:** Existing Python/GStreamer/GTK/SQLite and local faster-whisper; no new dependencies.
**Spec:** ubuntu-live-dictation-design.md (approved user behavior).

## Constraints and review focus

Local only; S16LE/16 kHz/mono; five-second sections; at most 300 seconds/9.6 MB queued PCM. GTK edits and appends only on main loop. Preserve corrections across Stop, saved history reopen, inference/storage failures and cancellation. Never clean full audio before edited text is committed. No silent chunk drops/cloud uploads or content logs. Test late callbacks, silence vs invalid JSON, a slow worker, section tail, mid-editor selection, draft-storage failure and refusal to overwrite edits on batch retry.

## Task 1: Streaming session and safe empty responses

Files: live_session.py, transcription_client.py, tests/test_live_session.py, tests/test_local_transcription.py.
Interfaces: LiveSession(config,dispatch,callback,transcriber=None); feed(pcm), finish(), cancel(); callback(session,text,error,done). Exact chunk ordering; finish emits the short tail; cancellation invalidates callbacks and closes requests through TranscriptionJob. Live client accepts an explicitly empty local text response only with allow_empty=True.
- [ ] Add RED tests for ordered output/tail, silence, cancellation, errors and bounded overflow; implement and run focused tests.

## Task 2: Editable history drafts and GTK integration

Files: history_store.py, live_controller.py, desktop_demo.py, tests/test_history_store.py, tests/test_demo_lifecycle.py, tests/test_live_controller.py, po/de.po.
Interface: HistoryStore.update_text(id,text) preserves status/audio; controller manages dirty drafts, append, session identity and completion. Demo owns capture pipeline and existing operation guards.
- [ ] Add RED storage/controller tests for preserved corrections, draft persistence without audio cleanup, failure guards and stale output.
- [ ] Add editable TextView and local checkbox; tee/appsink capture; Stop drains tail, Cancel retains drafts/audio, editor checkpoint debounce and Retry save.
- [ ] Keep batch mode and cloud defaults explicit; refuse replacing existing text by re-transcription. Update German labels.
- [ ] Run full Linux suite and real synthetic GTK/GStreamer checks; commit explicit files.

## Task 3: Verification and delivery

- [ ] Independent whole-change review; reproduce/fix Important findings with regression tests.
- [ ] Real local-container synthetic audio check, EN/DE desktop rendering and edited-text restart test in isolated data roots; syntax and whitespace checks.
- [ ] Update Linux user documentation and full verbatim validation report; commit, push feature branch and create draft PR. No merge/release or recording interruption.
