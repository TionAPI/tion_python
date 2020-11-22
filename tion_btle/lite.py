import logging
from random import randrange


if __package__ == "":
    from tion_btle.tion import tion, TionException
else:
    from .tion import tion, TionException

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


class Lite(tion):
    uuid: str = "98f00001-3788-83ea-453e-f52244709ddb"
    uuid_write: str = "98f00002-3788-83ea-453e-f52244709ddb"
    uuid_notify: str = "98f00003-3788-83ea-453e-f52244709ddb"
    uuid_notify_descriptor: str = "00002902-0000-1000-8000-00805f9b34fb"
    write: None
    notify: None
    MAGIC_NUMBER: int = 0x3a  # 58
    CRC = [0xbb, 0xaa]

    SINGLE_PACKET_ID = 0x80
    FIRST_PACKET_ID = 0x00
    MIDDLE_PACKET_ID = 0x40
    END_PACKET_ID = 0xc0
    REQUEST_DEVICE_INFO = [0x09, MIDDLE_PACKET_ID]
    REQUEST_PARAMS = [0x32, 0x12]
    SET_PARAMS = [0x30, 0x12]

    def __init__(self, mac: str):
        super().__init__(mac)

        self._data: bytearray = bytearray()
        self._package_size: bytearray = bytearray()
        self._command_type: bytearray = bytearray()
        self._request_id: bytearray = bytearray()
        self._sent_request_id: bytearray = bytearray()
        self._crc: bytearray = bytearray()
        self._header: bytearray = bytearray()
        self._have_full_package = False
        self._got_new_sequence = False

        if mac == "dummy":
            _LOGGER.info("Dummy mode!")
            self._package_id: int = 0
            self._packages = [
                bytearray([0x00, 0x49, 0x00, 0x3a, 0x4e, 0x31, 0x12, 0x0d, 0xd7, 0x1f, 0x8f, 0xbf, 0xc9, 0x40, 0x37, 0xcf, 0xd8, 0x02, 0x0f, 0x04]),
                bytearray([0x40, 0x09, 0x0f, 0x1a, 0x80, 0x8e, 0x05, 0x00, 0xe9, 0x8b, 0x05, 0x00, 0x17, 0xc2, 0xe7, 0x00, 0x26, 0x1b, 0x18, 0x00]),
                bytearray([0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x00, 0x04, 0x02, 0x00, 0x00, 0x00, 0x00]),
                bytearray([0xc0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0a, 0x14, 0x19, 0x02, 0x04, 0x06, 0x06, 0x18, 0x00, 0xb5, 0xad])
            ]
            self._dummy_data = bytearray([
                0xcf, 0xd8, 0x02, 0x0f, 0x04, 0x09, 0x0f, 0x1a, 0x80, 0x8e, 0x05, 0x00, 0xe9, 0x8b, 0x05, 0x00, 0x17,
                0xc2, 0xe7, 0x00, 0x26, 0x1b, 0x18, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x03, 0x00, 0x04, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0a, 0x14, 0x19,
                0x02, 0x04, 0x06, 0x06, 0x18, 0x00
            ])

        # states
        self.have_breezer_state: bool = False
        self._light: bool = False
        self._filter_change_required: bool = False
        self._co2_auto_control: bool = False
        self._have_heater: bool = False
        self._electronic_temp: int = 0
        self._electronic_work_time: float = 0
        self._device_work_time: float = 0
        self._error_code: int = 0
        if self.mac == "dummy":
            self._get_data_from_breezer = self._get_data_from_breezer_dummy

    def _decode_header(self, header: bytearray):
        _LOGGER.debug("Header is %s", bytes(header).hex())
        self._package_size = int.from_bytes(header[1:2], byteorder='big', signed=False)
        if header[3] != self.MAGIC_NUMBER:
            _LOGGER.error("Got wrong magic number at position 3")
            raise Exception("wrong magic number")
        self._command_type = reversed(header[5:6])
        self._request_id = header[7:10]  # must match self._sent_request_id
        self._command_number = header[11:14]

    def _collect_message(self, package: bytearray) -> bool:
        self._have_full_package = False

        _LOGGER.debug("Got %s from tion", bytes(package).hex())

        if package[0] == self.FIRST_PACKET_ID or package[0] == self.SINGLE_PACKET_ID:
            self._data = package
            self._have_full_package = True if package[0] == self.SINGLE_PACKET_ID else False
            self._got_new_sequence = True if package[0] == self.FIRST_PACKET_ID else False
        elif package[0] == self.MIDDLE_PACKET_ID:
            if not self._got_new_sequence:
                _LOGGER.critical("Got middle packet but waiting for a first!")
            else:
                package = list(package)
                package.pop(0)
                self._data += bytearray(package)
        elif package[0] == self.END_PACKET_ID:
            if not self._got_new_sequence:
                _LOGGER.critical("Got end packet but waiting for a first!")
            else:
                self._have_full_package = True
                self._got_new_sequence = False
                package = list(package)
                package.pop(0)
                self._data += bytearray(package)
        else:
            _LOGGER.error("Unknown package id %s", hex(package[0]))

        if self._have_full_package:
            self._header = self._data[:15]
            self._data = self._data[15:-2]
            self._crc = self._data[-2:]

        return self._have_full_package

    def __try_get_state(self) -> bytearray:
        if self.mac == "dummy":
            p = self._packages[self._package_id]
            self._package_id += 1
            return p
        return self.notify.read()

    def _get_data_from_breezer(self) -> bytearray:
        def generate_request_id() -> bytearray:
            self._sent_request_id = bytearray([0x0d, 0xd7, 0x1f, 0x8f])
            return self._sent_request_id

        # def create_request_device_info_command() -> bytearray:
        #    generate_request_id()
        #    return bytearray(
        #        [self.SINGLE_PACKET_ID, 0x10, 0x00, self.MAGIC_NUMBER, 0x02] +
        #        self.REQUEST_DEVICE_INFO + list(self._sent_request_id) +
        #        [0x3c, 0x9f, 0xe9] + self.CRC)
        def create_request_params_command() -> bytearray:
            generate_request_id()
            packet_size = 0x10  # 17 bytes
            return bytearray(
                [self.SINGLE_PACKET_ID, packet_size, 0x00, self.MAGIC_NUMBER, 0x02] +
                self.REQUEST_PARAMS + list(self._sent_request_id) +
                [0x48, 0xd3, 0xc3, 0x1a] + self.CRC)

        self.have_breezer_state = False

        self._do_action(self._try_write, request=create_request_params_command())
        _LOGGER.debug("Collecting data")

        i = 0
        while i < 10:
            if self.mac == "dummy":
                while not self._collect_message(self.__try_get_state()):
                    pass
                else:
                    self._package_id = 0
                    self.have_breezer_state = True
                    break
            else:
                if self._btle.waitForNotifications(1.0):
                    byte_response = self._delegation.data
                    if self._collect_message(byte_response):
                        self.have_breezer_state = True
                        break
                    i = 0
                i += 1
        else:
            _LOGGER.debug("Waiting too long for data")
            self.notify.read()

        if self.have_breezer_state:
            result = self._data
        else:
            raise TionException("Lite _get_data_from_breezer", "Could not get breezer state")

        return result

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
            self._target_temp = response[3]
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
    def __random(self) -> bytes:
        # return random hex number.
        return randrange(0xFF)

    @property
    def __random4(self) -> list:
        # return 4 random hex.
        return [self.__random, self.__random, self.__random, self.__random]

    @property
    def __presets(self) -> list:
        return [0x0a, 0x14, 0x19, 0x02, 0x04, 0x06]

    @property
    def light(self) -> str:
        return self._decode_state(self._light)

    @light.setter
    def light(self, new_state: str):
        self._light = self._encode_state(new_state)

    def _send_request(self, request: bytearray):
        def chunks(lst, n):
            """Yield successive n-sized chunks from lst."""
            for j in range(0, len(lst), n):
                yield lst[j:j + n]

        if len(request) < 20:
            request[0] = self.SINGLE_PACKET_ID
            data_for_sent = [request]
        else:
            request[0] = self.FIRST_PACKET_ID
            data_for_sent = list(chunks(request, 20))

            for i in range(1, len(data_for_sent)):
                if i == len(data_for_sent)-1:
                    data_for_sent[i].insert(0, self.END_PACKET_ID)
                else:
                    data_for_sent[i].insert(0, self.MIDDLE_PACKET_ID)

        self.have_breezer_state = False

        for d in data_for_sent:
            _LOGGER.debug("Doing _try_write with request=%s", bytes(d).hex())
            self._do_action(self._try_write, request=d)

    def _encode_request(self, request: dict) -> bytearray:
        def encode_state():
            result = \
                self._encode_state(request["status"]) | \
                (self._encode_state(request["sound"]) << 1) | \
                (self._encode_state(request["light"]) << 2) | \
                (self._encode_state(request["heater"]) << 4)
            return result

        sb = 0x00  # ??
        tb = 0x02 if (self.target_temp > 0 or self.fan_speed > 0) else 0x01
        lb = [0x60, 0x00] if sb == 0 else [0x00, 0x00]

        return bytearray(
            [0x00, 0x1e, 0x00, self.MAGIC_NUMBER, self.__random] +
            self.SET_PARAMS + self.__random4 + self.__random4 +
            [encode_state(), sb, tb, int(request["heater_temp"]), int(request["fan_speed"])] +
            self.__presets + lb + [0x00] + self.CRC
        )
