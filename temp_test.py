from machine import Pin
import time

def to_fahrenheit(temp_c):

    temp_f = 32. + (temp_c * (9/5))
    return temp_f

led_pin = Pin(25, Pin.OUT)

led_pin.off()
time.sleep(0.5)

led_pin.on()

print("Initializing temp sensor")


# import time, ds18x20, onewire
# ow = onewire.OneWire(Pin(16)) 
# ds = ds18x20.DS18X20(ow)
# roms = ds.scan()
# ds.convert_temp()
# time.sleep_ms(750)
# for rom in roms:
#     temp_c = ds.read_temp(rom)
#     temp_f = to_fahrenheit(temp_c)
#     print("Temp is " + str(temp_f) + "F")

import usys
import ustruct as struct
import utime
from machine import Pin, SPI
from nrf24l01 import NRF24L01
from micropython import const

import nrf24l01test
nrf24l01test.master()