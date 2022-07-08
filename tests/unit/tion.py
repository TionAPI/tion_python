import pytest

from tion_btle.tion import Tion


@pytest.mark.parametrize(
    "heater, heater_temp, in_temp, out_temp, result",
    [
        ["on",  20, -2, 21, "on"],
        ["on",  20, 15, 21, "on"],
        ["on",  16, 15, 21, "off"],
        ["off", 20, 15, 21, "off"],
    ])
def test__detect_heating_state(heater, in_temp, out_temp, heater_temp, result):
    """Test heating detection"""

    tion = Tion(mac="")
    tion.heater = heater
    tion._in_temp = in_temp
    tion._out_temp = out_temp
    tion._heater_temp = heater_temp

    assert tion.heating == result
