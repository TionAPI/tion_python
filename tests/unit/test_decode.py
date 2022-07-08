import pytest
from typing import List, Type, Union

import tion_btle


scenarios: List[dict[str, Union[Type[tion_btle.Tion], bytearray, dict]]] = [
    {
        "instance": tion_btle.s3.TionS3,
        "data":  [0xb3, 0x10, 0x24, 0x14, 0x03, 0x00, 0x15, 0x14, 0x14, 0x8f, 0x00, 0x0c, 0x0a, 0x00, 0x4b, 0x0a, 0x00,
                  0x33, 0x00, 0x5a],
        "results": {
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
    },
    {
        "instance": tion_btle.lite.TionLite,
        "data": [0xcf, 0xd8, 0x02, 0x0f, 0x04, 0x09, 0x0f, 0x1a, 0x80, 0x8e, 0x05, 0x00, 0xe9, 0x8b, 0x05, 0x00, 0x17, 0xc2,
             0xe7, 0x00, 0x26, 0x1b, 0x18, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03,
             0x00, 0x04, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0a, 0x14, 0x19, 0x02, 0x04, 0x06,
             0x06, 0x18, 0x00],
        "results": {
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
    },
    {
        "instance": tion_btle.TionS4,
        "data": [0x2f, 0x51, 0x00, 0x19, 0x04, 0x0e, 0x10, 0x1b, 0x26, 0x3b, 0x6e, 0x07, 0x00, 0xfa, 0x4e, 0x07, 0x00,
             0x06, 0xff, 0xe5, 0x00, 0xa6, 0xe9, 0x22, 0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0x00],
        "results": {
            'state': 'on',
            'heater': 'on',
            'sound': 'on',
            'mode': 'outside',
            'out_temp': 16,
            'in_temp': 14,
            'target_temp': 25,
            'fan_speed': 4,
            '_filter_remain': 174.45636574074075,
            'model': 'S4',
        }
    }
]


def pytest_generate_tests(metafunc):
    global scenarios
    tests = []

    for scenario in scenarios:
        tion_type: Type[tion_btle.Tion] = scenario["instance"]
        tion: tion_btle.Tion = tion_type(mac="")
        tion._decode_response(response=scenario["data"])

        for k in scenario["results"].keys():
            v = scenario["results"][k]
            _id = f"{tion.__class__.__name__}-{k}"
            tests.append(pytest.param(_id, getattr(tion, k), v, id=_id))

    metafunc.parametrize("parameter,decoded_value,expected_value", tests)


def test_param(parameter, decoded_value, expected_value):
    assert decoded_value == expected_value
