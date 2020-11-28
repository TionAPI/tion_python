import abc
import logging
import time
from typing import Callable
from time import localtime, strftime

from bluepy import btle
from bluepy.btle import DefaultDelegate

_LOGGER = logging.getLogger(__name__)


class TionDelegation(DefaultDelegate):
    def __init__(self):
        self._data = None
        DefaultDelegate.__init__(self)

    def handleNotification(self, handle: int, data: bytes):
        self._data = data
        _LOGGER.debug("Got data in %d response %s", handle, bytes(data).hex())

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if isNewDev:
            _LOGGER.debug("Discovered device %s", dev.addr)
        elif isNewData:
            _LOGGER.debug("Received new data from %s", dev.addr)

    @property
    def data(self) -> bytes:
        return self._data


class TionException(Exception):
    def __init__(self, expression, message):
        self.expression = expression
        self.message = message


class TionDummy:
    """
    Class for dummy methods, that should be used for tests
    """

    _dummy_data: bytearray

    @staticmethod
    def _connect_dummy():
        """dummy connection"""

        _LOGGER.info("Dummy connect")
        return

    @staticmethod
    def _disconnect_dummy():
        return

    def _get_data_from_breezer_dummy(self) -> bytearray:
        return self._dummy_data

    @staticmethod
    def _try_write_dummy(request: bytearray):
        _LOGGER.debug("Dummy write %s", bytes(request).hex())
        return

    @staticmethod
    def _enable_notifications_dummy():
        return


