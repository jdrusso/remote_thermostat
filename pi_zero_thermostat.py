#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Example program to receive packets from the radio link
#
import json
import RPi.GPIO as GPIO

# from thermometer import get_temp
# GPIO.setmode(GPIO.BOARD)
GPIO.setmode(GPIO.BCM)
from lib_nrf24 import NRF24
import time
import spidev

import datetime
from PIL import Image, ImageDraw, ImageFont
import ST7735

from w1thermsensor import W1ThermSensor

from rich.console import Console

logfile_console = Console(
    file=open(f'logfiles/thermostat_{time.strftime("%m_%d_%Y-%H_%M")}.log', "a"),
    log_time_format="[%x_%X]",
)

# Props to https://stackoverflow.com/a/11784984
import logging
from rich.logging import RichHandler

TEMP_LEVEL_NUM = 5

FORMAT = "%(message)s"
logging.basicConfig(
    format=FORMAT,
    level=logging.DEBUG,
    datefmt="[%x %X]",
    handlers=[RichHandler(), RichHandler(console=logfile_console)],
)

logging.addLevelName(TEMP_LEVEL_NUM, "TEMP")


def temp_log(self, message, *args, **kws):
    if self.isEnabledFor(TEMP_LEVEL_NUM):
        self._log(TEMP_LEVEL_NUM, message, args, **kws)


logging.Logger.temp = temp_log
log = logging.getLogger()

small_font = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14
)
big_font = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24
)
real_big_font = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28
)
init_font = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14
)


def to_fahrenheit(celsius):

    return celsius * (9 / 5) + 32


def to_celsius(fahrenheit):

    return (fahrenheit - 32) * (5 / 9)


def calibrate_temp(fahrenheit, low, high):

    temp_c = to_celsius(fahrenheit)
    low_c = to_celsius(low)
    high_c = to_celsius(high)

    # Using ref high and low temps from calibration
    corrected_temp = (temp_c - low_c) * 100 / (high_c - low_c)
    temp_f = to_fahrenheit(corrected_temp)

    return temp_f


# Scheduling: A time range, associated with a temperature range


class Schedule:
    def __init__(self, default_range=[70, 72, 1]):

        self.log = logging.getLogger("Schedule")
        self.log.setLevel(logging.DEBUG)
        self.log.info("Schedule object being created")

        self.times = []
        self.temps = []

        self.add_range(default_range, "default")

    def get_current_target_temp_range(self, current_time=None):
        """Obtains the target temperature for the current time. Returns the default if no match is found."""

        current_range = self.default_range

        # You shouldn't pass a time in general, but this lets me test it more easily.
        if current_time is None:
            current_time = datetime.datetime.now().time()

        for time_idx, time_range in enumerate(self.times):
            if time_range[0] < current_time <= time_range[1]:
                current_range = self.temps[time_idx]
                # self.log.info(f"\t Schedule range is {time_range[0]} - {time_range[1]}")
                break
            else:
                pass

        # self.log.info(f"At time {current_time:%H:%M:%S}, the target temp range is {current_range[0]} - {current_range[1]}.")

        return current_range

    def add_range(self, temp_range, time_range, t_src=0):

        thermometer_source = ["local", "remote"][t_src]

        self.log.info("Adding schedule")

        # Allow setting a default range, in case no temp range has been set for the current time
        if time_range == "default":
            self.log.info(f"Setting default range to {temp_range}")
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
                    [datetime.time(0, 0), time_range[1]],
                ]

                # And add as two independent schedule entries
                for time_range in new_ranges:
                    self.log.info(f"Adding range {time_range} with a midnight split")
                    self.times.append(time_range)
                    self.temps.append(temp_range)

            else:
                # Add the new time and temp ranges
                self.log.info(f"Adding time range {time_range}")
                self.times.append(time_range)
                self.temps.append(temp_range)

                # Make sure these lists didn't get out of whack somehow
                assert len(self.times) == len(self.temps)

            # TODO: Check that the current time range doesn't overlap anything existing...
            # TODO: Validate that time_range and temp_range are legitimate
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
        self.log = logging.getLogger("Thermostat")
        self.log.setLevel(logging.DEBUG)

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

    def all_off(self, reset_hysteresis=True):
        # self.temp_control_pin.off()
        GPIO.output(self.temp_control_pin, False)
        GPIO.output(self.temp_select_pin, False)
        self.fan_off()

        if reset_hysteresis:
            self.heating = False
            self.cooling = False

    def set_target_temp_range(self, low_temp, high_temp, hysteresis=1):
        # This is deprecated now in favor of using a Schedule()

        assert low_temp < high_temp, "Invalid temp range -- provide as [low, high]"
        assert low_temp < (
            high_temp - hysteresis
        ), "Temp range too small for hysteresis"

        self.low_temp = low_temp
        self.high_temp = high_temp
        self.hysteresis = hysteresis

    def update_state(self, current_temp):

        self.set_target_temp_range(*self.schedule.get_current_target_temp_range())

        self.log.info(
            "Thermostat state updating -- {%.2f} ({%.2f}) | [%.2f - %.2f]"
            % (current_temp, self.local_temp, self.low_temp, self.high_temp)
        )

        if current_temp < self.low_temp:
            self.log.critical("Heat, on")
            self.heat_on()

        elif current_temp > self.high_temp:
            self.log.critical("AC, on")
            self.ac_on()

        elif self.heating and current_temp > self.low_temp + self.hysteresis:
            self.log.critical("Off, warm")
            self.all_off()

        elif self.cooling and current_temp < self.high_temp - self.hysteresis:
            self.log.critical("Off, cool")
            self.all_off()

        # In hysteresis
        else:
            self.log.critical("Off, maintaining")
            pass


