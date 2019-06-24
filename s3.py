from . import tion
from bluepy import btle

class s3(tion):
  getDataCommand = bytearray([61, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 90])
  statuses = [ 'off', 'on' ]
  command_suffix = 90

  command_PAIR = 5
  command_REQUEST_PARAMS = 1
  command_SET_PARAMS = 2

  topic_NOTIFY = 0xb3
  topic_WRITE_NO_RESPONSE = 61

  _btle = btle.Peripheral(None)

  def create_command(self, topic: int, command: int) -> bytearray:
    return bytearray([topic, command, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, self.command_suffix])

  def _get_pair_command(self) -> bytearray:
    return self.create_command(self.topic_WRITE_NO_RESPONSE, self.command_PAIR)
  
  def _get_status_command(self) -> bytearray:
    return self.create_command(self.topic_WRITE_NO_RESPONSE, self.command_REQUEST_PARAMS)

  def _btle_send_command(self, command: bytearray): None
    topic = command.pop(0)
    self._btle.writeCharacteristic(topic, command)

  def _btle_connect(self, mac):
    self._btle.connect(mac, btle.ADDR_TYPE_RANDOM)
    self._btle_send_command(self._get_pair_command())

  def _btle_disconnect(self):
     self._btle.disconnect()

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

  def _send_request(self, mac: str, request: bytearray) -> bytearray:
    self._btle_connect(mac)
    self._btle_send_command(request)
    self._btle_disconnect()
    return self._btle.readCharacteristic(self.topic_NOTIFY)
    return bytearray([0xB3, 0x10, 0x26, 0x0F, 0x02, 0x00, 0x17, 0x17, 0x17, 0x60, 0x01, 0x17, 0x32, 0x00, 0x8C, 0x03, 0x00, 0x33, 0x00, 0x5A])

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
    return self._decode_response(self._send_request(mac, self.create_command(self.topic_WRITE_NO_RESPONSE, self.command_REQUEST_PARAMS)))