class tion(TionDummy):
    statuses = ['off', 'on']
    modes = ['recirculation', 'mixed']  # 'recirculation', 'mixed' and 'outside', as Index exception
    uuid_notify: str = ""
    uuid_write: str = ""

    def __init__(self, mac: str):
        self._mac = mac
        self._btle: btle.Peripheral = btle.Peripheral(None)
        self._delegation = TionDelegation()
        self._fan_speed = 0
        self._model: str = self.__class__.__name__
        self._data: bytearray = bytearray()
        """Data from breezer response at request state command"""
        # states
        self._in_temp: int = 0
        self._out_temp: int = 0
        self._target_temp: int = 0
        self._fan_speed: int = 0
        self._mode: int = 0
        self._state: bool = False
        self._heater: bool = False
        self._sound: bool = False
        self._heating: bool = False
        self._filter_remain: float = 0.0
        self._error_code: int = 0

        if self.mac == "dummy":
            _LOGGER.warning("Dummy mode detected!")
            self._dummy_data: bytearray = bytearray()
            self._connect = self._connect_dummy
            self._disconnect = self._disconnect_dummy
            self._try_write = self._try_write_dummy
            self._enable_notifications = self._enable_notifications_dummy
            self._get_data_from_breezer = self._get_data_from_breezer_dummy

    @abc.abstractmethod
    def _send_request(self, request: bytearray) -> bytearray:
        """ Send request to device

        Args:
          request : array of bytes to send to device
        Returns:
          array of bytes with device response
        """
        pass

    @abc.abstractmethod
    def _decode_response(self, response: bytearray) -> dict:
        """ Decode response from device

        Args:
          response: array of bytes with data from device, taken from _send_request
        Returns:
          dictionary with device response
        """
        pass

    @abc.abstractmethod
    def _encode_request(self, request: dict) -> bytearray:
        """ Encode dictionary of request to byte array

        Args:
          request: dictionary with request
        Returns:
          Byte array for sending to device
        """
        pass

    @abc.abstractmethod
    def _get_data_from_breezer(self) -> bytearray:
        """ Get byte array with brezer response on state request
        Returns:
          breezer response
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def _generate_model_specific_json(self) -> dict:
        """
        Generates dict with model-specific parameters based on class variables
        :return: dict of model specific properties
        """
        raise NotImplementedError()

    def __generate_common_json(self) -> dict:
        """
        Generates dict with common parameters based on class properties
        :return: dict of common properties
        """
        return {
            "state": self.state,
            "heater": self.heater,
            "heating": self.heating,
            "sound": self.sound,
            "mode": self.mode,
            "out_temp": self.out_temp,
            "in_temp": self.in_temp,
            "heater_temp": self.target_temp,
            "fan_speed": self.fan_speed,
            "filter_remain": self.filter_remain,
            "time": strftime("%H:%M", localtime()),
            "request_error_code": self._error_code,
            "model": self.model,
        }

    def __detect_heating_state(self,
                               in_temp: int = None,
                               out_temp: int = None,
                               target_temp: int = None,
                               heater: str = None) -> None:
        """
        Tries to guess is heater working right now
        :param in_temp: air intake temperature
        :param out_temp: ait outtake temperature
        :param target_temp: target temperature for heater
        :param heater: heater state
        :return: None
        """
        if in_temp is None:
            in_temp = self.in_temp
        if out_temp is None:
            out_temp = self.out_temp
        if target_temp is None:
            target_temp = self.target_temp
        if heater is None:
            heater = self.heater

        if heater == "off":
            self.heating = "off"
        else:
            if in_temp < target_temp and out_temp - target_temp < 3:
                self.heating = "on"
            else:
                self.heating = "off"

    def get(self, keep_connection: bool = False) -> dict:
        """
        Get current device state
        :param keep_connection: should we keep connection to device or disconnect after getting data
        :return:
          dictionary with device state
        """
        try:
            self._connect()
            response = self._get_data_from_breezer()
        finally:
            if not keep_connection:
                self._disconnect()

        self._decode_response(response)
        self.__detect_heating_state()
        common = self.__generate_common_json()
        model_specific_data = self._generate_model_specific_json()

        return {**common, **model_specific_data}

    def set(self, new_settings=None) -> None:
        """
        Set new breezer state
        :param new_settings: json with new state
        :return: None
        """
        if new_settings is None:
            new_settings = {}

        try:
            if new_settings["fan_speed"] == 0:
                del new_settings["fan_speed"]
                new_settings["status"] = "off"
        except KeyError:
            pass

        try:
            self._connect()
            current_settings = self.get(True)

            merged_settings = {**current_settings, **new_settings}

            encoded_request = self._encode_request(merged_settings)
            _LOGGER.debug("Will write %s", encoded_request)
            self._send_request(encoded_request)
        finally:
            self._disconnect()

    @property
    def mac(self):
        return self._mac

    @staticmethod
    def decode_temperature(raw: int) -> int:
        """ Converts temperature from bytes with addition code to int
        Args:
          raw: raw temperature value from Tion
        Returns:
          Integer value for temperature
        """
        barrier = 0b10000000
        return raw if raw < barrier else -(~(raw - barrier) + barrier + 1)

    def _process_status(self, code: int) -> str:
        try:
            status = self.statuses[code]
        except IndexError:
            status = 'unknown'
        return status

    @property
    def connection_status(self):
        connection_status = "disc"
        try:
            connection_status = self._btle.getState()
        except btle.BTLEInternalError as e:
            if str(e) == "Helper not started (did you call connect()?)":
                pass
            else:
                raise e
        except btle.BTLEDisconnectError as e:
            pass
        except BrokenPipeError as e:
            self._btle = btle.Peripheral(None)

        return connection_status

    def _connect(self):
        if self.connection_status == "disc":
            try:
                self._btle.connect(self.mac, btle.ADDR_TYPE_RANDOM)
                for tc in self._btle.getCharacteristics():
                    if tc.uuid == self.uuid_notify:
                        self.notify = tc
                    if tc.uuid == self.uuid_write:
                        self.write = tc

                self._enable_notifications()
            except btle.BTLEDisconnectError as e:
                _LOGGER.warning("Got %s exception", str(e))
                time.sleep(2)
                raise e

    def _disconnect(self):
        if self.connection_status != "disc":
            self._btle.disconnect()

    def _try_write(self, request: bytearray):
        _LOGGER.debug("Writing %s to %s", bytes(request).hex(), self.write.uuid)
        return self.write.write(request)

    def _do_action(self, action: Callable, max_tries: int = 3, *args, **kwargs):
        tries: int = 0
        while tries < max_tries:
            _LOGGER.debug("Doing " + action.__name__ + ". Attempt " + str(tries + 1) + "/" + str(max_tries))
            try:
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

    def _enable_notifications(self):
        _LOGGER.debug("Enabling notification")
        setup_data = b"\x01\x00"

        _LOGGER.debug("Notify handler is %s", self.notify.getHandle())
        notify_handle = self.notify.getHandle() + 1

        _LOGGER.debug("Will write %s to %s handle", setup_data, notify_handle)
        result = self._btle.writeCharacteristic(notify_handle, setup_data, withResponse=True)
        _LOGGER.debug("Result is %s", result)
        self._btle.withDelegate(self._delegation)
        self.notify.read()

    @property
    def fan_speed(self):
        return self._fan_speed

    @fan_speed.setter
    def fan_speed(self, new_speed: int):
        if 0 <= new_speed <= 6:
            self._fan_speed = new_speed

        else:
            _LOGGER.warning("Incorrect new fan speed. Will use 1 instead")
            self._fan_speed = 1

        # self.set({"fan_speed": new_speed})

    def _process_mode(self, mode_code: int) -> str:
        try:
            mode = self.modes[mode_code]
        except IndexError:
            mode = 'outside'
        return mode

    @staticmethod
    def _decode_state(state: bool) -> str:
        return "on" if state else "off"

    @staticmethod
    def _encode_state(state: str) -> bool:
        return state == "on"

    @property
    def state(self) -> str:
        return self._decode_state(self._state)

    @state.setter
    def state(self, new_state: str):
        self._state = self._encode_state(new_state)

    @property
    def heater(self) -> str:
        return self._decode_state(self._heater)

    @heater.setter
    def heater(self, new_state: str):
        self._heater = self._encode_state(new_state)

    @property
    def target_temp(self) -> int:
        return self._target_temp

    @target_temp.setter
    def target_temp(self, new_temp: int):
        self._target_temp = new_temp

    @property
    def in_temp(self):
        """Income air temperature"""
        return self._in_temp

    @property
    def out_temp(self):
        """Outcome air temperature"""
        return self._out_temp

    @property
    def sound(self) -> str:
        return self._decode_state(self._sound)

    @sound.setter
    def sound(self, new_state: str):
        self._sound = self._encode_state(new_state)

    @property
    def filter_remain(self) -> float:
        return self._filter_remain

    @property
    def heating(self) -> str:
        return self._decode_state(self._heating)

    @heating.setter
    def heating(self, new_state: str):
        self._heating = self._encode_state(new_state)

    @property
    def mode(self):
        return self._process_mode(self._mode)

    @property
    def model(self) -> str:
        return self._model

    def _encode_status(self, status: str) -> int:
        """
        Encode string status () to int
        :param status: one of:  "on", "off"
        :return: integer equivalent of state
        """
        return self.statuses.index(status) if status in self.statuses else 0

    def _encode_mode(self, mode: str) -> int:
        """
        Encode string mode to integer
        :param mode: one of self.modes + any other as outside
        :return: integer equivalent of mode
        """
        return self.modes.index(mode) if mode in self.modes else 2