def get_remote_temp(radio):

    pipe = [1]

    # Timeout, in seconds
    wait_threshold = 10
    last_received = time.time()

    log.debug(radio.whatHappened())

    radio.flush_rx()

    while not radio.available(pipe):
        time.sleep(0.1)
        if time.time() - last_received > wait_threshold:
            log.error(
                f"Timeout reached! {wait_threshold} seconds since last temperature received"
            )
            raise Exception

    log.debug("Received")

    recv_buffer = []
    radio.read(recv_buffer, 8)

    temp = int.from_bytes(recv_buffer[4:], "little") / 100

    return temp


def open_radio(
    ce_pin,
    csn_pin,
    pa_level,
    datarate,
    write_pipe,
    read_pipe,
    crc,
    channel=120,
    _retries=15,
):
    radio2 = NRF24(GPIO, spidev.SpiDev())
    radio2.begin(ce_pin=ce_pin, csn_pin=csn_pin)
    radio2.setRetries(_retries, _retries)
    radio2.setPayloadSize(8)
    radio2.setChannel(channel)
    radio2.setDataRate(datarate)
    radio2.setPALevel(pa_level)
    radio2.openWritingPipe(write_pipe)
    radio2.openReadingPipe(1, read_pipe)
    radio2.setCRCLength(crc)
    radio2.printDetails()
    radio2.flush_rx()

    time.sleep(0.01)
    log.debug(radio2.whatHappened())

    radio2.startListening()

    return radio2


