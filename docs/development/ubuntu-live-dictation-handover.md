# Editable local live dictation handover

Branch: `feat/ubuntu-live-dictation`, based on merged `5a9431c9` (PR #5).
User-approved behavior: edit recognized text while recording; new results only append.

## Test before merge

Close the previous prototype normally; never interrupt an active recording.
From the main checkout:

```bash
bash .claude/worktrees/ubuntu-live-dictation/scripts/linux/start-local-transcription.sh
LANGUAGE=de bash .claude/worktrees/ubuntu-live-dictation/scripts/linux/run-prototype.sh
```

Keep Live transcription enabled, Record microphone, speak for more than five
seconds, edit the first result, then keep speaking. Later recognition appends
in new paragraphs without replacing that correction or moving a cursor inside
older text. Stop finalizes audio and drains remaining sections; editing stays
available during this step. Quit/reopen checks that the edited result survived.
Switch Live off to use manual batch transcription. Cloud mode stays manual.

## Implementation and decisions

A tee receives 16 kHz mono S16LE PCM. One branch records full WAV; the other
supplies five-second sections to a bounded sequential session. Each complete
private temporary section reuses existing TranscriptionJob timeout/cancellation
and the local service. No model, image, provider endpoint or dependency change.

- Five-second sections avoid repeatedly re-transcribing a growing file. Cost:
  word boundaries/context can be worse than full-file recognition; no overlap
  reconciliation or token streaming is promised.
- Live inference is local-only. Cloud remains explicit manual batch; there is
  no automatic cloud fallback. Cost: cloud streaming is not part of this slice.
- A common GStreamer cap before the tee stops both audio branches at 300 seconds.
  A delayed UI Stop cannot abort accepted sections. Cost if incorrect would be
  lost queued text or audio too long to retry; real three-rate tests cover it.

Gtk.TextBuffer.insert appends without replacing existing text. A focused
controller tracks changes immediately, checkpoints edited text after 500 ms,
and flushes before changing entries/quitting. Free text entered without a selected
entry gets a manual history row. Draft writes preserve audio/status; successful
completion saves the current edited buffer before deleting audio. Failed writes
keep the dirty result and block losing it; Retry save or successful text export
provides a recovery path. No history schema bump or automatic pruning.

Cancel invalidates live callbacks and retains edited text/audio. Manual capture
Cancel also retains typed text; without text it discards the unfinished clip.
An unfinished WAV may be invalid. Re-transcribing a nonempty editor is refused
until the user explicitly clears it; completion also preserves text typed while
waiting for a manual request. Long history previews ellipsize so they do not
force the editor beyond the window width.

## Verification and review

Full verbatim command output: [ubuntu-live-dictation-validation.txt](ubuntu-live-dictation-validation.txt).
104 headless tests pass: 1 tooling guard and 103 prototype tests. Python compile,
shell syntax and whitespace checks pass. Real GTK/GStreamer/local-model checks
passed in English and German using the public whisper.cpp JFK test WAV, isolated
data roots and no microphone/private history/cloud calls. These checks confirmed
text during capture, correction/cursor retention, Stop drain, successful audio
cleanup, and edited text after reopening SQLite. Real synthetic GStreamer input
at 16, 44.1 and 48 kHz produced exactly matching 300-second WAV and live PCM.
Existing history restore/open/export/delete/native-dialog-construction check passed.
The system emitted one GStreamer video-plugin scanner diagnostic in an early run;
audio checks completed successfully; it is not an application content log.

One initial reviewer was lost to a server restart. The completed independent
`gpt-6-astra` review identified three Important issues. All were reproduced in
RED tests, fixed in one pass and verified with the full suite:

1. Manual Cancel discarded typed text and left dirty metadata pointing to a
   deleted row: preserve typed drafts and reset dirty state on explicit deletion.
2. Fresh-editor text was ignored without an entry ID: track immediately and
   create a manual text entry on checkpoint.
3. The time limit cancelled queued recognition: cap upstream and drain accepted
   sections normally, including a delayed Stop boundary test.

No Critical or deferred Minor findings were reported. No re-review requested.
Implementation tasks share this recording/editor lifecycle and are delivered in
one integrated commit after review, rather than isolated per-task commits.

## Remaining limits

Five-minute prototype cap, section latency plus CPU inference time, possible
recognition loss near section boundaries, plaintext local storage and synchronous
small SQLite writes with a 100 ms lock timeout. A slow filesystem can still delay
metadata work. Crash recovery may miss the latest debounce window; incomplete
WAV headers are not repaired. Microphone quality still needs user testing.
Mac runtime is unchanged and cannot be executed on Ubuntu. No release/merge.

### Technical Learnings

Audio capture, inference and editing need separate lifecycles and explicit identities.

### Why It Works

Only new recognition is appended; saving uses the current edited buffer. Audio
is deleted only after that buffer commits successfully.

### Engineering Trade-offs

Fixed sections keep CPU/memory bounded and reuse the existing service, at the
cost of delay and reduced context around section boundaries.

### Common Pitfalls

Do not replace an editor buffer after asynchronous work, delete dirty drafts,
or abort accepted work because the UI timer stops slightly late.

### What I Should Remember

Track text immediately, persist before cleanup, reject stale callbacks and place
recording limits upstream of all audio consumers.
