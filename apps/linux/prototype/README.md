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

The GUI and validation report are added by the next foundation task.
Audio and generated probe outputs belong in temporary/ignored storage, never Git.
