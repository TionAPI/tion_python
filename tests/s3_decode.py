#!/usr/bin/python
import sys
import os
import unittest

PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from tion_btle.s3 import S3


class TestLite(unittest.TestCase):
    data = bytearray()

    def test_decode(self):
        self.lite = S3("dummy")
        self.lite._decode_response(self.data)
        name_value = [
            ('state', 'on'),
            ('heater', 'on'),
            ('sound', 'off'),
            ('mode', 'outside'),
            ('out_temp', 20),
            ('in_temp', 20),
            ('target_temp', 20),
            ('fan_speed', 4),
            ('_filter_remain', 143),
            ('model', 'S3'),
        ]
        for s in name_value:
            with self.subTest(s[0]):
                self.assertEqual(getattr(self.lite, s[0]), s[1], "%s should be '%s'" % (s[0], s[1]) )


TestLite.data = bytearray([
    0xb3, 0x10, 0x24, 0x14, 0x03, 0x00, 0x15, 0x14, 0x14, 0x8f, 0x00, 0x0c, 0x0a, 0x00, 0x4b, 0x0a, 0x00, 0x33, 0x00,
    0x5a
])

if __name__ == '__main__':
    unittest.main()
