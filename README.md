![CI tests](https://github.com/TionAPI/tion_python/workflows/CI%20tests/badge.svg?branch=master&event=push)

# About
This module will allow you to control your Tion S3 or Tion Lite breezer via bluetooth.

If you want to use MagicAir API please follow https://github.com/airens/tion
# Installation
```bash
pip3 install tion-btle
```
# Usage
Use class according to the breezer type. For example for Tion S3 you should use
```python
from tion_btle import S3 as Breezer
```
# Documentation
## Few notes about asyncio
`get`, `set`, `pair`, `connect` and `disconnect` methods are async. Use it in async loop:
## init
You must provide device's MAC-address to the constructor
```python
from tion_btle import S3 as Breezer
mac: str=str("XX:XX:XX:XX:XX:XX")
device = Breezer(mac)
```
## get
Use `get()` function to get current state of the breezer.
It will return json with all available attributes.
```python
print(await device.get())
```
Result will depend on the breezer model
#### All models
  * state -- current breezer state (on/off)
  * heater -- current heater status (on/off)
  * heating -- is breezer heating right now (on/off). For example, if the output temerature is 25 and target temperature 21, then heater may be ON, but heating will be OFF
  * sound -- current sound mode (on/off)
  * mode -- current air source (depend on model: outside/recirculation for all plus mixed for S3)
  * out_temp -- air temperature at the outlet of the device
  * in_temp -- air temperature at the inlet to the device
  * heater_temp -- target temperature for device
  * fan_speed -- current fan speed (1..6)
  * filter_remain 
  * time -- time when parameters were taken. May be different from the current time. Depends on breezer time for S3
  * request_error_code -- error code for the request (0 if all goes well)
  * code -- response code (200 if all goes well)
  * model -- breezer model (S3/Lite)
#### S3
  This parameters are available only for S3:
  * productivity -- current flow in m^3/h
  * fw_version -- breezer firmware version
  * timer -- timer state (on/off)
#### Lite
  This parameters are available only for Lite:
  * device_work_time
  * electronic_work_time
  * electronic_temp
  * co2_auto_control -- co2 auto control status (on/off). When breezer is used with MagicAir
  * filter_change_required -- is filter change required (on/off)
  * light -- light state (on/off)
## set
Use `set({parameter1: value, parameter2: value, ...})` to set breezer parameters that may be changed. It depends on the breezer model.
```python
await device.set({
    'fan_speed': 4,
    'heater_temp': 21, 
    'heater': 'on' 
})
```
### All models
  * state -- current breezer state (on/off)
  * heater -- current heater status (on/off)
  * sound -- current sound mode (on/off)
  * mode -- current air source (depend on model: outside/recirculation for all plus mixed for S3)
  * heater_temp -- target temperature for the device
  * fan_speed -- current fan speed (1..6)
### Lite
  This parameters may be set only for Tion Lite
  * light -- light state (on/off)
  * co2_auto_control -- co2 auto control status (on/off). When breezer is used with MagicAir

## pair
To pair device turn breezer to pairing mode and call
```python
await device.pair()
```
