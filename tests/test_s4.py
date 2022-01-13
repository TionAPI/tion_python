import logging
import sys
import time
from tion_btle.s4 import S4


def read_state(tion: S4):
    result = tion.get()

    _LOGGER.debug("Result is %s " % result)

    _LOGGER.info("Initial state: device is %s, light is %s, sound is %s, heater is %s, fan_speed is %d, target_temp is %d",
                 tion.state,
                 tion.light,
                 tion.sound,
                 tion.heater,
                 tion.fan_speed,
                 tion.heater_temp)


def pause(interval: int = 10):
    _LOGGER.info("Sleeping %s seconds...", interval)
    time.sleep(interval)


logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel("DEBUG")
try:
    mac = sys.argv[1]
    if mac == 'discover':
        _LOGGER.debug("%s", sys.argv)
        mac = 'dummy'
except IndexError:
    mac = "dummy"

device = S4(mac)

sleep_step: int = 10
original_state = device.state
original_fan_speed = device.fan_speed

tests = {
    'state': {
        'on': ['off', 'on'],
        'off': ['on'],
    },
    'heater': {
        'on': ['off', 'on'],
        'off': ['on', 'off'],
    },
    'mode': {
        'recirculation': ['outside', 'recirculation'],
        'outside': ['recirculation', 'recirculation'],
    },
    'fan_speed': {}
}

read_state(device)
pause(sleep_step)

for test in tests.keys():
    _LOGGER.info("Testing %s", test)
    states = tests[test][getattr(device, test)] if test != 'fan_speed' else [2, 5]
    for state in states:
        _LOGGER.info("Going to set %s to %s", test, state)
        device.set({test: state})
        pause(sleep_step)
        read_state(device)
        pause(sleep_step)

# restoring original state
if original_state == 'off':
    device.set({'state': original_state})
elif original_fan_speed != 5:
    device.set({'fan_speed': original_fan_speed})
