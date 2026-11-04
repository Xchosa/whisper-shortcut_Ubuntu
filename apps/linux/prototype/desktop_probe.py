"""Redacted capability inventory. Presence is not a functional desktop test."""
import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

TIMEOUT_SECONDS = 5


def result(status, reason):
    return {"status": status, "reason": reason}


def run(command):
    """Never return stderr or command strings to the report."""
    try:
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=TIMEOUT_SECONDS, check=False)
        if completed.returncode != 0:
            return "unavailable", ""
        return "available", completed.stdout
    except subprocess.TimeoutExpired:
        return "blocked", ""
    except OSError:
        return "unavailable", ""


def gi_dependency(namespace, version, version_expression):
    code = (f"import gi; gi.require_version({namespace!r}, {version!r}); "
            f"from gi.repository import {namespace}; " + version_expression)
    status, output = run(["/usr/bin/python3", "-c", code])
    # Only version-like strings can leave the subprocess boundary.
    version_match = re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,3}\s*", output)
    reason = "Import succeeded; functionality untested"
    if status == "available" and version_match:
        reason = "Import succeeded; version " + output.strip() + "; functionality untested"
    elif status != "available":
        reason = "Dependency unavailable" if status == "unavailable" else "Dependency check timed out"
    return result(status, reason)


def bus_interfaces(destination, object_path):
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return "blocked", set()
    status, output = run(["gdbus", "introspect", "--session", "--dest", destination,
                          "--object-path", object_path, "--xml"])
    if status != "available":
        return status, set()
    try:
        return "available", {x.attrib.get("name") for x in ET.fromstring(output).findall("interface")}
    except ET.ParseError:
        return "blocked", set()


def portal_capability(interface, interfaces, bus_status):
    if bus_status != "available":
        return result("blocked", "Desktop portal unavailable or session bus inaccessible")
    if interface not in interfaces:
        return result("unavailable", "Portal interface not advertised")
    status, output = run(["gdbus", "call", "--session",
                          "--dest", "org.freedesktop.portal.Desktop",
                          "--object-path", "/org/freedesktop/portal/desktop",
                          "--method", "org.freedesktop.DBus.Properties.Get",
                          interface, "version"])
    version = re.search(r"uint32 (\d+)", output) if status == "available" else None
    detail = f" (version {version.group(1)})" if version else ""
    return result("untested", "Portal interface advertised" + detail + "; activation untested")


def collect_report() -> dict:
    dependencies = {
        "gtk": gi_dependency("Gtk", "4.0", "print(f'{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}')"),
        "gstreamer": gi_dependency("Gst", "1.0", "Gst.init(None); print('.'.join(map(str, Gst.version()[:3])))"),
        "libsecret": gi_dependency("Secret", "1", "print(f'{Secret.MAJOR_VERSION}.{Secret.MINOR_VERSION}.{Secret.MICRO_VERSION}')"),
    }
    bus_status, interfaces = bus_interfaces("org.freedesktop.portal.Desktop",
                                           "/org/freedesktop/portal/desktop")
    secret_status, secret_interfaces = bus_interfaces("org.freedesktop.secrets",
                                                      "/org/freedesktop/secrets")
    has_display = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))
    audio_status = dependencies["gstreamer"]["status"]
    capabilities = {
        "window": result("untested" if has_display and dependencies["gtk"]["status"] == "available" else "blocked",
                         "A real GTK window must be tested in a desktop session"),
        "clipboard": result("untested", "Copy/paste and background ownership require interactive testing"),
        "microphone": result("untested" if audio_status == "available" else audio_status,
                             "Record and listen back explicitly; dependency presence is insufficient"),
        "system_audio": result("untested" if audio_status == "available" else audio_status,
                               "Monitor source capture and headphones require interactive testing"),
        "global_shortcuts": portal_capability("org.freedesktop.portal.GlobalShortcuts", interfaces, bus_status),
        "screencast": portal_capability("org.freedesktop.portal.ScreenCast", interfaces, bus_status),
        "keyring": result("untested" if secret_status == "available" and "org.freedesktop.Secret.Service" in secret_interfaces else "blocked",
                          "Store/read/delete of a disposable value requires explicit interaction"),
    }
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower().split(":")
    return {
        "schema_version": 1,
        "platform": sys.platform if sys.platform in {"linux", "darwin", "win32"} else "other",
        "session_type": session if session in {"wayland", "x11"} else "unknown",
        "desktop": "GNOME" if "gnome" in desktop else "other",
        "dependencies": dependencies,
        "capabilities": capabilities,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit a redacted JSON report")
    parser.parse_args(argv)
    print(json.dumps(collect_report(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
