# Platform development commands

## Ubuntu 24.04 / GNOME / Wayland

The Linux work is a recording/transcription prototype with a separate local CPU container, not full feature parity.
The following scripts are introduced by the foundation work:

```bash
bash scripts/linux/probe-desktop.sh --json
bash scripts/linux/start-local-transcription.sh
bash scripts/linux/run-prototype.sh
bash scripts/linux/test.sh
```

Use `/usr/bin/python3` (Ubuntu Python 3.12), not a custom Python installation that
cannot import distribution GI packages. The probe and unit tests use only the
standard library. GUI/audio testing requires a real desktop session and explicit
user actions. See `apps/linux/prototype/README.md` for setup and controls.

## macOS

The existing root paths remain intact until a verified move to apps/macos:

```bash
bash scripts/rebuild-and-restart.sh
bash scripts/run-tests.sh --hermetic
```

These require macOS/Xcode. Linux checks cannot establish Mac compatibility.
Never restart during recording; existing Mac scripts' guards/sidecars stay intact.

## Distribution and historical automation

Release CI has no automatic tag trigger. Manual dispatch remains disabled unless
`FORK_RELEASES_ENABLED` is intentionally set to `true` in repository variables
and signing, destinations and approval policy have been reviewed. It remains
unset by this work. No release is requested or authorized here.

Original scheduled job and installer entry points refuse execution in this fork
with exit 2, before host commands. Their bodies, dependencies, reports and gate
values remain for history. No host jobs are installed or uninstalled.

Local inference setup, provider selection, five-minute limits and data lifetime:
`apps/linux/prototype/README.md`. Dockerfile build context excludes env files.
