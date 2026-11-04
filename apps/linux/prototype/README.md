# Ubuntu desktop integration prototype

This disposable prototype validates the desktop before production adapters are
chosen. It has no cloud requests, API keys, transcription or feature parity.

## Setup

On Ubuntu 24.04, the probe and unit tests require only system Python:

```bash
bash scripts/linux/probe-desktop.sh --json
bash scripts/linux/test.sh
```

For the GUI, use distribution packages (installation is an explicit user action):

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-gstreamer-1.0 \
  gir1.2-gst-plugins-base-1.0 gir1.2-secret-1 gstreamer1.0-tools \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good pulseaudio-utils gettext
```

Use `/usr/bin/python3`, which can find distro GI libraries. Do not install GTK
bindings into an unrelated global Python. Run GUI checks in your GNOME session,
not headless CI. The app does not install packages or register shortcuts silently.

## Meaning of results

JSON exit 0 means the report was generated. A dependency import, advertised
portal, or live session bus is not a successful recording or shortcut test.
Missing dependencies are `unavailable`; inaccessible session services are
`blocked`; present but unexercised capabilities are `untested`.
Reports exclude raw environment values, device identifiers and stderr.

## Interactive checks

```bash
bash scripts/linux/run-prototype.sh
# German UI, even if a German system locale is not installed:
LANGUAGE=de bash scripts/linux/run-prototype.sh
# Safe window/render check; never records or touches the keyring:
bash scripts/linux/run-prototype.sh --smoke-test
```

The smoke check refuses to run against an existing demo instance. Quit the demo
using its button before running a separate smoke check; never kill a recording.
It saves only a screenshot of its own window to /tmp/whisper-prototype-smoke.png.

1. Choose a microphone source; record a short spoken phrase; Stop; Play.
2. Play harmless system sound; Record system audio; Stop; Play. The monitor field
   uses PulseAudio's default monitor token. If your server rejects it, select an
   actual monitor name after installing pulseaudio-utils and using
   `pactl list short sources`. Do not substitute a microphone and claim success.
3. Test combined capture with headphones, then silence and device disconnection.
   Listen for both intended inputs and absence of duplicate feedback.
4. Copy the harmless sample text, enable background running, close the window,
   then paste into another application. Reopen with the same run command.
5. Optionally click the disposable keyring test. It stores a random test value,
   verifies and removes that exact item; it never reads your real credentials.
   Cancel the test to check cancellation. Do not quit until cleanup finishes.
6. Stop/cancel recordings before closing or quitting. Quit deletes prototype
   audio on normal shutdown. A crash may leave test files in the OS temporary
   directory; this prototype is not the production recovery implementation.

Recordings are WAV files inside a private temporary directory, with mode 0600.
Cancel deletes the current test recording; starting a new one replaces it.
No recordings or keys are uploaded. No captures start merely on opening a window.

## GNOME shortcut fallback

The GlobalShortcuts portal was not advertised on the tested Ubuntu 24.04 desktop.
Use GNOME Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts.
After microphone capture works, bind an absolute-path command:

```text
bash /absolute/path/to/repo/scripts/linux/run-prototype.sh --toggle-recording
```

Use the actual checkout path; a main checkout will not contain this script until
the PR is merged. This command uses the existing single instance, presenting its
window if needed. A cold start waits for source discovery. Press it again to
stop/finalize. This config change is manual; the prototype does not register a
shortcut or request unrestricted keyboard access.

The prototype reads single-line singular strings from po/de.po directly to avoid
requiring a gettext compiler for this experiment. Production localization will
use compiled gettext catalogs. Audio/report artifacts never belong in Git.

Measured results and pending checks: docs/development/ubuntu-desktop-prototype.md.
