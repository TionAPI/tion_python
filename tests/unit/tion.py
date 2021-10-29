import sys
import unittest
import unittest.mock as mock
from unittest.mock import MagicMock
sys.modules['bluepy'] = MagicMock()
sys.modules['bluepy.btle'] = MagicMock()
import tion_btle.tion  # noqa: E402


class TionTests(unittest.TestCase):
    def setUp(self):
        self.patch = mock.patch('tion_btle.tion.tion.__init__', return_value=None)
        self.patch.start()
        self._tion = tion_btle.tion.tion("")

    def tearDown(self):
        self.patch.stop()

    def test___detect_heating_state(self):
        # state, in, out, target, heater
        _variants = [
            ["on",  -2, 21, 20, "on"],
            ["on",  15, 21, 20, "on"],
            ["off", 15, 21, 16, "on"],
            ["off", 15, 21, 20, "off"],
        ]

        for expect, in_temp, out_temp, heater_temp, heater in _variants:
            with self.subTest(expect=expect,
                              in_temp=in_temp, out_temp=out_temp, heater_temp=heater_temp, heater=heater):
                # call private __detect_heating_state from tion class
                self._tion._tion__detect_heating_state(in_temp, out_temp, heater_temp, heater)
                self.assertEqual(self._tion.heating, expect)


if __name__ == '__main__':
    unittest.main()
