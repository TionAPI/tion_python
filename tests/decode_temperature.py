#!/usr/bin/python
import sys
import os
import unittest

PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from tion_btle import tion


class TestDecodeTemperature(unittest.TestCase, tion.tion):
    def test_positive(self):
        self.assertEqual(self.decode_temperature(0x09), 9, "Should be 9")

    def test_negative(self):
        self.assertEqual(self.decode_temperature(0xFF), -1, "Should be -1")


if __name__ == '__main__':
    unittest.main()
