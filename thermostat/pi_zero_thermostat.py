#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Example program to receive packets from the radio link
#

import RPi.GPIO as GPIO
#from thermometer import get_temp
#GPIO.setmode(GPIO.BOARD)
GPIO.setmode(GPIO.BCM)
from lib_nrf24 import NRF24
import time
import spidev

import datetime


# Scheduling: A time range, associated with a temperature range

class Schedule:

    def __init__(self, default_range=[70, 72, 1]):

        print("Schedule object being created")

        self.times = []
        self.temps = []

        self.add_range(default_range, 'default')

    def get_current_target_temp_range(self, current_time = None):
        """Obtains the target temperature for the current time. Returns the default if no match is found."""

        current_range = self.default_range

        # You shouldn't pass a time in general, but this lets me test it more easily.
        if current_time is None:
            current_time = datetime.datetime.now().time()

        for time_idx, time_range in enumerate(self.times):
            print(time_range)
            if time_range[0] < current_time <= time_range[1]:
                current_range = self.temps[time_idx]
                print(f"\t Schedule range is {time_range[0]} - {time_range[1]}")
                break
            else:
                pass

        print(f"\t At time {current_time}, the target temp range is {current_range[0]} - {current_range[1]}.")

        return current_range

    def add_range(self, temp_range, time_range):

        print("Adding schedule")

        # Allow setting a default range, in case no temp range has been set for the current time
        if time_range == 'default':
            print(f"Setting default range to {temp_range}")
            self.default_range = temp_range
            return

        else:

            # If the time interval spans midnight, split it up into two
            midnight_pm = datetime.time(23, 59)
            midnight_am = datetime.time(0, 0)
            # TODO: Best way to handle midnight crossover? I can automatically split a time range that crosses midnight
            #   but that's a little janky
            # This is a hell of an if statement
            if midnight_pm > time_range[0] > time_range[1] > midnight_am:

                # Split the time range [start, end] into [start, midnight] [midnight, end]
                new_ranges = [
                    [time_range[0], midnight_pm],
                    [datetime.time(0,0), time_range[1]]
                ]

                # And add as two independent schedule entries
                for time_range in new_ranges:
                    print(f"Adding range {time_range} with a midnight split")
                    self.times.append(time_range)
                    self.temps.append(temp_range)

            else:
                # Add the new time and temp ranges
                print(f"Adding time range {time_range}")
                self.times.append(time_range)
                self.temps.append(temp_range)

                # Make sure these lists didn't get out of whack somehow
                assert len(self.times) == len(self.temps)

            # TODO: Check that the current time range doesn't overlap anything existing...
            # TODO: Validate that time_range and temp_range are legitimate.
            #   Time_range should both be times.
            #   Temp_range should have valid temps, and a valid hysteresis

            return

class Thermostat:

    def __init__(self, temp_select_pin, temp_control_pin, fan_pin):

        # self.temp_select_pin = Pin(temp_select_pin, Pin.OUT)
        # self.temp_control_pin = Pin(temp_control_pin, Pin.OUT)
        # self.fan_pin = Pin(fan_pin, Pin.OUT)
        
        self.temp_select_pin = temp_select_pin
        self.temp_control_pin = temp_control_pin
        self.fan_pin = fan_pin
        GPIO.setup(temp_select_pin, GPIO.OUT)
        GPIO.setup(temp_control_pin, GPIO.OUT)
        GPIO.setup(fan_pin, GPIO.OUT)

        self.heating = False
        self.cooling = False
        self.fan_is_on = False

        self.schedule = Schedule()

    def fan_on(self):
        # self.fan_pin.on()
        GPIO.output(self.fan_pin, True)
        self.fan_is_on = True

    def fan_off(self):
        # self.fan_pin.off()
        GPIO.output(self.fan_pin, False)
        self.fan_is_on = False

    def heat_on(self):
        # self.temp_select_pin.on()
        # self.temp_control_pin.on()
        GPIO.output(self.temp_select_pin, False)
        GPIO.output(self.temp_control_pin, True)

        self.fan_on()
        self.heating = True
        self.cooling = False

    def ac_on(self):
        # self.temp_select_pin.off()
        # self.temp_control_pin.on()
        GPIO.output(self.temp_select_pin, True)
        GPIO.output(self.temp_control_pin, True)

        self.fan_on()
        self.heating = False
        self.cooling = True

    def all_off(self):
        # self.temp_control_pin.off()
        GPIO.output(self.temp_control_pin, False)
        GPIO.output(self.temp_select_pin, False)
        self.fan_off()
        self.heating = False
        self.cooling = False

    def set_target_temp_range(self, low_temp, high_temp, hysteresis=1):
        # This is deprecated now in favor of using a Schedule()

        assert low_temp < high_temp, \
            "Invalid temp range -- provide as [low, high]"
        assert low_temp < (high_temp - hysteresis), \
            "Temp range too small for hysteresis"

        self.low_temp = low_temp
        self.high_temp = high_temp
        self.hysteresis = hysteresis

    def update_state(self, current_temp):

        print('\n')
        self.set_target_temp_range(*self.schedule.get_current_target_temp_range())

        print("Thermostat state updating -- {%.2f} | [%.2f - %.2f]" % (current_temp, self.low_temp, self.high_temp))

        if current_temp < self.low_temp:
            print("Turning on heat")
            self.heat_on()

        elif current_temp > self.high_temp:
            print("Turning on AC")
            self.ac_on()

        elif self.heating and current_temp > self.low_temp + self.hysteresis:
            self.all_off()

        elif self.cooling and current_temp < self.high_temp - self.hysteresis:
            self.all_off()

        else:
            pass
            #print("Turning off")
            #self.all_off()


