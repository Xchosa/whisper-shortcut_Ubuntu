# Ubuntu desktop prototype evidence

Date: 2026-11-04. Environment: Ubuntu 24.04, GNOME, Wayland.
This is a prototype report, not production acceptance.

## Measured results

| Check | Expected | Observed | Status |
|---|---|---|---|
| System Python | 3.12 with distro GI | Python 3.12.3; PyGObject 3.48.2 | available |
| GTK | window launch and responsive loop | GTK 4.14.5; real window rendered; timer callback fired; screenshot visually inspected | passed for smoke scope |
| GStreamer | necessary audio elements present | 1.24.2; pulsesrc, audiomixer, wavenc, playbin, autoaudiosink factories found | available; recording untested |
| Audio enumeration | discover capture devices without starting streams | 1 default-provider source; 4 entries with show-all enabled (may include duplicates) | enumeration passed; input identity/content untested |
| Shortcut portal | advertised GlobalShortcuts interface | interface not advertised | unavailable |
| GNOME shortcut fallback | activation with another app focused | documented command; user configuration/activation not yet demonstrated | pending |
| ScreenCast portal | presence only | interface version 5; not evidence of system audio | untested |
| Secret Service | asynchronous synthetic store/read/delete | service advertised and libsecret imports; test button implemented | pending user action |
| Microphone | speech recorded and heard correctly | no capture started by the agent; listening check requested | pending user action |
| System capture | playback recorded and heard | monitor token path implemented; no capture started by the agent | pending user action |
| Combined/headphones | both sources, no duplicate feedback | controls implemented; hardware listening checks pending | pending user action |
| Silence/disconnect | honest errors and cleanup | handlers implemented; device tests pending | pending user action |
| Clipboard | paste into another app after hiding window | control implemented; cross-app/background check pending | pending user action |
| Single instance | second command targets first process | normal second launch exited 0; D-Bus owner PID unchanged | passed for reopen; recording action untested |
| German copy | every UI message has translation | 43 messages covered; separate German smoke window rendered and screenshot visually inspected | coverage and render passed |

Smoke command: `bash scripts/linux/run-prototype.sh --smoke-test`, exit 0:

```text
GTK window rendered; main-loop timer fired; no recording started.
```

A first exploratory GStreamer property lookup used a newer API name and was
rejected. The installed 1.24 API uses the `show-all` property; enumeration then
succeeded. No audio stream was started by these discovery checks.

No packages were installed; pactl and msgfmt are absent. The prototype uses
GStreamer enumeration and a narrow PO reader, so neither blocks window launch.
No API key, transcript, raw device ID or recording is included in this report.

## Current decision

GTK is viable for window rendering; GStreamer is a candidate audio adapter.
Final audio/clipboard/background/shortcut adoption remains conditional on the
pending tests above. In particular, microphone-only recording cannot satisfy
meeting acceptance. No further toolkit decision is inferred from installed APIs.

Keep the Mac tree where it is: there is no authorized Mac runtime environment
for relocation verification. Existing secret-free Mac CI remains enabled.

## Official references

- [GTK application lifecycle](https://pygobject.gnome.org/tutorials/gtk4/application.html)
- [GStreamer device monitor](https://gstreamer.freedesktop.org/documentation/gstreamer/gstdevicemonitor.html)
- [PulseAudio GStreamer elements](https://gstreamer.freedesktop.org/documentation/pulseaudio/index.html)
- [WAV encoding](https://gstreamer.freedesktop.org/documentation/wavenc/index.html)
- [libsecret asynchronous Python examples](https://gnome.pages.gitlab.gnome.org/libsecret/libsecret-python-examples.html)
- [Global shortcut portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html)

Documentation defines APIs; it does not prove this desktop's functional support.

## Local transcription follow-up — 2026-11-05

The user confirmed recordings work. The local CPU base model now transcribed the
public faster-whisper JFK fixture through the actual loopback client in 2.54 s.
A real GTK job displayed that result while 44 main-loop heartbeats fired.
No private recording, microphone capture, cloud request or API key was involved.
The initial decoder test exposed PyAV 19.0.2 incompatibility with faster-whisper
1.2.1; pinning PyAV 16.0.1 and adding a Docker build-time WAV decode check fixed it.
Docker Desktop did not publish ports on the internal network; a normal bridge
with host 127.0.0.1:8765 is used. Runtime weights load locally/offline, while the
container itself is not protected by an egress firewall.

User speech accuracy, system mixing/headphones, keyring and GNOME shortcut edge
cases remain separate checks. OpenRouter is retained as explicit opt-in and is
not live-tested. See the current prototype README for exact controls and limits.
