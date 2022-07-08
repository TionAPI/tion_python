import logging

if __package__ == "":
    from tion_btle.tion import TionException
    from tion_btle.light_family import TionLiteFamily
else:
    from .tion import TionException
    from .light_family import TionLiteFamily

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


class TionLite(TionLiteFamily):

    def __init__(self, mac: str):
        super().__init__(mac)
        self._package_size: bytearray = bytearray()
        self._command_type: bytearray = bytearray()
        self._request_id: bytearray = bytearray()
        self._sent_request_id: bytearray = bytearray()

        if mac == "dummy":
            _LOGGER.info("Dummy mode!")
            self._package_id: int = 0
        # states

        self._filter_change_required: bool = False
        self._co2_auto_control: bool = False
        self._electronic_temp: int = 0
        self._electronic_work_time: float = 0
        self._device_work_time: float = 0
        self._error_code: int = 0

    @property
    def REQUEST_PARAMS(self) -> list:
        return [0x32, 0x12]

    @property
    def SET_PARAMS(self) -> list:
        return [0x30, 0x12]
    
    @property
    def REQUEST_DEVICE_INFO(self) -> list:
        return [0x09, TionLiteFamily.MIDDLE_PACKET_ID]

    def _decode_header(self, header: bytearray):
        _LOGGER.debug("Header is %s", bytes(header).hex())
        self._package_size = int.from_bytes(header[1:2], byteorder='big', signed=False)
        if header[3] != self.MAGIC_NUMBER:
            _LOGGER.error("Got wrong magic number at position 3")
            raise Exception("wrong magic number")
        self._command_type = reversed(header[5:6])
        self._request_id = header[7:10]  # must match self._sent_request_id
        self._command_number = header[11:14]

    @property
    def command_getStatus(self) -> bytearray:
        def generate_request_id() -> bytearray:
            self._sent_request_id = bytearray([0x0d, 0xd7, 0x1f, 0x8f])
            return self._sent_request_id

        generate_request_id()
        packet_size = 0x10  # 17 bytes
        return bytearray(
            [self.SINGLE_PACKET_ID, packet_size, 0x00, self.MAGIC_NUMBER, 0x02] + self.REQUEST_PARAMS + list(
                self._sent_request_id) + [0x48, 0xd3, 0xc3, 0x1a] + self.CRC)

    def _decode_response(self, response: bytearray):
        _LOGGER.debug("Data is %s", bytes(response).hex())
        try:
            self._state = response[0] & 1
            self._sound = response[0] >> 1 & 1
            self._light = response[0] >> 2 & 1
            self._filter_change_required = response[0] >> 4 & 1
            self._co2_auto_control = response[0] >> 5 & 1
            self._heater = response[0] >> 6 & 1
            self._have_heater = response[0] >> 7 & 1

            self._mode = response[2]
            self._heater_temp = response[3]
            self._fan_speed = response[4]
            self._in_temp = self.decode_temperature(response[5])
            self._out_temp = self.decode_temperature(response[6])
            self._electronic_temp = response[7]
            self._electronic_work_time = int.from_bytes(response[8:11], byteorder='little', signed=False) / 86400  # days
            self._filter_remain = int.from_bytes(response[16:20], byteorder='little', signed=False) / 86400    # days
            self._device_work_time = int.from_bytes(response[20:24], byteorder='little', signed=False) / 86400     # days
            self._error_code = response[28]

            # self._preset_temp = data[48:50]
            # self._preset_fan = data[51:53]
            # self._max_fan = data[54]
            # self._heater_percent = data[55]
        except IndexError as e:
            raise TionException(
                "Lite _decode_response", "Got bad response from Tion '%s': %s while parsing" % (response, str(e))
            )

    def _generate_model_specific_json(self) -> dict:
        return {
            "code": 200,
            "device_work_time": self._device_work_time,
            "electronic_work_time": self._electronic_work_time,
            "electronic_temp": self._electronic_temp,
            "co2_auto_control": str(self._co2_auto_control),
            "filter_change_required": str(self._filter_change_required),
            "light": self.light,
        }

    @property
    def __presets(self) -> list:
        return [0x0a, 0x14, 0x19, 0x02, 0x04, 0x06]

    def _encode_request(self, request: dict) -> bytearray:
        def encode_state():
            result = \
                self._encode_state(request["state"]) | \
                (self._encode_state(request["sound"]) << 1) | \
                (self._encode_state(request["light"]) << 2) | \
                (self._encode_state(request["heater"]) << 4)
            return result

        sb = 0x00  # ??
        tb = 0x02 if (self.heater_temp > 0 or self.fan_speed > 0) else 0x01
        lb = [0x60, 0x00] if sb == 0 else [0x00, 0x00]

        return bytearray(
            [0x00, 0x1e, 0x00, self.MAGIC_NUMBER, self.random] +
            self.SET_PARAMS + self.random4 + self.random4 +
            [encode_state(), sb, tb, int(request["heater_temp"]), int(request["fan_speed"])] +
            self.__presets + lb + [0x00] + self.CRC
        )

    @property
    def _packages(self) -> list:
        return [
                bytearray([0x00, 0x49, 0x00, 0x3a, 0x4e, 0x31, 0x12, 0x0d, 0xd7, 0x1f, 0x8f, 0xbf, 0xc9, 0x40, 0x37, 0xcf, 0xd8, 0x02, 0x0f, 0x04]),
                bytearray([0x40, 0x09, 0x0f, 0x1a, 0x80, 0x8e, 0x05, 0x00, 0xe9, 0x8b, 0x05, 0x00, 0x17, 0xc2, 0xe7, 0x00, 0x26, 0x1b, 0x18, 0x00]),
                bytearray([0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x00, 0x04, 0x02, 0x00, 0x00, 0x00, 0x00]),
                bytearray([0xc0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0a, 0x14, 0x19, 0x02, 0x04, 0x06, 0x06, 0x18, 0x00, 0xb5, 0xad])
            ]
