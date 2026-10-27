import fcntl
import glob
import os

ASUS_VID = 0x0B05
KEYBOARD_PID = 0x19B6
SLASH_PID = 0x193B


def _hidiocsfeature(length):
    return (3 << 30) | (length << 16) | (ord("H") << 8) | 0x06


def find_hidraw(vid, pid):
    for node in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            with open(os.path.join(node, "device", "uevent")) as f:
                uevent = f.read()
        except OSError:
            continue
        for line in uevent.splitlines():
            if line.startswith("HID_ID="):
                _bus, v, p = line[len("HID_ID="):].split(":")
                if int(v, 16) == vid and int(p, 16) == pid:
                    return "/dev/" + os.path.basename(node)
    return None


class DeviceError(Exception):
    pass


class HidDevice:
    VID = ASUS_VID
    PID = 0
    PACKET_LEN = 64
    NAME = "device"

    def __init__(self):
        self.path = find_hidraw(self.VID, self.PID)

    @property
    def present(self):
        return self.path is not None

    @property
    def accessible(self):
        return self.present and os.access(self.path, os.R_OK | os.W_OK)

    def _send(self, packets):
        if not self.present:
            raise DeviceError(f"{self.NAME} not found")
        try:
            fd = os.open(self.path, os.O_RDWR)
        except PermissionError:
            raise DeviceError(
                f"No permission to open {self.path}. Run install.sh to add the udev rule."
            )
        except OSError as e:
            raise DeviceError(f"Could not open {self.path}: {e}")
        try:
            for pkt in packets:
                buf = bytearray(self.PACKET_LEN)
                buf[: len(pkt)] = bytes(pkt)
                fcntl.ioctl(fd, _hidiocsfeature(len(buf)), buf)
        except OSError as e:
            raise DeviceError(f"Write to {self.NAME} failed: {e}")
        finally:
            os.close(fd)


class Keyboard(HidDevice):
    PID = KEYBOARD_PID
    PACKET_LEN = 17
    NAME = "keyboard"

    INIT = [0x5A] + list(b"ASUS Tech.Inc.") + [0x00]
    SET = [0x5D, 0xB5]
    APPLY = [0x5D, 0xB4]

    MODES = {"static": 0, "breathe": 1, "cycle": 2, "rainbow": 3}
    SPEEDS = {"slow": 0xE1, "medium": 0xEB, "fast": 0xF5}

    def set_brightness(self, level):
        level = max(0, min(3, int(level)))
        self._send([self.INIT, [0x5A, 0xBA, 0xC5, 0xC4, level]])

    def set_effect(self, mode, color=(255, 255, 255), color2=(0, 0, 0), speed="medium"):
        m = [0] * self.PACKET_LEN
        m[0], m[1] = 0x5D, 0xB3
        m[3] = self.MODES[mode]
        if mode in ("cycle", "rainbow"):
            m[4] = 0xFF
        else:
            m[4], m[5], m[6] = color
        m[7] = self.SPEEDS.get(speed, 0xEB)
        if mode == "breathe":
            m[9] = 1
            m[10], m[11], m[12] = color2
        self._send([m, self.SET, self.APPLY])


class Slash(HidDevice):
    PID = SLASH_PID
    PACKET_LEN = 128
    NAME = "Slash lighting"

    MODES = {
        "Static": None,
        "Bounce": 0x10,
        "Slash": 0x12,
        "Loading": 0x13,
        "Bit Stream": 0x1D,
        "Transmission": 0x1A,
        "Flow": 0x19,
        "Flux": 0x25,
        "Phantom": 0x24,
        "Spectrum": 0x26,
        "Hazard": 0x32,
        "Interfacing": 0x33,
        "Ramp": 0x34,
        "Game Over": 0x42,
        "Start": 0x43,
        "Buzzer": 0x44,
    }

    @staticmethod
    def _p(*data):
        return [0x5E, *data]

    def init(self):
        self._send([
            self._p(0xD7, 0x00, 0x00, 0x01, 0xAC),
            self._p(0xD2, 0x02, 0x01, 0x08, 0xAB),
        ])

    def set_enabled(self, enabled):
        self._send([self._p(0xD8, 0x02, 0x00, 0x01, 0x00 if enabled else 0x80)])

    def set_options(self, enabled, brightness, interval):
        brightness = max(0, min(255, int(brightness)))
        interval = max(0, min(5, int(interval)))
        self._send([self._p(
            0xD3, 0x03, 0x01, 0x08, 0xAB, 0xFF, 0x01,
            0x01 if enabled else 0x00, 0x06, brightness, 0xFF, interval,
        )])

    def set_mode(self, name, brightness=255):
        code = self.MODES[name]
        if code is None:
            level = max(0, min(255, int(brightness)))
            self._send([
                self._p(0xD2, 0x02, 0x01, 0x08, 0xAC),
                self._p(0xD3, 0x00, 0x01, 0x07, *([level] * 7)),
            ])
            return
        self._send([
            self._p(0xD2, 0x03, 0x00, 0x0C),
            self._p(0xD3, 0x04, 0x00, 0x0C, 0x01, code, 0x02, 0x19,
                    0x03, 0x13, 0x04, 0x11, 0x05, 0x12, 0x06, 0x13),
        ])

    def apply(self, enabled, mode, brightness, interval):
        self.init()
        self.set_enabled(enabled)
        if enabled:
            self.set_mode(mode, brightness)
        self.set_options(enabled, brightness, interval)


def apply_settings(cfg, keyboard=True, slash=True):
    errors = []
    if keyboard:
        kb = Keyboard()
        k = cfg["keyboard"]
        try:
            kb.set_effect(k["mode"], tuple(k["color"]), tuple(k["color2"]), k["speed"])
            kb.set_brightness(k["brightness"])
        except DeviceError as e:
            errors.append(str(e))
    if slash:
        sl = Slash()
        s = cfg["slash"]
        try:
            sl.apply(s["enabled"], s["mode"], s["brightness"], s["interval"])
        except DeviceError as e:
            errors.append(str(e))
    return errors
