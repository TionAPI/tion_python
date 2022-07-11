import time
import pytest
import unittest.mock as mock

from bleak import exc

import tion_btle.tion
from tion_btle.tion import Tion
from tion_btle.lite import TionLiteFamily
from tion_btle.lite import TionLite
from tion_btle.s3 import TionS3
from tion_btle.s4 import TionS4
from tion_btle.tion import retry, MaxTriesExceededError


@pytest.mark.asyncio
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
async def test_retry(retries: int, repeats: int, succeed_run: int, t_delay: int):
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
        assert await i.a(_succeed_run=succeed_run) == "expected_result"
    else:
        with pytest.raises(MaxTriesExceededError) as c:
            await i.a(_succeed_run=succeed_run)

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

    @pytest.mark.asyncio
    async def test_debug_log_level(self):
        @retry(retries=0)
        async def debug():
            pass

        with mock.patch('tion_btle.tion._LOGGER') as log_mock:
            await debug()
            log_mock.debug.assert_called()
            log_mock.info.assert_not_called()
            log_mock.warning.assert_not_called()
            log_mock.critical.assert_not_called()

    @pytest.mark.asyncio
    async def test_warning_log_level(self):
        """Make sure that we have warnings for exception, but have no critical if all goes well finally"""
        @retry(retries=1)
        async def warning():
            if self.count == 0:
                self.count += 1
                raise exc.BleakError
            else:
                pass

        with mock.patch('tion_btle.tion._LOGGER') as log_mock:
            await warning()
            log_mock.warning.assert_called()
            log_mock.critical.assert_not_called()

    @pytest.mark.asyncio
    async def test_critical_log_level(self):
        """Make sure that we have message at critical level if all goes bad"""
        @retry(retries=0)
        async def critical():
            raise exc.BleakError

        with mock.patch('tion_btle.tion._LOGGER.critical') as log_mock:
            try:
                await critical()
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
    assert Tion.decode_temperature(raw_temperature) == result


@pytest.mark.parametrize(
    "instance",
    [Tion, TionLiteFamily, TionLite, TionS3, TionS4]
)
def test_mac(instance):
    target = 'foo'
    t_tion = instance(target)
    assert t_tion.mac == target
