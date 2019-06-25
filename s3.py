if __package__ == "":
  from tion import tion
else:
  from . import tion

from bluepy import btle

class s3(tion):
  uuid = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
  characteristic = None
  statuses = [ 'off', 'on' ]
  command_prefix = 61
  command_suffix = 90

  command_PAIR = 5
  command_REQUEST_PARAMS = 1
  command_SET_PARAMS = 2

  _btle = btle.Peripheral(None)

  def pair(self, mac: str):
    self._btle.connect(mac, btle.ADDR_TYPE_RANDOM)
    characteristic = self._btle.getServiceByUUID(self.uuid).getCharacteristics()[0]
    characteristic.write(bytes(self._get_pair_command()))
    self._btle.disconnect()

  def create_command(self, command: int) -> bytearray:
    command_special = 1 if command == self.command_PAIR else 0
    return bytearray([self.command_prefix, command, command_special, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, self.command_suffix])

  def _get_pair_command(self) -> bytearray:
    return self.create_command(self.command_PAIR)
  
  def _get_status_command(self) -> bytearray:
    return self.create_command(self.command_REQUEST_PARAMS)

  def _process_mode(self, mode_code: int) -> str:
    modes = [ 'recuperation', 'mied' ]
    try:
      result = modes[mode_code]
    except IndexError:
      result = 'outside'
    return result
  
  def _process_status(self, code: int) -> str:
    try:
      result = self.statuses[code]
    except IndexError:
      result = 'unknown'
    return result

  def _decode_response(self, response: bytearray) -> dict:
    return {
      "heater": self._process_status(response[2] & 1),
      "status": self._process_status(response[2] >> 1 & 1),
      "sound": self._process_status(response[2] >> 3 & 1),
      "mode": self._process_mode(int(list("{:02x}".format(response[2]))[0])),
      "fan_speed": int(list("{:02x}".format(response[2]))[1]),
      "heater_temp": response[3],
      "in_temp": response[8],
      "filter_remain": response[10]*256 + response[9],
      "time": "{}:{}".format(response[11],response[12]),
      "request_error_code": response[13],
      "fw_version": "{:02x}{:02x}".format(response[16],response[17])
    }

  def get(self, mac: str) -> dict:
    response = ""
    self._btle.connect(mac, btle.ADDR_TYPE_RANDOM)
    response =  self._btle.getServiceByUUID(self.uuid).getCharacteristics()[0].read()
    self._btle.disconnect()
    return self._decode_response(response)
