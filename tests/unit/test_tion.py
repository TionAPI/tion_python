import time
import pytest
import unittest.mock as mock

from bleak import exc

import tion_btle.tion
from tion_btle.tion import tion
from tion_btle.lite import LiteFamily
from tion_btle.lite import Lite
from tion_btle.s3 import S3
from tion_btle.s4 import S4
from tion_btle.tion import retry, MaxTriesExceededError


@pytest.mark.parametrize(
    "retries, repeats, succeed_run, t_delay",
    [
        pytest.param(0, 1, 0, 0, id="Succeed after first attempt with no retry"),
        pytest.param(1, 1, 0, 0, id="Succeed after first attempt with retry"),
        pytest.param(5, 4, 3, 0, id="Succeed after first 3rd attempt with 5 retry"),
        pytest.param(1, 2, 3, 0, id="Fail after one retry"),
        pytest.param(2, 2, 1, 2, id="Delay between retries"),
    ]
)
def test_retry(retries: int, repeats: int, succeed_run: int, t_delay: int):
    class TestRetry:
        count = 0

        @retry(retries=retries, delay=t_delay)
        def a(self, _succeed_run: int = 0):
            if self.count <= _succeed_run:
                self.count += 1
                if self.count - 1 == _succeed_run:
                    return "expected_result"

            raise exc.BleakError

    i = TestRetry()
    start = time.time()

    if succeed_run < repeats:
        assert i.a(_succeed_run=succeed_run) == "expected_result"
    else:
        with pytest.raises(MaxTriesExceededError) as c:
            i.a(_succeed_run=succeed_run)

    end = time.time()

    assert i.count == repeats
    assert end - start >= t_delay


class TestLogLevels:
    count = 0

    def setUp(self):
        self.count = 0
        tion_btle.tion._LOGGER.debug = mock.MagicMock(name='method')
        tion_btle.tion._LOGGER.info = mock.MagicMock(name='method')
        tion_btle.tion._LOGGER.warning = mock.MagicMock(name='method')
        tion_btle.tion._LOGGER.critical = mock.MagicMock(name='method')

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

    def test_warning_log_level(self):
        """Make sure that we have warnings for exception, but have no critical if all goes well finally"""
        @retry(retries=1)
        def warning():
            if self.count == 0:
                self.count += 1
                raise exc.BleakError
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
            raise exc.BleakError

        with mock.patch('tion_btle.tion._LOGGER.critical') as log_mock:
            try:
                critical()
            except MaxTriesExceededError:
                pass
            log_mock.assert_called()


@pytest.mark.parametrize(
    "raw_temperature, result",
    [
        [0x09, 9],
        [0xFF, -1]
    ]
)
def test_decode_temperature(raw_temperature, result):
    assert tion.decode_temperature(raw_temperature) == result


@pytest.mark.parametrize(
    "instance",
    [tion, LiteFamily, Lite, S3, S4]
)
def test_mac(instance):
    target = 'foo'
    t_tion = instance(target)
    assert t_tion.mac == target
