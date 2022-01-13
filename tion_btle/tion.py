import abc
import logging
import time
from typing import Callable, List
from time import localtime, strftime

from bluepy import btle
from bluepy.btle import DefaultDelegate

_LOGGER = logging.getLogger(__name__)


class MaxTriesExceededError(Exception):
    pass


def retry(retries: int = 2, delay: int = 0):
    def decor(f: Callable):
        def wrapper(*args, **kwargs):
            for i in range(retries+1):
                try:
                    _LOGGER.debug("Trying %d/%d: %s(args=%s,kwargs=%s)", i, retries, f.__name__, args, kwargs)
                    return f(*args, **kwargs)
                except (btle.BTLEDisconnectError, btle.BTLEInternalError) as _e:
                    _LOGGER.info(f"Got BTLEDisconnectError: {_e}")
                except Exception as _e:
                    next_message = "Will try again" if i < retries else "Will not try again"
                    _LOGGER.warning("Got exception: %s. %s", str(_e), next_message)
                    pass
                if delay > 0:
                    time.sleep(delay)
            else:
                _LOGGER.critical("Retry limit (%d) exceeded for %s(%s, %s)", retries, f.__name__, args, kwargs)
                raise MaxTriesExceededError
        return wrapper
    return decor


class TionDelegation(DefaultDelegate):
    def __init__(self):
        self._data: List[bytearray] = []
        self.__topic = None
        DefaultDelegate.__init__(self)

    def handleNotification(self, handle: int, data: bytearray):
        self._data.append(data)
        _LOGGER.debug("Got data in %d response %s", handle, bytes(data).hex())
        try:
            self.__topic.read()
        except btle.BTLEDisconnectError as e:
            _LOGGER.warning("Got %s while read in handleNotification. May continue working.", str(e))

    def setReadTopic(self, topic):
        self.__topic = topic

    @property
    def data(self) -> bytearray:
        return self._data.pop(0)

    @property
    def haveNewData(self) -> bool:
        return len(self._data) > 0


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
    def _connect_dummy(need_notifications: bool = True):
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
        self._heater_temp: int = 0
        self._fan_speed: int = 0
        self._mode: int = 0
        self._state: bool = False
        self._heater: bool = False
        self._sound: bool = False
        self._heating: bool = False
        self._filter_remain: float = 0.0
        self._error_code: int = 0
        self.__failed_connects: int = 0
        self.__connections_count: int = 0
        self.__notifications_enabled: bool = False
        self.have_breezer_state: bool = False

        if self.mac == "dummy":
            _LOGGER.warning("Dummy mode detected!")
            self._connect = self._connect_dummy
            self._disconnect = self._disconnect_dummy
            self._try_write = self._try_write_dummy
            self._enable_notifications = self._enable_notifications_dummy
            self._get_data_from_breezer = self._get_data_from_breezer_dummy

    @abc.abstractmethod
    def _send_request(self, request: bytearray):
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
            "heater_temp": self._heater_temp,
            "fan_speed": self.fan_speed,
            "filter_remain": self.filter_remain,
            "time": strftime("%H:%M", localtime()),
            "request_error_code": self._error_code,
            "model": self.model,
        }

    def __detect_heating_state(self,
                               in_temp: int = None,
                               out_temp: int = None,
                               heater_temp: int = None,
                               heater: str = None) -> None:
        """
        Tries to guess is heater working right now
        :param in_temp: air intake temperature
        :param out_temp: ait outtake temperature
        :param heater_temp: target temperature for heater
        :param heater: heater state
        :return: None
        """
        if in_temp is None:
            in_temp = self.in_temp
        if out_temp is None:
            out_temp = self.out_temp
        if heater_temp is None:
            heater_temp = self.heater_temp
        if heater is None:
            heater = self.heater

        if heater == "off":
            self.heating = "off"
        else:
            if heater_temp - in_temp > 3 and out_temp > in_temp:
                self.heating = "on"
            else:
                self.heating = "off"

    def get_state_from_breezer(self, keep_connection: bool = False) -> None:
        """
        Get current state from breezer
        :param keep_connection: should we keep connection to device or disconnect after getting data
        :return: None
        """
        try:
            self.connect()
            self._try_write(request=self.command_getStatus)
            response = self._get_data_from_breezer()
        finally:
            if not keep_connection:
                self.disconnect()
            else:
                _LOGGER.warning("You are using keep_connection parameter of get method. It will be removed in v2.0.0")
                self.__connections_count -= 1

        self._decode_response(response)
        self.__detect_heating_state()

    def get(self, keep_connection: bool = False, skip_update: bool = False) -> dict:
        """
        Report current breezer state
        :param skip_update: may we skip requesting data from breezer or not
        :param keep_connection: should we keep connection to device or disconnect after getting data
        :return:
          dictionary with device state
        """
        if skip_update and self.have_breezer_state:
            _LOGGER.debug(f"Skipping getting state from breezer because skip_update={skip_update} and "
                          f"have_breezer_state={self.have_breezer_state}")
        else:
            self.get_state_from_breezer(keep_connection)
        common = self.__generate_common_json()
        model_specific_data = self._generate_model_specific_json()

        return {**common, **model_specific_data}

    def _set_internal_state_from_request(self, request: dict) -> None:
        """
        Set internal parameters based on user request
        :param request: changed breezer parameter from set request
        :return: None
        """
        for p in ['fan_speed', 'heater_temp', 'heater', 'sound', 'mode', 'state']:
            # ToDo: lite have additional parameters to set: "light" and "co2_auto_control", so we should get this
            #  list from class
            try:
                setattr(self, p, request[p])
            except KeyError:
                pass

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
                new_settings["state"] = "off"
        except KeyError:
            pass

        try:
            self.connect()
            current_settings = self.get(skip_update=True)

            merged_settings = {**current_settings, **new_settings}

            encoded_request = self._encode_request(merged_settings)
            _LOGGER.debug("Will write %s", encoded_request)
            self._send_request(encoded_request)
            self._set_internal_state_from_request(new_settings)
        finally:
            self.disconnect()

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

    @retry(retries=1, delay=2)
    def _try_connect(self) -> None:
        """Tries to connect with retries"""

        self._btle.connect(self.mac, btle.ADDR_TYPE_RANDOM)

    def _connect(self, need_notifications: bool = True):
        _LOGGER.debug("Connecting")
        if self.connection_status == "disc":
            self._try_connect()
            for tc in self._btle.getCharacteristics():
                if tc.uuid == self.uuid_notify:
                    self.notify = tc
                if tc.uuid == self.uuid_write:
                    self.write = tc
            if need_notifications:
                self._enable_notifications()
            else:
                _LOGGER.debug("Notifications was not requested")

    def _disconnect(self):
        if self.connection_status != "disc":
            self._btle.disconnect()

    @retry(retries=3)
    def _try_write(self, request: bytearray):
        _LOGGER.debug("Writing %s to %s", bytes(request).hex(), self.write.uuid)
        return self.write.write(request)

    def __write_to_notify_handle(self, data):
        need_response: bool = True if self.model == "Lite" else False
        _LOGGER.debug("Notify handler is %s", self.notify.getHandle())
        notify_handle = self.notify.getHandle() + 1

        _LOGGER.debug("Will write %s to %s handle with withResponse=%s", data, notify_handle, need_response)
        result = self._btle.writeCharacteristic(notify_handle, data, withResponse=need_response)
        _LOGGER.debug("Result is %s", result)

    def _enable_notifications(self):
        _LOGGER.debug("Enabling notification")
        setup_data = b"\x01\x00"

        self.__write_to_notify_handle(setup_data)

        self._btle.withDelegate(self._delegation)
        _LOGGER.debug("Delegation enabled")
        try:
            data = self.notify.read()
            _LOGGER.debug("First read done. Data is %s", bytes(data).hex())
        except btle.BTLEDisconnectError as e:
            _LOGGER.critical("_enable_notifications: got '%s' while first read! Could not continue!", str(e))
            raise e

        self._delegation.setReadTopic(self.notify)
        _LOGGER.debug("enable_notification is done")
        self.__notifications_enabled = True

    def _disable_notifications(self):
        _LOGGER.debug("Disabling notifications")
        setup_data = b"\x00\x00"

        self.__write_to_notify_handle(setup_data)

        _LOGGER.debug("disable_notification is done")
        self.__notifications_enabled = False

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
    def heater_temp(self) -> int:
        return self._heater_temp

    @heater_temp.setter
    def heater_temp(self, new_temp: int):
        self._heater_temp = new_temp

    @property
    def target_temp(self) -> int:
        return self.heater_temp

    @target_temp.setter
    def target_temp(self, new_temp: int):
        self.heater_temp = new_temp

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

    @mode.setter
    def mode(self, new_state: str):
        self._mode = self._encode_mode(new_state)

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

    def pair(self):
        _LOGGER.debug("Pairing")
        self._connect(need_notifications=False)
        _LOGGER.debug("Connected. BT pairing ...")
        try:
            # use private methods to avoid disconnect if already paired
            self._btle._writeCmd('pair' + '\n')
            rsp = self._btle._waitResp('mgmt')
            _LOGGER.debug("Got response while sending pair command: %s", rsp)
            try:
                estat = rsp['estat'][0]
            except KeyError:
                # we may have no estat in response. It is OK.
                estat = 0

            if estat == 20:
                # it seem in https://github.com/TionAPI/tion_python/issues/17 that we may ignore it.
                _LOGGER.warning("bt pairing: could not pair! Permission denied. Check permissions at host. "
                                "Ignore it if all goes well")
            elif estat == 0 or estat == 19 or rsp['code'][0] == 'success':
                # 0 -- fine, no errors; 19 -- paired.
                try:
                    msg = rsp['emsg'][0]
                except KeyError:
                    msg = rsp['code'][0]
                _LOGGER.debug(msg)
            else:
                _LOGGER.critical("Unexpected response: %s", rsp)
                raise TionException('pair', rsp)
            # device-specific pairing
            _LOGGER.debug("Device-specific pairing ...")
            self._pair()
            _LOGGER.debug("Device pair is done")
        except Exception as e:
            _LOGGER.critical(f"Got exception while pair {type(e).__name__}: {str(e)}")
            raise TionException('pair', f"{type(e).__name__}: {str(e)}")
        finally:
            _LOGGER.debug("disconnected")
            self._disconnect()

    @abc.abstractmethod
    def _pair(self):
        """Perform model-specific pair steps"""

    def connect(self):
        if self.__connections_count < 0:
            self.__connections_count = 0

        if self.__connections_count == 0:
            self.have_breezer_state = False
            self._connect()

        self.__connections_count += 1

    def disconnect(self):
        self.__connections_count -= 1
        if self.__connections_count <= 0:
            self._disconnect()
            self.have_breezer_state = False

    @property
    @abc.abstractmethod
    def command_getStatus(self) -> bytearray:
        raise NotImplementedError()

    @abc.abstractmethod
    def _collect_message(self, package: bytearray) -> bool:
        """
        Collects message from several package
        Must set self._data

        :param package: single package from breezer
        :return: Have we full response from breezer or not
        """
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def _dummy_data(self) -> bytearray:
        """
        full response from breezer for test, as it was collected from packages: without deader and CRC
        """
        raise NotImplementedError()

    def _get_data_from_breezer(self) -> bytearray:
        """ Get byte array with breezer response on state request

        :returns:
          breezer response
        """
        self.have_breezer_state = False

        _LOGGER.debug("Collecting data")

        i = 0

        while i < 10:
            if self.mac == "dummy":
                return self._dummy_data
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
            raise TionException("_get_data_from_breezer", "Could not get breezer state")

        return result