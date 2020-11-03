import logging
import asyncio
from bleak import exc
from typing import Callable

if __package__ == "":
    from tion_btle.tion import tion, TionException, TionExceptionGet
else:
    from .tion import tion, TionException, TionExceptionGet

import time

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


class s3(tion):
    uuid = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    uuid_write = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    uuid_notify = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
    write = None
    notify = None

    modes = ['recirculation', 'mixed']
    _btle = None

    command_prefix = 61
    command_suffix = 90

    command_PAIR = 5
    command_REQUEST_PARAMS = 1
    command_SET_PARAMS = 2

    def __init__(self, mac: str):
        super().__init__(mac)

    def __try_get_state(self) -> bytearray:
        response = self._btle.getServiceByUUID(self.uuid).getCharacteristics()[0].read()
        _LOGGER.debug("Response is %s", bytes(response).hex())
        return response

    async def pair(self):
        async def get_pair_command() -> bytearray:
            return await self.create_command(self.command_PAIR)

        _LOGGER.setLevel("DEBUG")
        _LOGGER.debug("Going to pair with %s" % self.mac)
        try:
            _LOGGER.debug("Connecting")
            await self._connect()
            _LOGGER.debug("BT Pairing")
            await self._btle.pair()
            pair_command = await get_pair_command()
            _LOGGER.debug("Sending pair command %s to %s", bytes(pair_command).hex(), self.uuid_write)
            await self._try_write(request=pair_command)
            _LOGGER.debug("Done!")
        finally:
            _LOGGER.debug("Disconnecting")
            await self._disconnect()

    async def create_command(self, command: int) -> bytearray:
        command_special = 1 if command == self.command_PAIR else 0
        return bytearray([self.command_prefix, command, command_special, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          self.command_suffix])

    async def get(self) -> dict:
        async def get_status_command() -> bytearray:
            return await self.create_command(self.command_REQUEST_PARAMS)

        async def decode_response(response: bytearray) -> dict:
            async def process_mode(mode_code: int) -> str:
                try:
                    mode = self.modes[mode_code]
                except IndexError:
                    mode = 'outside'
                return mode

            result = {}
            try:
                self.fan_speed = int(list("{:02x}".format(response[2]))[1])
                result = {"code": 200,
                          "mode": await process_mode(int(list("{:02x}".format(response[2]))[0])),
                          "fan_speed": self.fan_speed,
                          "heater_temp": response[3],
                          "heater": await self._process_status(response[4] & 1),
                          "status": await self._process_status(response[4] >> 1 & 1),
                          "timer": await self._process_status(response[4] >> 2 & 1),
                          "sound": await self._process_status(response[4] >> 3 & 1),
                          "out_temp": await self.decode_temperature(response[7]),
                          "in_temp": await self.decode_temperature(response[8]),
                          "filter_remain": response[10] * 256 + response[9],
                          "time": "{}:{}".format(response[11], response[12]),
                          "request_error_code": response[13],
                          "productivity":  response[14],
                          "fw_version": "{:02x}{:02x}".format(response[18], response[17])}

                if result["heater"] == "off":
                    result["is_heating"] = "off"
                else:
                    if result["in_temp"] < result["heater_temp"] and result["out_temp"] - result["heater_temp"] < 3:
                        result["is_heating"] = "on"
                    else:
                        result["is_heating"] = "off"

            except IndexError as e:
                result = {"code": 400,
                          "error": "Got bad response from Tion '%s': %s while parsing" % (response, str(e))}
            finally:
                return result

        try:
            await self._connect()
            await self._enable_notifications()
            await self._try_write(request=await get_status_command())

            i = 0
            try:
                while i < 10 and not self._delegation.have_new_data:
                    await asyncio.sleep(1)
                    i += 1
                if i < 10:
                    byte_response = self._delegation.data
                else:
                    byte_response = await self._btle.read_gatt_char(
                        self.uuid_notify
                    )
                    msg = "Waiting too long for data. Use data from %s as response" % self.uuid_notify
                    _LOGGER.warning(msg)
                result = await decode_response(byte_response)

            except exc.BleakError as e:
                _LOGGER.error("Got %s while waiting for notification", str(e))
                raise TionExceptionGet('get', str(e))
        except TionException as e:
            _LOGGER.error(str(e))
            raise e
        finally:
            await self._disconnect()

        return result

    async def set(self, request: dict, keep_connection=False):
        async def encode_request(request: dict) -> bytearray:
            async def encode_mode(mode: str) -> int:
                return self.modes.index(mode) if mode in self.modes else 2

            async def encode_status(status: str) -> int:
                return self.statuses.index(status) if status in self.statuses else 0

            try:
                if request["fan_speed"] == 0:
                    del request["fan_speed"]
                    request["status"] = "off"
            except KeyError:
                pass

            try:
                current_settings = await self.get()
            except TionExceptionGet:
                raise TionException('set', 'Could not get current settings!')

            _LOGGER.debug("set: got '%s' settings" % current_settings)
            settings = {**current_settings, **request}
            new_settings = await self.create_command(self.command_SET_PARAMS)
            new_settings[2] = int(settings["fan_speed"])
            new_settings[3] = int(settings["heater_temp"])
            new_settings[4] = await encode_mode(settings["mode"])
            new_settings[5] = await encode_status(settings["heater"]) | (await encode_status(settings["status"]) << 1) | (
                        await encode_status(settings["sound"]) << 3)
            return new_settings
        try:
            await self._connect()
            try:
                encoded_request = await encode_request(request)
            except (KeyError, TionException) as e:
                _LOGGER.warning("Could not create encoded settings command: %s" % str(e))
                return

            await self._try_write(request=encoded_request)

        except TionException as e:
            _LOGGER.error(str(e))
        finally:
            await self._disconnect()
