"""
Code  for the remote  thermometer of my  thermostat.
"""

# TODO: What's utime? Should  I use this instead of time?
import usys, utime
import ustruct as struct

from machine import Pin, SPI
from nrf24l01 import NRF24L01
from micropython import const


import ds18x20, onewire


if usys.platform == "rp2":  # PI PICO
    cfg = {"spi": 0, "miso": 4, "mosi": 7, "sck": 6, "csn": 14, "ce": 17}


else:
    raise ValueError("Unsupported platform {}".format(usys.platform))

def to_fahrenheit(temp_c):

    temp_f = 32. + (temp_c * (9/5))
    return temp_f

# Addresses are in little-endian format. They correspond to big-endian
# 0xf0f0f0f0e1, 0xf0f0f0f0d2
# pipes = (b"\xe1\xf0\xf0\xf0\xf0", b"\xd2\xf0\xf0\xf0\xf0")
pipes = (b"\xc2\xc2\xc2\xc2\xc2", b"\xf0\xf0\xf0\xf0\xf0")


# RF_SETUP register
POWER_0 = const(0x00)  # -18 dBm
POWER_1 = const(0x02)  # -12 dBm
POWER_2 = const(0x04)  # -6 dBm
POWER_3 = const(0x06)  # 0 dBm
SPEED_1M = const(0x00)
SPEED_2M = const(0x08)
SPEED_250K = const(0x20)

def get_temp(_thermometer):

    roms = _thermometer.scan()
    _thermometer.convert_temp()
    utime.sleep_ms(100)
    for rom in roms:
        temp_c  = _thermometer.read_temp(rom)
        temp_f = to_fahrenheit(temp_c)
    
    return temp_f

def remote_thermometer_loop():
    """
    This function reads the temperature from a thermometer and sends it over RF.

    Specifically, it initializes an NRF24L01 RF tx/rx, a DS18X20 thermometer, 
    and then infinitely loops, sending the temperature with a short timeout.
    """

    # Prep the  NRF for comms
    csn = Pin(cfg["csn"], mode=Pin.OUT, value=1)
    ce = Pin(cfg["ce"], mode=Pin.OUT, value=0)
    nrf = NRF24L01(SPI(cfg["spi"]), csn, ce, payload_size=8, channel=46)
    nrf.set_power_speed(POWER_2, SPEED_1M)
    nrf.set_crc(2)
    # nrf.set_channel(46)

    # Open the comm channel
    nrf.open_tx_pipe(pipes[0])
    nrf.open_rx_pipe(1, pipes[1])

    print("Connecting to thermometer")
    ow = onewire.OneWire(Pin(16)) 
    ds = ds18x20.DS18X20(ow)

    temp_f = get_temp(ds)
    print("Temp is " + str(temp_f) + "F")

    print("remote thermometer entering tx loop...")

    temp_int = 0

    # Infinitely loop here, sending  the thermometer temp
    while True:# or (num_successes < num_needed and num_failures < num_needed):

        millis = utime.ticks_ms()
        temp_f = get_temp(ds)
        print("Temp is " + str(temp_f) + "F")

        #  TODO: What does this do? I think I can change "ii" to "i" and remove
        #       since I think I'm just sending it as an int.
        temp_int = int(temp_f*100)

        print("sending:", millis, temp_int)
        try:
            nrf.send(struct.pack("ii", millis, temp_int))
        except OSError:
            pass

        # delay then loop
        utime.sleep_ms(500)

remote_thermometer_loop()