import logging
import sys
from tion_btle.lite import Lite

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

device = Lite(mac)

result = device.get()
print("crc is: " + bytes(device._crc).hex())

print("header._package_size = %s" % device._package_size)
print("header_commad_type = %s" % bytes(device._command_type).hex())

_LOGGER.debug("Result is %s " % result)

_LOGGER.info("Initial state: device is %s, light is %s, sound is %s, heater is %s, fan_speed is %d, heater_temp is %d",
              device.state,
              device.light,
              device.sound,
              device.heater,
              device.fan_speed,
              device.heater_temp
              )


