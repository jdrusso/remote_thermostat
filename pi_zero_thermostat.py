#!/usr/bin/python
# -*- coding: utf-8 -*-
#
import json
import datetime
from PIL import Image, ImageDraw
import ST7735
from w1thermsensor import W1ThermSensor
from rich.console import Console

from convenience.conversions import *
from convenience.radio import *
from convenience.fonts import *


### Set up logging
logfile_console = Console(
    file=open(f'logfiles/thermostat_{time.strftime("%m_%d_%Y-%H_%M")}.log', "a"),
    log_time_format="[%x_%X]",
)

from thermostat import Thermostat

# Props to https://stackoverflow.com/a/11784984
import logging
from rich.logging import RichHandler
FORMAT = "%(message)s"
logging.basicConfig(
    format=FORMAT,
    level=logging.DEBUG,
    datefmt="[%x %X]",
    handlers=[RichHandler(), RichHandler(console=logfile_console)],
)

TEMP_LEVEL_NUM = 5
logging.addLevelName(TEMP_LEVEL_NUM, "TEMP")
def temp_log(self, message, *args, **kws):
    if self.isEnabledFor(TEMP_LEVEL_NUM):
        self._log(TEMP_LEVEL_NUM, message, args, **kws)
logging.Logger.temp = temp_log
log = logging.getLogger()


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
        schedules = json.load(schedule_file)["schedules"]
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
