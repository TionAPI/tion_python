from . import tion

class s3(tion):
  getDataCommand = bytearray([61, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 90])
  statuses = [ 'off', 'on' ]

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

  def _send_request(self, request: bytearray) -> bytearray:
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

  def get(self) -> dict:
    return self._decode_response(self._send_request(self.getDataCommand))