if __name__ == "__main__":

    # Initialize display
    disp = ST7735.ST7735(
        port=0,
        cs=1,
        # cs=ST7735.BG_SPI_CS_FRONT,  # BG_SPI_CSB_BACK or BG_SPI_CS_FRONT
        dc=20,  # 27,
        rst=21,  # 17,
        width=128,
        height=128,
        backlight=22,  # 18 for back BG slot, 19 for front BG slot.
        rotation=90,  # 180,
        invert=False,
        spi_speed_hz=24000000,
        offset_top=3,
    )
    disp.begin()
    width = disp.width
    height = disp.height

    # Display initialization message
    img = Image.new("RGB", (width, height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    MESSAGE = "INITIALIZING"
    size_x, size_y = draw.textsize(MESSAGE, init_font)
    draw.text((0, 0), MESSAGE, font=init_font, fill=(255, 255, 255))
    disp.display(img)

    # Initialize thermostat

    thermostat = Thermostat(temp_control_pin=22, temp_select_pin=18, fan_pin=22)

    with open("schedule.json", "r") as schedule_file:
        schedules = json.load(schedule_file)["schedule"]
        for schedule in schedules:
            thermostat.schedule.add_range(
                [*schedule["temp_range"], schedule["hysteresis"]],
                [datetime.time(*schedule["start"]), datetime.time(*schedule["end"])],
            )
    thermostat.all_off()

    # Initialize radio
    pipes = [[0xC2, 0xC2, 0xC2, 0xC2, 0xC2], [0xF0, 0xF0, 0xF0, 0xF0, 0xF0]]
    time.sleep(0.01)
    radio2 = open_radio(
        ce_pin=19,
        csn_pin=0,
        pa_level=NRF24.PA_LOW,
        datarate=NRF24.BR_2MBPS,
        write_pipe=pipes[1],
        read_pipe=pipes[0],
        crc=NRF24.CRC_16,
    )

    c = 1

    log.info("Entering main loop")

    sensor = W1ThermSensor()

    thermostat_thermometer_calibration = (38, 211.4)
    remote_thermometer_calibration = (40, 210.76)

    invalid_responses = 0
    while True:

        raw_local_temp = to_fahrenheit(sensor.get_temperature())
        calibrated_local_temp = calibrate_temp(
            raw_local_temp, *thermostat_thermometer_calibration
        )
        thermostat.local_temp = calibrated_local_temp

        log.info("Waiting on temp")
        retries = 0
        while True:
            raw_remote_temp = 0.0
            calibrated_remote_temp = 0.0

            try:
                raw_remote_temp = get_remote_temp(radio2)
                calibrated_remote_temp = calibrate_temp(
                    raw_remote_temp, *remote_thermometer_calibration
                )

                recv_temp = calibrated_remote_temp
                break

            except Exception:
                # If you fail to read the radio, reset everything and try again a couple times.

                log.error("Failed to get response - trying again...")
                radio2.stopListening()
                radio2.flush_rx()
                radio2.flush_tx()
                radio2.end()

                radio2 = open_radio(
                    ce_pin=19,
                    csn_pin=0,
                    pa_level=NRF24.PA_LOW,
                    datarate=NRF24.BR_2MBPS,
                    write_pipe=pipes[1],
                    read_pipe=pipes[0],
                    crc=NRF24.CRC_16,
                )

                radio2.startListening()
                retries += 1

                if retries > 2:
                    log.error("Couldn't get temperature. Falling back to local.")
                    recv_temp = calibrated_local_temp
                    break

        if 100 > recv_temp > 0:
            invalid_responses = 0
            cur_temp = recv_temp
            log.info(
                f"Remote| Current: {raw_remote_temp:.2f}. Calibrated: {calibrated_remote_temp:.2f}"
            )
            log.info(
                f"Local|  Current: {raw_local_temp:.2f}. Calibrated: {calibrated_local_temp:.2f}"
            )

            # Only update thermostat state if we're actually getting input
            thermostat.update_state(current_temp=cur_temp)

        else:
            invalid_responses += 1
            continue

        if invalid_responses > 100:
            log.warning(
                ">100 invalid responses received. Turning off thermostat until I get valid responses."
            )
            thermostat.all_off()

        log.temp(
            f"{time.time():.0f},{calibrated_remote_temp:.2f},{calibrated_local_temp:.2f}"
        )
        time.sleep(1.0)

        # Update display with
        #   Target
        #   Current
        #   Status
        #   Last received
        status = "NONE"
        if thermostat.heating:
            status = "HEAT"
            stat_color = (225, 6, 0)
        elif thermostat.cooling:
            status = "COOL"
            stat_color = (0, 255, 255)
        else:
            status = "OFF"
            stat_color = (255, 255, 255)

        # Make the temperature color yellow if you had to fall back to local temp
        if retries > 2:
            cur_color = (255, 215, 0)
        else:
            cur_color = (255, 255, 255)

        # Prepare the output image
        img = Image.new("RGB", (width, height), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Set messages
        TGT_MESSAGE = f"[{thermostat.low_temp} - {thermostat.high_temp}] | {calibrated_local_temp:.1f}"
        CUR_MESSAGE = f"   {cur_temp:.1f}"
        STATUS_MESSAGE = f"  {status}"
        LAST_MESSAGE = f"Last: {datetime.datetime.now().time():%H:%M:%S}"

        # Determine message sizes
        small_text_width, small_height = draw.textsize(TGT_MESSAGE, small_font)
        big_text_width, big_height = draw.textsize(TGT_MESSAGE, big_font)

        # Draw baby draw
        draw.text((0, 0), TGT_MESSAGE, font=small_font, fill=(255, 255, 255))
        draw.text(
            (0, small_height * 1.5), CUR_MESSAGE, font=real_big_font, fill=cur_color
        )
        draw.text(
            (0, small_height * 2 + big_height * 1),
            STATUS_MESSAGE,
            font=real_big_font,
            fill=stat_color,
        )
        draw.text(
            (0, small_height * 1 + big_height * 3),
            LAST_MESSAGE,
            font=small_font,
            fill=(255, 255, 255),
        )

        disp.display(img)