def get_remote_temp(radio):

    akpl_buf = [c,1, 2, 3,4,5,6,7,8,9,0,1, 2, 3,4,5,6,7,8]
    pipe = [1]

    print(radio.whatHappened())
    
    while not radio.available(pipe):
        time.sleep(0.1)

    recv_buffer = []
    radio.read(recv_buffer, 8)

    # print ("Received:") ,
    # print (recv_buffer)

    temp = int.from_bytes(recv_buffer[4:], 'little') / 100

    return temp


if __name__=="__main__":

    # Initialize thermostat

    temp_control_pin = 13
    temp_select_pin = 16
    fan_pin = 26

    thermostat = Thermostat(temp_control_pin=temp_control_pin,
                            temp_select_pin=temp_select_pin,
                            fan_pin=fan_pin)


    # From 8AM to 12PM, set the temp to 70-75 with 1.5 degree hysteresis
    thermostat.schedule.add_range([70, 75, 1.5], [datetime.time(8, 0), datetime.time(12, 0)])
    
    # From 12PM to 11PM, set the temp to 71-73 with 1.5 degree hysteresis
    thermostat.schedule.add_range([73, 75, 1.5], [datetime.time(12, 0), datetime.time(23, 0)])

    # From 11PM to 8AM, set the temp to 62-69 with 1.5 degree hysteresis
    thermostat.schedule.add_range([62, 69, 1.5], [datetime.time(23, 0), datetime.time(8, 0)])

    thermostat.all_off()

    # Initialize radio

    pipes = [[0xc2, 0xc2, 0xc2, 0xc2, 0xc2], [0xf0, 0xf0, 0xf0, 0xf0, 0xf0]]

    radio2 = NRF24(GPIO, spidev.SpiDev())
    radio2.begin(ce_pin=25, csn_pin=0)

    radio2.setRetries(15,15)

    radio2.setPayloadSize(8)
    radio2.setChannel(120)
    radio2.setDataRate(NRF24.BR_2MBPS)
    #radio2.setDataRate(NRF24.BR_250KBPS)
    radio2.setPALevel(NRF24.PA_MIN)

    radio2.openWritingPipe(pipes[1])
    radio2.openReadingPipe(1, pipes[0])

    radio2.setCRCLength(NRF24.CRC_16)
    #radio2.disableCRC()

    radio2.printDetails()

    time.sleep(0)

    print(radio2.whatHappened())

    radio2.startListening()

    c=1

    print("Entering main loop")

    while True:

        
        # Block on this, with a timeout
        # recv_temp = get_remote_temp(nrf)
        # print("Received temp is " + str(recv_temp))
        recv_temp = get_remote_temp(radio2)
        print("Temp is " + str(recv_temp) + " Fahrenheit")
    
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
        time.sleep(.500)

