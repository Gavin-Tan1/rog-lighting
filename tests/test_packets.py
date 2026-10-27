import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rog_lighting import config, devices  # noqa: E402


def capture(device_cls):
    with mock.patch.object(devices, "find_hidraw", return_value="/dev/null"):
        dev = device_cls()
    sent = []
    dev._send = lambda packets: sent.extend(packets)
    return dev, sent


class KeyboardPackets(unittest.TestCase):
    def test_brightness(self):
        kb, sent = capture(devices.Keyboard)
        kb.set_brightness(2)
        self.assertEqual(sent[0][:2], [0x5A, 0x41])
        self.assertEqual(sent[1], [0x5A, 0xBA, 0xC5, 0xC4, 2])

    def test_brightness_is_clamped(self):
        kb, sent = capture(devices.Keyboard)
        kb.set_brightness(9)
        self.assertEqual(sent[-1][4], 3)

    def test_static_effect_then_set_and_apply(self):
        kb, sent = capture(devices.Keyboard)
        kb.set_effect("static", (10, 20, 30))
        self.assertEqual(sent[0][:7], [0x5D, 0xB3, 0, 0, 10, 20, 30])
        self.assertEqual(sent[1], [0x5D, 0xB5])
        self.assertEqual(sent[2], [0x5D, 0xB4])

    def test_breathe_uses_second_color(self):
        kb, sent = capture(devices.Keyboard)
        kb.set_effect("breathe", (1, 2, 3), (4, 5, 6), "fast")
        m = sent[0]
        self.assertEqual(m[3], 1)
        self.assertEqual(m[7], 0xF5)
        self.assertEqual(m[9:13], [1, 4, 5, 6])


class SlashPackets(unittest.TestCase):
    def test_all_packets_use_report_0x5e(self):
        sl, sent = capture(devices.Slash)
        sl.apply(True, "Bounce", 200, 2)
        self.assertTrue(sent)
        self.assertTrue(all(p[0] == 0x5E for p in sent))

    def test_mode_byte(self):
        sl, sent = capture(devices.Slash)
        sl.set_mode("Flow")
        self.assertEqual(sent[1][6], 0x19)

    def test_options(self):
        sl, sent = capture(devices.Slash)
        sl.set_options(True, 300, 9)
        p = sent[0]
        self.assertEqual(p[8], 0x01)
        self.assertEqual(p[10], 255)
        self.assertEqual(p[12], 5)

    def test_disabled_skips_mode(self):
        sl, sent = capture(devices.Slash)
        sl.apply(False, "Bounce", 100, 0)
        self.assertNotIn(0x0C, [p[4] for p in sent if len(p) > 4 and p[1] == 0xD2])


class ConfigValidation(unittest.TestCase):
    def test_bad_values_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "settings.json")
            with open(path, "w") as f:
                json.dump({
                    "keyboard": {"brightness": 7, "mode": "disco", "color": "red"},
                    "slash": {"mode": "Nope", "interval": -4, "extra": 1},
                }, f)
            with mock.patch.object(config, "CONFIG_PATH", path):
                cfg = config.load()
        self.assertEqual(cfg["keyboard"]["brightness"], 3)
        self.assertEqual(cfg["keyboard"]["mode"], "static")
        self.assertEqual(cfg["keyboard"]["color"], [255, 255, 255])
        self.assertEqual(cfg["slash"]["mode"], "Bounce")
        self.assertEqual(cfg["slash"]["interval"], 0)
        self.assertNotIn("extra", cfg["slash"])

    def test_missing_file_gives_defaults(self):
        with mock.patch.object(config, "CONFIG_PATH", "/nonexistent/settings.json"):
            self.assertEqual(config.load(), config.DEFAULTS)


if __name__ == "__main__":
    unittest.main()
