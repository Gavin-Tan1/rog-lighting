import os
import signal
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from . import config, daemon, devices

APP_ID = "io.github.Gavin_Tan1.RogLighting"
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTOSTART_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "autostart", "rog-lighting-daemon.desktop",
)

KB_MODES = [("static", "Static"), ("breathe", "Breathing"), ("cycle", "Color cycle"), ("rainbow", "Rainbow")]
KB_SPEEDS = [("slow", "Slow"), ("medium", "Medium"), ("fast", "Fast")]
KB_LEVELS = ["Off", "Low", "Medium", "High"]
SLASH_MODES = list(devices.Slash.MODES)


def rgba_to_list(rgba):
    return [round(rgba.red * 255), round(rgba.green * 255), round(rgba.blue * 255)]


def list_to_rgba(c):
    rgba = Gdk.RGBA()
    rgba.parse(f"rgb({c[0]},{c[1]},{c[2]})")
    return rgba


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="ROG Lighting", default_width=480, default_height=760)
        self.cfg = config.load()
        self.syncing = False
        self.slash_timer = None
        self.keyboard = devices.Keyboard()
        self.slash = devices.Slash()

        self.toasts = Adw.ToastOverlay()
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.banner = Adw.Banner(
            title="Device access isn't set up yet. Run install.sh once (needs sudo), then reopen."
        )
        box.append(self.banner)
        page = Adw.PreferencesPage()
        page.set_vexpand(True)
        box.append(page)
        toolbar.set_content(box)
        self.toasts.set_child(toolbar)
        self.set_content(self.toasts)

        page.add(self.build_keyboard_group())
        page.add(self.build_slash_group())
        page.add(self.build_background_group())

        self.refresh_device_state()
        self.load_into_widgets()

        self.monitor = Gio.File.new_for_path(config.CONFIG_PATH).monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.monitor.connect("changed", self.on_config_file_changed)

    def build_keyboard_group(self):
        g = Adw.PreferencesGroup(title="Keyboard backlight")
        self.kb_group = g

        row = Adw.ActionRow(title="Brightness")
        levels = Gtk.Box(css_classes=["linked"], valign=Gtk.Align.CENTER)
        self.level_buttons = []
        for i, label in enumerate(KB_LEVELS):
            b = Gtk.ToggleButton(label=label)
            if self.level_buttons:
                b.set_group(self.level_buttons[0])
            b.connect("toggled", self.on_level_toggled, i)
            levels.append(b)
            self.level_buttons.append(b)
        row.add_suffix(levels)
        g.add(row)

        self.kb_mode = Adw.ComboRow(title="Effect", model=Gtk.StringList.new([m[1] for m in KB_MODES]))
        self.kb_mode.connect("notify::selected", self.on_kb_effect_changed)
        g.add(self.kb_mode)

        dialog = Gtk.ColorDialog(with_alpha=False)
        self.kb_color_row = Adw.ActionRow(title="Color")
        self.kb_color = Gtk.ColorDialogButton(dialog=dialog, valign=Gtk.Align.CENTER)
        self.kb_color.connect("notify::rgba", self.on_kb_effect_changed)
        self.kb_color_row.add_suffix(self.kb_color)
        g.add(self.kb_color_row)

        self.kb_color2_row = Adw.ActionRow(title="Second color", subtitle="Breathing fades between the two")
        self.kb_color2 = Gtk.ColorDialogButton(dialog=dialog, valign=Gtk.Align.CENTER)
        self.kb_color2.connect("notify::rgba", self.on_kb_effect_changed)
        self.kb_color2_row.add_suffix(self.kb_color2)
        g.add(self.kb_color2_row)

        self.kb_speed = Adw.ComboRow(title="Speed", model=Gtk.StringList.new([s[1] for s in KB_SPEEDS]))
        self.kb_speed.connect("notify::selected", self.on_kb_effect_changed)
        g.add(self.kb_speed)
        return g

    def build_slash_group(self):
        g = Adw.PreferencesGroup(title="Slash lighting", description="The LED bar on the back of the lid")
        self.slash_group = g

        self.slash_enabled = Adw.SwitchRow(title="Enabled")
        self.slash_enabled.connect("notify::active", self.on_slash_changed)
        g.add(self.slash_enabled)

        row = Adw.ActionRow(title="Brightness")
        self.slash_brightness = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self.slash_brightness.set_size_request(220, -1)
        self.slash_brightness.set_valign(Gtk.Align.CENTER)
        self.slash_brightness.set_draw_value(False)
        for v in (0, 85, 170, 255):
            self.slash_brightness.add_mark(v, Gtk.PositionType.BOTTOM, None)
        self.slash_brightness.connect("value-changed", self.on_slash_changed)
        row.add_suffix(self.slash_brightness)
        g.add(row)

        self.slash_mode = Adw.ComboRow(title="Animation", model=Gtk.StringList.new(SLASH_MODES))
        self.slash_mode.connect("notify::selected", self.on_slash_changed)
        g.add(self.slash_mode)

        self.slash_interval = Adw.SpinRow.new_with_range(0, 5, 1)
        self.slash_interval.set_title("Pause between loops")
        self.slash_interval.set_subtitle("0 = continuous")
        self.slash_interval.connect("notify::value", self.on_slash_changed)
        g.add(self.slash_interval)
        return g

    def build_background_group(self):
        g = Adw.PreferencesGroup(title="Background")
        self.hotkeys = Adw.SwitchRow(
            title="Fn+F2 / Fn+F3 hotkeys",
            subtitle="Small helper that runs at login, handles the brightness keys, "
                     "and restores these settings after boot and sleep",
        )
        self.hotkeys.set_active(os.path.exists(AUTOSTART_PATH))
        self.hotkeys.connect("notify::active", self.on_hotkeys_toggled)
        g.add(self.hotkeys)

        reapply = Adw.ActionRow(title="Re-apply saved settings")
        btn = Gtk.Button(label="Apply", valign=Gtk.Align.CENTER)
        btn.connect("clicked", lambda *_: self.report(devices.apply_settings(self.cfg)))
        reapply.add_suffix(btn)
        g.add(reapply)
        return g

    def refresh_device_state(self):
        need_setup = (self.keyboard.present and not self.keyboard.accessible) or (
            self.slash.present and not self.slash.accessible
        )
        self.banner.set_revealed(need_setup)
        self.kb_group.set_sensitive(self.keyboard.present)
        self.kb_group.set_description(None if self.keyboard.present else "Keyboard controller not detected")
        self.slash_group.set_sensitive(self.slash.present)
        if not self.slash.present:
            self.slash_group.set_description("Slash controller not detected")

    def load_into_widgets(self):
        self.syncing = True
        k, s = self.cfg["keyboard"], self.cfg["slash"]
        self.level_buttons[k["brightness"]].set_active(True)
        self.kb_mode.set_selected([m[0] for m in KB_MODES].index(k["mode"]))
        self.kb_color.set_rgba(list_to_rgba(k["color"]))
        self.kb_color2.set_rgba(list_to_rgba(k["color2"]))
        self.kb_speed.set_selected([sp[0] for sp in KB_SPEEDS].index(k["speed"]))
        self.slash_enabled.set_active(s["enabled"])
        self.slash_brightness.set_value(s["brightness"])
        self.slash_mode.set_selected(SLASH_MODES.index(s["mode"]) if s["mode"] in SLASH_MODES else 0)
        self.slash_interval.set_value(s["interval"])
        self.syncing = False
        self.update_visibility()

    def update_visibility(self):
        mode = KB_MODES[self.kb_mode.get_selected()][0]
        self.kb_color_row.set_visible(mode in ("static", "breathe"))
        self.kb_color2_row.set_visible(mode == "breathe")
        self.kb_speed.set_visible(mode != "static")

    def report(self, errors):
        for e in errors or []:
            self.toasts.add_toast(Adw.Toast(title=e, timeout=4))

    def on_level_toggled(self, button, level):
        if self.syncing or not button.get_active():
            return
        self.cfg["keyboard"]["brightness"] = level
        config.save(self.cfg)
        try:
            self.keyboard.set_brightness(level)
        except devices.DeviceError as e:
            self.report([str(e)])

    def on_kb_effect_changed(self, *_):
        self.update_visibility()
        if self.syncing:
            return
        k = self.cfg["keyboard"]
        k["mode"] = KB_MODES[self.kb_mode.get_selected()][0]
        k["speed"] = KB_SPEEDS[self.kb_speed.get_selected()][0]
        k["color"] = rgba_to_list(self.kb_color.get_rgba())
        k["color2"] = rgba_to_list(self.kb_color2.get_rgba())
        config.save(self.cfg)
        try:
            self.keyboard.set_effect(k["mode"], tuple(k["color"]), tuple(k["color2"]), k["speed"])
        except devices.DeviceError as e:
            self.report([str(e)])

    def on_slash_changed(self, *_):
        if self.syncing:
            return
        s = self.cfg["slash"]
        s["enabled"] = self.slash_enabled.get_active()
        s["brightness"] = int(self.slash_brightness.get_value())
        s["mode"] = SLASH_MODES[self.slash_mode.get_selected()]
        s["interval"] = int(self.slash_interval.get_value())
        config.save(self.cfg)
        if self.slash_timer:
            GLib.source_remove(self.slash_timer)
        self.slash_timer = GLib.timeout_add(120, self.push_slash)

    def push_slash(self):
        self.slash_timer = None
        s = self.cfg["slash"]
        try:
            self.slash.apply(s["enabled"], s["mode"], s["brightness"], s["interval"])
        except devices.DeviceError as e:
            self.report([str(e)])
        return False

    def on_hotkeys_toggled(self, row, _pspec):
        if row.get_active():
            os.makedirs(os.path.dirname(AUTOSTART_PATH), exist_ok=True)
            with open(AUTOSTART_PATH, "w") as f:
                f.write(
                    "[Desktop Entry]\nType=Application\nName=ROG Lighting helper\n"
                    f'Exec="{sys.executable}" "{os.path.join(APP_ROOT, "rog-lighting")}" daemon\n'
                    "NoDisplay=true\nX-GNOME-Autostart-enabled=true\n"
                )
            if not daemon.is_running():
                subprocess.Popen(
                    [sys.executable, os.path.join(APP_ROOT, "rog-lighting"), "daemon"],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
        else:
            try:
                os.remove(AUTOSTART_PATH)
            except FileNotFoundError:
                pass
            pid = daemon.running_pid()
            if pid:
                os.kill(pid, signal.SIGTERM)

    def on_config_file_changed(self, _mon, _file, _other, event):
        if event == Gio.FileMonitorEvent.DELETED:
            return
        fresh = config.load()
        if fresh["keyboard"]["brightness"] != self.cfg["keyboard"]["brightness"]:
            self.cfg["keyboard"]["brightness"] = fresh["keyboard"]["brightness"]
            self.syncing = True
            self.level_buttons[fresh["keyboard"]["brightness"]].set_active(True)
            self.syncing = False


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        win = self.get_active_window() or Window(self)
        win.present()


def main():
    return App().run([sys.argv[0]])
