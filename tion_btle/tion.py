import abc
import logging
import time
import bleak
import asyncio
from typing import Callable
from bleak import BleakClient
from bleak import exc

_LOGGER = logging.getLogger(__name__)


class TionDelegation:
    def __init__(self):
        self._have_new_data: bool = False
        self._data: bytearray = bytearray()

    def handleNotification(self, handle: int, data: bytearray):
        self._data = data
        self._have_new_data = True
        _LOGGER.debug("Got data in %d response %s", handle, bytes(data).hex())

    @property
    def data(self) -> bytearray:
        self._have_new_data = False
        return self._data

    @property
    def have_new_data(self) -> bool:
        return self._have_new_data


class TionException(Exception):
    def __init__(self, expression, message):
        self.expression = expression
        self.message = message


class TionExceptionGet(TionException):
    def __init__(self, expression, message):
        super().__init__(expression, message)


class tion:
    statuses = ['off', 'on']
    uuid_notify: str = ""
    uuid_write: str = ""

    def __init__(self, mac: str):
        self._mac: str = mac
        self._btle: BleakClient = BleakClient(self.mac)
        self._delegation = TionDelegation()
        self._fan_speed = 0
        self._connections: int = 0

    @abc.abstractmethod
    async def _send_request(self, request: bytearray) -> bytearray:
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
    async def _encode_request(self, request: dict) -> bytearray:
        """ Encode dictionary of request to byte array

        Args:
          request: dictionry with request
        Returns:
          Byte array for sending to device
        """
        pass

    @abc.abstractmethod
    async def get(self) -> dict:
        """ Get device information
        Returns:
          dictionay with device paramters
        """
        pass

    @property
    def mac(self):
        return self._mac

    async def decode_temperature(self, raw: bytes) -> int:
        """ Converts temperature from bytes with addition code to int
        Args:
          raw: raw temperature value from Tion
        Returns:
          Integer value for temperature
        """
        barrier = 0b10000000
        if (raw < barrier):
            result = raw
        else:
            result = -(~(result - barrier) + barrier + 1)

        return result

    async def _process_status(self, code: int) -> str:
        try:
            status = self.statuses[code]
        except IndexError:
            status = 'unknown'
        return status

    @property
    async def connection_status(self):
        status = "connected" if await self._btle.is_connected() else "disc"
        _LOGGER.debug("connection_status is %s" % status)
        return status

    async def _connect(self):
        self._connections += 1
        if self.mac == "dummy":
            _LOGGER.info("Dummy connect")
            return

        if await self.connection_status == "disc":
            try:
                await self._btle.connect()
            except exc.BleakError as e:
                _LOGGER.warning("Got %s exception", str(e))
                await asyncio.sleep(2)
                raise e
        else:
            _LOGGER.debug("Already connected!")

    async def _disconnect(self):
        self._connections -= 1
        if await self.connection_status != "disc":
            if self.mac != "dummy":
                if self._connections == 0:
                    await self._btle.disconnect()
                    # drop _services_resolved flag, that not dropped while disconnect
                    self._btle._services_resolved = False

    async def _try_write(self, request: bytearray):
        if self.mac != "dummy":
            _LOGGER.debug("Writing %s to %s", bytes(request).hex(), self.uuid_write)
            return await self._btle.write_gatt_char(
                self.uuid_write,
                request,
                False
            )
        else:
            _LOGGER.info("Dummy write")
            return "dummy write"

    async def _enable_notifications(self):
        _LOGGER.debug("Enabling notification")
        try:
            result = await self._btle.start_notify(self.uuid_notify, self._delegation.handleNotification)
        except bleak.exc.BleakError as e:
            _LOGGER.critical("Got exception %s while enabling notifications!" % str(e))
            raise e
        return result

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
