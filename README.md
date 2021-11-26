# Remote Thermostat

My apartment has a bedroom, and a big window on the other side.
My desk is over by the window, which gives me a lovely view, but...
Since the thermostat is in the middle near the bedroom, it's adjusting the temperature based on the temperature in the middle of the room.
Given that my desk is on the opposite side, and that there's substantial heat transfer through this window, this means the temperature where I'm usually sitting is poorly regulated.

This project, borne from that, is a Pi Zero-based thermostat which reads temperature from a remote thermometer.
Each has an NRF24L01+ transciever, which is used to send temperatures from the thermometer to the thermostat.


Note that because the thermometer uses a Pi Pico running Micropython, `thermometer.py` and the `nrf24l01.py` library need to live in the top-level directory.
When it's deployed to the Pi Pico, it needs to be in the root directory (named `main.py`... TODO) so it can be automatically run.

## Main components

### Thermometer

- Raspberry Pi Pico
- DS18X20 one-wire thermometer
- NRF24L01+ RF transceiver

### Thermostat

- Raspberry Pi Zero W
- Sainsmart 4-channel relay module
- NRF24L01+ RF transceiver

## Functionality

The `Thermostat` class implements basic thermostat functionality, allowing setting a target temperature range, along with a hysteresis parameter.
It handles toggling the appropriate relays -- one to select heat/cool, one to toggle the fan, and one to control temperature.

(That said... The temperature control one is redundant. I should just replace that with the fan control, I really only need 2 relay channels.)


## TODO

- [] Replace with 2 relay channels, and remove the temperature control relay.
- [] Add the actual `lib_nrf24.py` library in, instead of a symlink to the actual file on the Pi's filesystem
- [] Rename thermometer.py to `main.py`
- [] Figure out a way to put the Pi Pico files in a subdirectory
- [] Add a local thermometer on the thermostat, so I can switch over
- [] Extend the `Scheduler` to optionally specify a thermometer to read temperatures from for that time period
