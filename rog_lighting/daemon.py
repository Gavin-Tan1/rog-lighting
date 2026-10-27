import fcntl
import os
import sys

import gi

gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib

from . import config, devices

KEY_BRIGHT_UP = 0xC4
KEY_BRIGHT_DOWN = 0xC5
RECONNECT_SECONDS = 3

LOCK_PATH = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR") or os.path.expanduser("~/.cache"),
    f"rog-lighting-{os.getuid()}.lock",
)


def is_running():
    try:
        fd = os.open(LOCK_PATH, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        os.close(fd)


def running_pid():
    if not is_running():
        return None
    try:
        with open(LOCK_PATH) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


class Daemon:
    def __init__(self, debug_keys=False):
        self.debug_keys = debug_keys
        self.fd = None
        self.watch_id = None
        self.loop = GLib.MainLoop()

    def connect(self):
        path = devices.find_hidraw(devices.ASUS_VID, devices.KEYBOARD_PID)
        if not path:
            return True
        try:
            self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            return True
        self.watch_id = GLib.io_add_watch(
            self.fd, GLib.PRIORITY_DEFAULT,
            GLib.IOCondition.IN | GLib.IOCondition.HUP | GLib.IOCondition.ERR,
            self.on_readable,
        )
        self.apply_saved()
        return False

    def disconnect(self):
        if self.watch_id:
            GLib.source_remove(self.watch_id)
            self.watch_id = None
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        GLib.timeout_add_seconds(RECONNECT_SECONDS, self.connect)

    def on_readable(self, fd, cond):
        if cond & (GLib.IOCondition.HUP | GLib.IOCondition.ERR):
            self.disconnect()
            return False
        try:
            data = os.read(fd, 64)
        except BlockingIOError:
            return True
        except OSError:
            self.disconnect()
            return False
        if len(data) >= 2 and data[0] == 0x5A:
            code = data[1]
            if self.debug_keys:
                print(f"hotkey 0x{code:02x}", flush=True)
            if code == KEY_BRIGHT_UP:
                self.step_brightness(+1)
            elif code == KEY_BRIGHT_DOWN:
                self.step_brightness(-1)
        return True

    def step_brightness(self, delta):
        cfg = config.load()
        level = max(0, min(3, cfg["keyboard"]["brightness"] + delta))
        cfg["keyboard"]["brightness"] = level
        try:
            devices.Keyboard().set_brightness(level)
        except devices.DeviceError:
            return
        config.save(cfg)

    def apply_saved(self):
        devices.apply_settings(config.load())
        return False

    def on_sleep_signal(self, _conn, _sender, _path, _iface, _signal, params):
        (going_to_sleep,) = params.unpack()
        if not going_to_sleep:
            GLib.timeout_add_seconds(2, self.apply_saved)

    def run(self):
        os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
        self.lock_fd = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("rog-lighting daemon is already running", file=sys.stderr)
            return 1
        os.ftruncate(self.lock_fd, 0)
        os.write(self.lock_fd, str(os.getpid()).encode())

        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            bus.signal_subscribe(
                "org.freedesktop.login1", "org.freedesktop.login1.Manager",
                "PrepareForSleep", "/org/freedesktop/login1", None,
                Gio.DBusSignalFlags.NONE, self.on_sleep_signal,
            )
        except GLib.Error:
            pass

        if self.connect():
            GLib.timeout_add_seconds(RECONNECT_SECONDS, self.connect)
        try:
            self.loop.run()
        except KeyboardInterrupt:
            pass
        return 0
