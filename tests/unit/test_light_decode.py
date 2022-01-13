#!/usr/bin/python
import sys
import os
import unittest

PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from tion_btle.lite import Lite


class LiteTests(unittest.TestCase):
    data = bytearray()

    def test_decode(self):
        self.lite = Lite("dummy")
        self.lite._decode_response(self.data)
        name_value = [
            ('state', 'on'),
            ('heater', 'on'),
            ('sound', 'on'),
            ('mode', 'outside'),
            ('out_temp', 15),
            ('in_temp', 9),
            ('target_temp', 15),
            ('fan_speed', 4),
            ('_filter_remain', 175.7928587962963),
            ('model', 'Lite'),
            ('_device_work_time', 18.284884259259258),
            ('_electronic_work_time', 4.214814814814815),
            ('_electronic_temp', 26),
            ('_co2_auto_control', 0),
            ('_filter_change_required', 0),
            ('light', 'on')
        ]
        for s in name_value:
            with self.subTest(s[0]):
                self.assertEqual(getattr(self.lite, s[0]), s[1], "%s should be '%s'" % (s[0], s[1]) )


LiteTests.data = bytearray([
    0xcf, 0xd8, 0x02, 0x0f, 0x04, 0x09, 0x0f, 0x1a, 0x80, 0x8e, 0x05, 0x00, 0xe9, 0x8b, 0x05, 0x00, 0x17, 0xc2,
    0xe7, 0x00, 0x26, 0x1b, 0x18, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03,
    0x00, 0x04, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0a, 0x14, 0x19, 0x02, 0x04, 0x06,
    0x06, 0x18, 0x00
])

if __name__ == '__main__':
    unittest.main()
