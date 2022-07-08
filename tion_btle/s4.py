import logging

if __package__ == "":
    from tion_btle.tion import TionException
    from tion_btle.light_family import TionLiteFamily
else:
    from .tion import TionException
    from .light_family import TionLiteFamily

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


class TionS4(TionLiteFamily):
    def __init__(self, mac: str):
        super().__init__(mac)

        self.modes = ['outside', 'recirculation']

        if mac == "dummy":
            _LOGGER.info("Dummy mode!")
            self._package_id: int = 0

    @property
    def REQUEST_DEVICE_INFO(self) -> list:
        return [50, 51]  # 0x32 0x33

    @property
    def SET_PARAMS(self) -> list:
        return [48, 50]  # 0x30 0x32

    @property
    def REQUEST_PARAMS(self) -> list:
        return [50, 50]  # 0x32 0x32

    def _decode_response(self, response: bytearray):
        _LOGGER.debug("Data is %s", bytes(response).hex())
        try:
            self._mode = response[2]
            self._heater_temp = response[3]
            self._fan_speed = response[4]
            self._in_temp = self.decode_temperature(response[5])
            self._out_temp = self.decode_temperature(response[6])
            self._filter_remain = int.from_bytes(response[17:20], byteorder='little', signed=False) / 86400
            self._state = response[0] & 1
            self._sound = response[0] >> 1 & 1
            self._light = response[0] >> 2 & 1
            self._heater = True if response[0] >> 4 & 1 == 0 else False
        except IndexError as e:
            raise TionException(
                "s4 _decode_response",
                f"Got bad response from Tion '{response}': {str(e)} while parsing"
            )

    def _generate_model_specific_json(self) -> dict:
        return {
            "light": self.light
        }

    def _encode_request(self, request: dict) -> bytearray:
        def encode_state() -> int:
            """Encode different device states to single status int"""
            #   power   sound   light   heater  true    resetSettings   resetErrorCounter   resetFilterResource
            #   0       1       2       3       4       5               6                   7
            return self._encode_state(request["state"]) | \
                (self._encode_state(request["sound"]) << 1) | \
                (self._encode_state(request["light"]) << 2) | \
                ((not self._encode_state(request["heater"])) << 3) | \
                (True << 4)
        try:
            sign = 181
        except KeyError:
            sign = 0

        return bytearray([0x00, 0x17, 0x00, self.MAGIC_NUMBER, self.random] +
                         self.SET_PARAMS + self.random4 + self.random4 +
                         [
                             encode_state(), 0x00, self._encode_mode(request["mode"]), int(request["heater_temp"]),
                             int(request["fan_speed"])
                         ] +
                         list(sign.to_bytes(2, byteorder='little')) + self.CRC
                         )

    @property
    def _packages(self) -> list:
        return [
            #                                       |           |                                               |
            bytearray([0x00, 0x2f, 0x00, 0x3a, 0x27, 0x31, 0x32, 0x72, 0x7b, 0x64, 0xd7, 0x31, 0xea, 0x58, 0x3a, 0x2f, 0x51, 0x00, 0x19, 0x04]),
            bytearray([0x40, 0x0e, 0x10, 0x1b, 0x26, 0x3b, 0x6e, 0x07, 0x00, 0xfa, 0x4e, 0x07, 0x00, 0x06, 0xff, 0xe5, 0x00, 0xa6, 0xe9, 0x22]),
            bytearray([0xc0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0x00, 0x98, 0x5d])
        ]

    @property
    def command_getStatus(self) -> bytearray:
        return bytearray([TionLiteFamily.SINGLE_PACKET_ID, 0x10, 0x00, self.MAGIC_NUMBER, 0xa1] +
                         self.REQUEST_PARAMS +
                         self.random4 + self.random4 +
                         self.CRC
                         )
