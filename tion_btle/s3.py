import logging

if __package__ == "":
    from tion_btle.tion import tion, TionException
else:
    from .tion import tion, TionException

from bluepy import btle

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


class S3(tion):
    uuid = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    uuid_write = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    uuid_notify = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
    write = None
    notify = None

    _btle = None

    command_prefix = 61
    command_suffix = 90

    command_PAIR = 5
    command_REQUEST_PARAMS = 1
    command_SET_PARAMS = 2

    def __init__(self, mac: str):
        super().__init__(mac)

        # S3-specific properties
        self._timer: bool = False
        self._time: str = "unknown"
        self._productivity: int = 0
        self._fw_version: str = "unknown"

        if self.mac == "dummy":
            self._dummy_data = bytearray([0xb3, 0x10, 0x24, 0x14, 0x03, 0x00, 0x15, 0x14, 0x14, 0x8f, 0x00, 0x0c,
                                          0x0a, 0x00, 0x4b, 0x0a, 0x00, 0x33, 0x00, 0x5a])

    @property
    def pair_command(self) -> bytearray:
        return self.create_command(self.command_PAIR)

    @property
    def get_status_command(self) -> bytearray:
        return self.create_command(self.command_REQUEST_PARAMS)

    def __try_get_state(self) -> bytearray:
        response = self._btle.getServiceByUUID(self.uuid).getCharacteristics()[0].read()
        _LOGGER.debug("Response is %s", bytes(response).hex())
        return response

    def _pair(self):
        _LOGGER.debug("Sending pair command")
        self._send_request(self.pair_command)
        _LOGGER.debug("Done!")

    def create_command(self, command: int) -> bytearray:
        command_special = 1 if command == self.command_PAIR else 0
        return bytearray([self.command_prefix, command, command_special, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          self.command_suffix])

    def _get_data_from_breezer(self) -> bytearray:
        have_data_from_breezer: bool = False
        self._do_action(self._try_write, request=self.get_status_command)

        i = 0
        try:
            while i < 10:
                if self._delegation.haveNewData:
                    have_data_from_breezer = True
                    break
                else:
                    self._btle.waitForNotifications(1.0)
                i += 1
            else:
                _LOGGER.debug("Waiting too long for data")
                self.notify.read()
        except btle.BTLEDisconnectError as e:
            _LOGGER.debug("Got %s while waiting for notification", str(e))

        if have_data_from_breezer:
            self._data = self._delegation.data
            result = self._data

        else:
            raise TionException("s3 _get_data_from_breezer", "Could not get breezer state")

        return result

    def _decode_response(self, response: bytearray):
        _LOGGER.debug("Data is %s", bytes(response).hex())
        try:
            self._fan_speed = int(list("{:02x}".format(response[2]))[1])
            self._mode = int(list("{:02x}".format(response[2]))[0])
            self._heater = response[4] & 1
            self._state = response[4] >> 1 & 1
            self._target_temp = response[3]
            self._sound = response[4] >> 3 & 1
            self._out_temp = self.decode_temperature(response[7])
            self._in_temp = self.decode_temperature(response[8])
            self._filter_remain = response[10] * 256 + response[9]
            self._error_code = response[13]

            self._timer = self._process_status(response[4] >> 2 & 1)
            self._time = "{}:{}".format(response[11], response[12])
            self._productivity = response[14]
            self._fw_version = "{:02x}{:02x}".format(response[18], response[17])

        except IndexError as e:
            raise TionException("s3 _decode_response", "Got bad response from Tion '%s': %s while parsing" % (response, str(e)))

    def _generate_model_specific_json(self) -> dict:
        return {
            "code": 200,
            "timer": self._timer,
            "time": self._time,
            "productivity": self._productivity,
            "fw_version": self._fw_version,
        }

    def _encode_request(self, request: dict) -> bytearray:
        new_settings = self.create_command(self.command_SET_PARAMS)
        new_settings[2] = int(request["fan_speed"])
        new_settings[3] = int(request["heater_temp"])
        new_settings[4] = self._encode_mode(request["mode"])
        new_settings[5] = self._encode_status(request["heater"]) | (self._encode_status(request["state"]) << 1) | (
                    self._encode_status(request["sound"]) << 3)
        return new_settings

    def _send_request(self, request: bytearray):
        self._do_action(self._try_write, request=request)
