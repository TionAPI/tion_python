import abc
import logging
from random import randrange

if __package__ == "":
    from tion_btle.tion import tion, TionException
else:
    from .tion import tion, TionException

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


class LiteFamily(tion):
    uuid: str = "98f00001-3788-83ea-453e-f52244709ddb"
    uuid_write: str = "98f00002-3788-83ea-453e-f52244709ddb"
    uuid_notify: str = "98f00003-3788-83ea-453e-f52244709ddb"
    uuid_notify_descriptor: str = "00002902-0000-1000-8000-00805f9b34fb"

    write: None
    notify: None

    SINGLE_PACKET_ID = 0x80
    FIRST_PACKET_ID = 0x00
    MIDDLE_PACKET_ID = 0x40
    END_PACKET_ID = 0xc0
    MAGIC_NUMBER: int = 0x3a  # 58

    def __init__(self, mac: str):
        super().__init__(mac)
        self._data: bytearray = bytearray()
        self._crc: bytearray = bytearray()
        self._header: bytearray = bytearray()
        self._have_full_package: bool = False
        self._got_new_sequence: bool = False
        self.have_breezer_state: bool = False

        # states
        self._light: bool = False
        self._have_heater: bool = False

        # for tests
        if self.mac == "dummy":
            self._get_data_from_breezer = self._get_data_from_breezer_dummy

    @property
    def light(self) -> str:
        return self._decode_state(self._light)

    @light.setter
    def light(self, new_state: str):
        self._light = self._encode_state(new_state)

    @property
    def random(self) -> bytes:
        # return random hex number.
        return randrange(0xFF)

    @property
    def random4(self) -> list:
        # return 4 random hex.
        return [self.random, self.random, self.random, self.random]

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
        self.have_breezer_state = False
        self._do_action(self._try_write, request=self.create_request_params_command)
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
                if self._delegation.haveNewData:
                    byte_response = self._delegation.data
                    if self._collect_message(byte_response):
                        self.have_breezer_state = True
                        break
                    i = 0
                else:
                    self._btle.waitForNotifications(1.0)
                i += 1
        else:
            _LOGGER.debug("Waiting too long for data")
            self.notify.read()

        if self.have_breezer_state:
            result = self._data
        else:
            raise TionException("Lite _get_data_from_breezer", "Could not get breezer state")

        return result

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

    def _pair(self):
        """Lite family breezers is not require special pairing procedure"""
        return

    @property
    def CRC(self) -> list:
        return [0xbb, 0xaa]

    @abc.abstractmethod
    def _encode_request(self, request: dict) -> bytearray:
        """
        encode requested parameters
        :param request: dict with parameters that we should set
        :return: bytearray of encoded request. result[0] will be overwritten in  self._send_request()
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def _decode_response(self, response: bytearray):
        raise NotImplementedError()

    @abc.abstractmethod
    def _generate_model_specific_json(self) -> dict:
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def create_request_params_command(self) -> bytearray:
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def REQUEST_PARAMS(self) -> list:
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def SET_PARAMS(self) -> list:
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def REQUEST_DEVICE_INFO(self) -> list:
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def _packages(self) -> list:
        """Packages for tests"""
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def _dummy_data(self) -> bytearray:
        """Data for tests"""
        raise NotImplementedError()
