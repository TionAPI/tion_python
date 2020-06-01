import logging
from typing import Callable

if __package__ == "":
    from tion import tion
else:
    from . import tion

from bluepy import btle
import time

_LOGGER = logging.getLogger(__name__)


class TionException(Exception):
    def __init__(self, expression, message):
        self.expression = expression
        self.message = message


class s3(tion):
    uuid = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    uuid_write = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    uuid_notify = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
    write = None
    notify = None
    statuses = ['off', 'on']
    modes = ['recirculation', 'mixed']
    _btle = None

    command_prefix = 61
    command_suffix = 90

    command_PAIR = 5
    command_REQUEST_PARAMS = 1
    command_SET_PARAMS = 2

    def __init__(self, mac: str):
        self._btle = btle.Peripheral(None)
        self._mac = mac

    @property
    def mac(self):
        return self._mac

    def __try_write(self, request: bytearray):
        return self.write.write(request)

    def __try_get_state(self) -> bytearray:
        return self._btle.getServiceByUUID(self.uuid).getCharacteristics()[0].read()

    def _do_action(self, action: Callable, max_tries: int = 3, *args, **kwargs):
        tries: int = 0
        while tries < max_tries:
            _LOGGER.debug("Doing " + action.__name__ + ". Attempt " + str(tries + 1) + "/" + str(max_tries))
            try:
                if action.__name__ != '_connect':
                    self._connect()

                response = action(*args, **kwargs)
                break
            except Exception as e:
                tries += 1
                _LOGGER.warning("Got exception while " + action.__name__ + ": " + str(e))
                pass
        else:
            if action.__name__ == '_connect':
                message = "Could not connect to " + self.mac
            elif action.__name__ == '__try_write':
                message = "Could not write request + " + kwargs['request'].hex()
            elif action.__name__ == '__try_get_state':
                message = "Could not get updated state"
            else:
                message = "Could not do " + action.__name__

            raise TionException(action.__name__, message)

        return response

    def pair(self):
        def get_pair_command(self) -> bytearray:
            return self.create_command(self.command_PAIR)

        self._btle.connect(self.mac, btle.ADDR_TYPE_RANDOM)
        characteristic = self._btle.getServiceByUUID(self.uuid).getCharacteristics()[0]
        characteristic.write(bytes(get_pair_command()))
        self._btle.disconnect()

    def create_command(self, command: int) -> bytearray:
        command_special = 1 if command == self.command_PAIR else 0
        return bytearray([self.command_prefix, command, command_special, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          self.command_suffix])

    def _connect(self):
        try:
            connection_status = self._btle.getState()
        except btle.BTLEInternalError as e:
            if str(e) == "Helper not started (did you call connect()?)":
                connection_status = "disc"
            else:
                raise e
        except BrokenPipeError as e:
            connection_status = "disc"
            self._btle = btle.Peripheral(None)

        if connection_status == "disc":
            self._btle.connect(self.mac, btle.ADDR_TYPE_RANDOM)
            for tc in self._btle.getCharacteristics():
                if tc.uuid == self.uuid_notify:
                    self.notify = tc
                if tc.uuid == self.uuid_write:
                    self.write = tc

        self.notify.read()

    def get(self, keep_connection=False) -> dict:
        def get_status_command() -> bytearray:
            return self.create_command(self.command_REQUEST_PARAMS)

        def decode_response(response: bytearray) -> dict:
            def process_status(code: int) -> str:
                try:
                    status = self.statuses[code]
                except IndexError:
                    status = 'unknown'
                return status

            def process_mode(mode_code: int) -> str:
                try:
                    mode = self.modes[mode_code]
                except IndexError:
                    mode = 'outside'
                return mode

            result = {}
            try:
                result = {"code": 200, "heater": process_status(response[4] & 1),
                          "status": process_status(response[4] >> 1 & 1), "sound": process_status(response[4] >> 3 & 1),
                          "mode": process_mode(int(list("{:02x}".format(response[2]))[0])),
                          "fan_speed": int(list("{:02x}".format(response[2]))[1]), "heater_temp": response[3],
                          "in_temp": self.decode_temperature(response[8]),
                          "out_temp": self.decode_temperature(response[7]),
                          "filter_remain": response[10] * 256 + response[9],
                          "time": "{}:{}".format(response[11], response[12]), "request_error_code": response[13],
                          "fw_version": "{:02x}{:02x}".format(response[16], response[17])}
            except IndexError as e:
                result = {"code": 400,
                          "error": "Got bad response from Tion '%s': %s while parsing" % (response, str(e))}
            finally:
                return result

        try:
            self._do_action(self._connect)
            self._do_action(self.__try_write, request=get_status_command())
            byte_response = self._do_action(self.__try_get_state)
        except TionException as e:
            _LOGGER.error(str(e))
        finally:
            if not keep_connection:
                self._btle.disconnect()

        return decode_response(byte_response)

    def set(self, request: dict, keep_connection=False):
        def encode_request(request: dict) -> bytearray:
            def encode_mode(mode: str) -> int:
                return self.modes.index(mode) if mode in self.modes else 2

            def encode_status(status: str) -> int:
                return self.statuses.index(status) if status in self.statuses else 0

            try:
                if request["fan_speed"] == 0:
                    del request["fan_speed"]
                    request["status"] = "off"
            except KeyError:
                pass

            settings = {**self.get(True), **request}
            new_settings = self.create_command(self.command_SET_PARAMS)
            new_settings[2] = settings["fan_speed"]
            new_settings[3] = settings["heater_temp"]
            new_settings[4] = encode_mode(settings["mode"])
            new_settings[5] = encode_status(settings["heater"]) | (encode_status(settings["status"]) << 1) | (
                        encode_status(settings["sound"]) << 3)
            return new_settings
        try:
            self._do_action(self._connect)
            self._do_action(self.__try_write, request=encode_request(request))
        except TionException as e:
            _LOGGER.error(str(e))
        finally:
            if not keep_connection:
                self._btle.disconnect()
