# Local transcription handover

Branch: feat/ubuntu-transcription, based on origin/main 70ea2f70. This implements
the user-requested local-first slice; it is not the complete four-feature app.

## Result and use

Start the separate CPU container with scripts/linux/start-local-transcription.sh,
then run scripts/linux/run-prototype.sh. Record, Stop and finalize, Transcribe
recording (local CPU), then read/copy the Transcript field. LANGUAGE=de selects
German UI. Existing OpenRouter env entries need no modification for default local
mode. No API key is forwarded to the container and no cloud request was made.

See apps/linux/prototype/README.md for exact commands and limits, and
[verbatim validation](ubuntu-local-transcription-validation.txt).

## Implementation and review

Configuration, bounded HTTP transport, cancellable background job and GTK state
are separate modules. Local inference is faster-whisper base/INT8 in a dedicated
non-root CPU container, published only to host loopback. The model revision and
compatible PyAV version are pinned. The Docker build tests WAV decoding.

Independent code review by gpt-6-astra found a synchronous HTTP cleanup path that
could block GTK Cancel and postpone timeout delivery. Real HTTP reader-lock tests
failed first; asynchronous cleanup/socket interruption and dispatch-first timeout
publication fixed both. The full headless suite passed. No deferred minors.

## Decisions and costs

- Extend the existing prototype to deliver visible transcripts now; production
  storage/keyring/long meetings remain future work.
- Honor the user's env-based development setup; production keyring UI is still
  absent. Real env files are never copied/committed.
- Follow the user's local-first priority; OpenRouter is explicit opt-in, and its
  real API/auth availability is not tested.
- Use normal Docker bridge with 127.0.0.1 publication because Desktop did not
  publish ports on the internal bridge. Model loading is offline; this is not an
  egress firewall, and same-host processes can access the service.
- Accept parent-run real GTK/container evidence alongside read-only code review;
  these runtime checks were not independently repeated by the reviewer.
- Use the public fixture for automated speech proof; fresh user/device accuracy
  and edge cases remain manual checks.
- Keep transcripts window-only and audio temporary in this slice; copy before
  Quit, and do not treat it as production recovery.
- Leave Mac runtime untouched; no new local Mac verification is claimed.
- Final documentation was self-reviewed after code review; it has no second
  independent review.

### Technical Learnings

A healthy process does not prove decoding/inference works. Pin compatible library
APIs and test the real boundary. Cancellation must invalidate results before
potentially blocking cleanup.

### Why It Works

The GTK loop only schedules work and displays identity-checked callbacks. The
worker talks to loopback, whose server uses baked local model files. Cleanup runs
outside GTK and timeout publication does not wait for HTTP reader locks.

### Engineering Trade-offs

The small base model favors an easy CPU setup over maximum recognition quality.
The private JSON endpoint matches the client but is not a general OpenAI-compatible
server. The model is baked into the image, trading image size for offline loads.

### Common Pitfalls

Automatic cloud fallback; confusing chat and speech models; deleting valid audio
on failure; assuming close() cannot block; trusting health without a speech test;
losing copied-only text by quitting before saving it elsewhere.

### What I Should Remember

Validate whole workflows with representative data. Keep UI state, I/O and cleanup
separate. Local inference means no cloud request; it does not imply a container
has an operating-system egress firewall.
