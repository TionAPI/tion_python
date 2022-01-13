import time
import unittest
import unittest.mock as mock
import bluepy

import tion_btle.tion
from tion_btle.tion import tion
from tion_btle.lite import LiteFamily
from tion_btle.lite import Lite
from tion_btle.s3 import S3
from tion_btle.s4 import S4
from tion_btle.tion import retry, MaxTriesExceededError


class retryTests(unittest.TestCase):
    def setUp(self):
        self.count = 0
        tion_btle.tion._LOGGER.debug = mock.MagicMock(name='method')
        tion_btle.tion._LOGGER.info = mock.MagicMock(name='method')
        tion_btle.tion._LOGGER.warning = mock.MagicMock(name='method')
        tion_btle.tion._LOGGER.critical = mock.MagicMock(name='method')

    def test_success_single_try(self):
        @retry(retries=0)
        def a():
            self.count += 1
            return "expected_result"
        self.assertEqual(a(), "expected_result")
        self.assertEqual(self.count, 1)

    def test_success_two_tries(self):
        @retry(retries=1)
        def a():
            self.count += 1
            return "expected_result"
        self.assertEqual(a(), "expected_result")
        self.assertEqual(self.count, 1)

    def test_failure_two_tries(self):
        @retry(retries=1)
        def a():
            self.count += 1
            raise Exception()
        try:
            a()
            self.fail()
        except MaxTriesExceededError:
            self.assertEqual(self.count, 2)

    def test_success_after_third_try(self):
        @retry(retries=5)
        def a():
            self.count += 1
            if self.count == 3:
                return "expected_result"
            else:
                raise Exception()
        self.assertEqual(a(), "expected_result")
        self.assertEqual(self.count, 3)

    def test_delay(self):
        t_delay = 2

        @retry(retries=2, delay=t_delay)
        def a():
            self.count += 1
            if self.count == 2:
                return "expected_result"
            else:
                raise Exception()

        start = time.time()
        a()
        end = time.time()
        self.assertGreaterEqual(end-start, t_delay)

    def test_debug_log_level(self):
        @retry(retries=0)
        def debug():
            pass

        with mock.patch('tion_btle.tion._LOGGER') as log_mock:
            debug()
            log_mock.debug.assert_called()
            log_mock.info.assert_not_called()
            log_mock.warning.assert_not_called()
            log_mock.critical.assert_not_called()

    def test_info_log_level(self):
        """only debug and info messages if we have just BTLEDisconnectError and BTLEInternalError"""
        @retry(retries=1)
        def info(_e):
            if self.count == 0:
                self.count += 1
                raise _e(message="foo")
            else:
                pass

        for e in (bluepy.btle.BTLEDisconnectError, bluepy.btle.BTLEInternalError):
            self.count = 0
            with self.subTest(exception=e):
                with mock.patch('tion_btle.tion._LOGGER') as log_mock:
                    info(e)
                    log_mock.info.assert_called()
                    log_mock.warning.assert_not_called()
                    log_mock.critical.assert_not_called()

    def test_warning_log_level(self):
        """Make sure that we have warnings for exception, but have no critical if all goes well finally"""
        @retry(retries=1)
        def warning():
            if self.count == 0:
                self.count += 1
                raise Exception
            else:
                pass

        with mock.patch('tion_btle.tion._LOGGER') as log_mock:
            warning()
            log_mock.warning.assert_called()
            log_mock.critical.assert_not_called()

    def test_critical_log_level(self):
        """Make sure that we have message at critical level if all goes bad"""
        @retry(retries=0)
        def critical():
            raise Exception

        with mock.patch('tion_btle.tion._LOGGER.critical') as log_mock:
            try:
                critical()
            except MaxTriesExceededError:
                pass
            log_mock.assert_called()

    def test_MaxTriesExceededError(self):
        @retry(retries=0)
        def e():
            raise Exception

        with self.assertRaises(MaxTriesExceededError) as c:
            e()


class TionTests(unittest.TestCase):
    def setUp(self):
        self.instances = [tion, LiteFamily, Lite, S3, S4]

    def test_DecodeTemperature(self):
        self.assertEqual(tion.decode_temperature(0x09), 9, "Should be 9")
        self.assertEqual(tion.decode_temperature(0xFF), -1, "Should be -1")

    def test_mac(self):
        """mac property should be same as in init"""
        target = 'foo'
        for s in self.instances:
            with self.subTest(test_instance=s):
                t_tion = s(target)
                self.assertEqual(t_tion.mac, target)
