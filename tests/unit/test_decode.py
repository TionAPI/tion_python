import pytest
from typing import ClassVar

import tion_btle


@pytest.mark.parametrize(
    "tion_instance, data, result",
    [
        [
            tion_btle.s3.S3,
            [0xb3, 0x10, 0x24, 0x14, 0x03, 0x00, 0x15, 0x14, 0x14, 0x8f,
             0x00, 0x0c, 0x0a, 0x00, 0x4b, 0x0a, 0x00, 0x33, 0x00, 0x5a],
            {
                'state': 'on',
                'heater': 'on',
                'sound': 'off',
                'mode': 'outside',
                'out_temp': 20,
                'in_temp': 20,
                'target_temp': 20,
                'fan_speed': 4,
                '_filter_remain': 143,
                'model': 'S3',
            }
        ],
        [
            tion_btle.lite.Lite,
            [0xcf, 0xd8, 0x02, 0x0f, 0x04, 0x09, 0x0f, 0x1a, 0x80, 0x8e, 0x05, 0x00, 0xe9, 0x8b, 0x05, 0x00, 0x17, 0xc2,
             0xe7, 0x00, 0x26, 0x1b, 0x18, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03,
             0x00, 0x04, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0a, 0x14, 0x19, 0x02, 0x04, 0x06,
             0x06, 0x18, 0x00],
            {
                'state': 'on',
                'heater': 'on',
                'sound': 'on',
                'mode': 'outside',
                'out_temp': 15,
                'in_temp': 9,
                'target_temp': 15,
                'fan_speed': 4,
                '_filter_remain': 175.7928587962963,
                'model': 'Lite',
                '_device_work_time': 18.284884259259258,
                '_electronic_work_time': 4.214814814814815,
                '_electronic_temp': 26,
                '_co2_auto_control': 0,
                '_filter_change_required': 0,
                'light': 'on',
            }
        ]
    ]
)
def test_decode(tion_instance: ClassVar[tion_btle.tion.tion], data: bytearray, result: dict):
    tion = tion_instance(mac="")
    tion._decode_response(data)
    for parameter in result.keys():
        assert getattr(tion, parameter) == result[parameter]

