import copy
import json
import os

CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "rog-lighting"
)
CONFIG_PATH = os.path.join(CONFIG_DIR, "settings.json")

DEFAULTS = {
    "keyboard": {
        "brightness": 2,
        "mode": "static",
        "color": [255, 255, 255],
        "color2": [0, 0, 0],
        "speed": "medium",
    },
    "slash": {
        "enabled": True,
        "mode": "Bounce",
        "brightness": 170,
        "interval": 0,
    },
}

KB_MODES = ("static", "breathe", "cycle", "rainbow")
KB_SPEEDS = ("slow", "medium", "fast")


def _int_in(value, lo, hi, default):
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(lo, min(hi, value))


def _color(value, default):
    if isinstance(value, list) and len(value) == 3:
        return [_int_in(c, 0, 255, 0) for c in value]
    return list(default)


def _sanitize(cfg, slash_modes):
    d, k, s = DEFAULTS, cfg["keyboard"], cfg["slash"]
    k["brightness"] = _int_in(k["brightness"], 0, 3, d["keyboard"]["brightness"])
    if k["mode"] not in KB_MODES:
        k["mode"] = d["keyboard"]["mode"]
    if k["speed"] not in KB_SPEEDS:
        k["speed"] = d["keyboard"]["speed"]
    k["color"] = _color(k["color"], d["keyboard"]["color"])
    k["color2"] = _color(k["color2"], d["keyboard"]["color2"])
    s["enabled"] = bool(s["enabled"])
    s["brightness"] = _int_in(s["brightness"], 0, 255, d["slash"]["brightness"])
    s["interval"] = _int_in(s["interval"], 0, 5, d["slash"]["interval"])
    if s["mode"] not in slash_modes:
        s["mode"] = d["slash"]["mode"]
    return cfg


def load():
    from .devices import Slash

    cfg = copy.deepcopy(DEFAULTS)
    try:
        with open(CONFIG_PATH) as f:
            saved = json.load(f)
        for section in cfg:
            if isinstance(saved.get(section), dict):
                cfg[section].update(
                    {key: v for key, v in saved[section].items() if key in cfg[section]}
                )
    except (OSError, ValueError, AttributeError):
        pass
    return _sanitize(cfg, Slash.MODES)


def save(cfg):
    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_PATH)
