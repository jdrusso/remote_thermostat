"""
THIS IS SUPER EXPERIMENTAL AND DOESN'T WORK!
"""

"""
Code for the thermostat.

This code mainly does the following:

    1. Gets the current temperature
        - This may come from  a local or remote thermometer

    2. Gets the current target temperature RANGE
        -  This can come from  a fixed  preset, a  manual override,  or  a  schedule
        -  This needs to be a RANGE for  hysteresis, so it's not always firing
        on and  off.

    3.  Decides what to do with the thermostat accordingly
        - If temp < min target temp, then turn on the heat and fan
        - If temp > max target temp, then  turn on the AC  and fan
        - Else, turn off all.
"""
import usys
import ustruct as struct
import utime
from machine import Pin, SPI
from nrf24l01 import NRF24L01
from micropython import const

# Addresses are in little-endian format. They correspond to big-endian
# 0xf0f0f0f0e1, 0xf0f0f0f0d2
pipes = (b"\xe1\xf0\xf0\xf0\xf0", b"\xd2\xf0\xf0\xf0\xf0")

# RF_SETUP register
POWER_0 = const(0x00)  # -18 dBm
POWER_1 = const(0x02)  # -12 dBm
POWER_2 = const(0x04)  # -6 dBm
POWER_3 = const(0x06)  # 0 dBm
SPEED_1M = const(0x00)
SPEED_2M = const(0x08)
SPEED_250K = const(0x20)

if usys.platform == "rp2":  # PI PICO
    cfg = {"spi": 0, "miso": 4, "mosi": 7, "sck": 6, "csn": 14, "ce": 17}
else:
    raise Exception

# Pause between Rx polling
_RX_POLL_DELAY = const(15)

class Thermostat:

    def __init__(self, temp_select_pin, temp_control_pin, fan_pin):

        self.temp_select_pin = Pin(temp_select_pin, Pin.OUT)
        self.temp_control_pin = Pin(temp_control_pin, Pin.OUT)
        self.fan_pin = Pin(fan_pin, Pin.OUT)

    def fan_on(self):
        self.fan_pin.on()

    def fan_off(self):
        self.fan_pin.off()

    def heat_on(self):
        self.temp_select_pin.on()
        self.temp_control_pin.on()

        self.fan_on()

    def ac_on(self):
        self.temp_select_pin.off()
        self.temp_control_pin.on()

        self.fan_on()

    def all_off(self):
        self.temp_control_pin.off()
        self.fan_off()

    def set_target_temp_range(self, low_temp, high_temp):

        assert low_temp < high_temp, \
            "Invalid temp range -- provide as [low, high]"
        assert low_temp < (high_temp - 2), \
            "Temp range too small for hysteresis"

        self.low_temp = low_temp
        self.high_temp = high_temp

    def update_state(self, current_temp):


        print("Thermostat state updating -- {%.2f} | [%.2f - %.2f]" % (current_temp, self.low_temp, self.high_temp))

        if current_temp < self.low_temp:
            print("Turning on heat")
            self.heat_on()

        elif current_temp > self.high_temp:
            print("Turning on AC")
            self.ac_on()

        else:
            print("Turning off all")
            self.all_off()

def thermostat_loop():

    temp_control_pin = 10
    temp_select_pin = 11
    fan_pin = 12

    thermostat = Thermostat(temp_control_pin=temp_control_pin,
                            temp_select_pin=temp_select_pin,
                            fan_pin=fan_pin)

    thermostat.set_target_temp_range(76, 78.1)

    csn = Pin(cfg["csn"], mode=Pin.OUT, value=1)
    ce = Pin(cfg["ce"], mode=Pin.OUT, value=0)
    if cfg["spi"] == -1:
        spi = SPI(-1, sck=Pin(cfg["sck"]), mosi=Pin(cfg["mosi"]), miso=Pin(cfg["miso"]))
        nrf = NRF24L01(spi, csn, ce, payload_size=8)
    else:
        nrf = NRF24L01(SPI(cfg["spi"]), csn, ce, payload_size=8)
        nrf.set_power_speed(POWER_0, SPEED_1M)

    nrf.open_tx_pipe(pipes[1])
    nrf.open_rx_pipe(1, pipes[0])
    nrf.start_listening()

    print("NRF24L01 slave mode, waiting for packets... (ctrl-C to stop)")

    cur_temp = -100.0

    invalid_responses = 0

    while True:

        # Block on this, with a timeout
        recv_temp = get_remote_temp(nrf)
        print("Received temp is " + str(recv_temp))

        if recv_temp > -100:
            invalid_responses = 0
            cur_temp = recv_temp

            # Only update thermostat state if we're actually getting input
            thermostat.update_state(current_temp=cur_temp)

        else:
            invalid_responses += 1

        if invalid_responses > 100:
            print(">100 invalid responses received. Turning off thermostat until I get valid responses.")
            thermostat.all_off()

        print("Current temp is " + str(cur_temp) + "F")
        utime.sleep_ms(500)

def get_remote_temp(nrf):
    """
    Retrieve the temperature from a remote thermostat.
    """

    temp = -100.0

    if nrf.any():
        while nrf.any():
            buf = nrf.recv()
            millis, led_state = struct.unpack("ii", buf)
            print("received:", millis, led_state)

            temp = led_state / 100

            utime.sleep_ms(_RX_POLL_DELAY)

    return temp