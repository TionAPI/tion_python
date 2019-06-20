from . import tion

class s3(tion):
  getDataCommand = bytearray([61, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 90])
  def get() -> dict:
    return self._decode_response(self._send_request(self.getDataCommand))
