#!/usr/bin/python
# -*- coding: utf-8 -*-
#
import json
import datetime
from w1thermsensor import W1ThermSensor
from rich.console import Console

from convenience.conversions import *
from convenience.radio import *
from convenience.display import Display
from convenience.display import Colors
from thermostat import Thermostat

import logging
from rich.logging import RichHandler

# Set up logging. This makes a file that the logger will write to
logfile_console = Console(
    file=open(f'logfiles/thermostat_{time.strftime("%m_%d_%Y-%H_%M")}.log', "a"),
    log_time_format="[%x_%X]",
)

# By specifying two loggers here, I can display some stuff to the console, and other stuff to a logfile.
# Props to https://stackoverflow.com/a/11784984
FORMAT = "%(message)s"
# noinspection PyArgumentList
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

thermostat_thermometer_calibration = (38, 211.4)
remote_thermometer_calibration = (40, 210.76)
pipes = [[0xC2, 0xC2, 0xC2, 0xC2, 0xC2], [0xF0, 0xF0, 0xF0, 0xF0, 0xF0]]

if __name__ == "__main__":

    display = Display(
        port=0,
        cs=1, dc=20, rst=21,
        rotation=90, offset_top=3,
    )

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
    radio2 = open_radio(
        ce_pin=19,
        csn_pin=0,
        pa_level=NRF24.PA_LOW,
        datarate=NRF24.BR_2MBPS,
        write_pipe=pipes[1],
        read_pipe=pipes[0],
        crc=NRF24.CRC_16,
    )

    log.info("Entering main loop")

    sensor = W1ThermSensor()

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

            except TimeoutError:
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

        status = "NONE"
        if thermostat.heating:
            status = "HEAT"
            stat_color = Colors.RED
        elif thermostat.cooling:
            status = "COOL"
            stat_color = Colors.BLUE
        else:
            status = "OFF"
            stat_color = Colors.WHITE

        # Make the temperature color yellow if you had to fall back to local temp
        if retries > 2:
            cur_color = Colors.YELLOW
        else:
            cur_color = Colors.WHITE

        display.update_thermostat_display(
            low_temp=thermostat.low_temp,
            high_temp=thermostat.high_temp,
            local_temp=calibrated_local_temp,
            cur_temp=cur_temp,
            status=status,
            last_update=datetime.datetime.now().time(),
            cur_color=cur_color,
            stat_color=stat_color
        )
