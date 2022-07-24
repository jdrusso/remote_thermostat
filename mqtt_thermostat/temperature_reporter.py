#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Reports temperatures to MQTT

TODO: Could probably break this up into a local and a remote reporter...
"""

import json
import datetime
from w1thermsensor import W1ThermSensor
from rich.console import Console

from convenience.conversions import *
from convenience.radio import *
from convenience.display import Display
from convenience.display import Colors

from thermostat import broker, MQTT_AUTH, status_topic
import paho.mqtt.client as mqtt

import os.path

topic = 'home-assistant/thermostat'
local_temp_topic = f'{topic}/local_temperature'
remote_temp_topic = f'{topic}/remote_temperature'
temp_topic = f'{topic}/temperature'

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


def update_thermostat_schedule(_thermostat, _schedule_path, last_updated=None):

    file_update = os.path.getmtime(_schedule_path)
    if last_updated is not None:
        need_update = file_update > last_updated
    else:
        need_update = True

    if need_update:

        _thermostat.schedule.clear_ranges()

        with open(_schedule_path, "r") as schedule_file:
            schedules = json.load(schedule_file)["schedules"]
            for schedule in schedules:
                _thermostat.schedule.add_range(
                    [*schedule["temp_range"], schedule["hysteresis"]],
                    [datetime.time(*schedule["start"]), datetime.time(*schedule["end"])],
                )

    return file_update


logging.Logger.temp = temp_log
log = logging.getLogger()

thermostat_thermometer_calibration = (38, 211.4)
remote_thermometer_calibration = (40, 210.76)
pipes = [[0xC2, 0xC2, 0xC2, 0xC2, 0xC2], [0xF0, 0xF0, 0xF0, 0xF0, 0xF0]]


class DisplayManager:

    def __init__(self):
        self.status = None

        # TODO: Get low/high setpoints from MQTT
        self.low_temp = 0
        self.high_temp = 0

        self.local_temp = 0
        self.cur_temp = 0

    def update_display(self):

        # status = "NONE"
        if self.status == 'Heating':
            status = "HEAT"
            stat_color = Colors.RED
        elif self.status == 'Cooling':
            status = "COOL"
            stat_color = Colors.BLUE
        else:
            status = "OFF"
            stat_color = Colors.WHITE
        log.debug(f"Updating display, status is {self.status} | {status}")

        cur_color = Colors.WHITE
        ## TODO: Reimplement Make the temperature color yellow if you had to fall back to local temp
        # if retries > 2:
        #     cur_color = Colors.YELLOW
        # else:
        #     cur_color = Colors.WHITE

        display.update_thermostat_display(
            low_temp=self.low_temp,
            high_temp=self.high_temp,
            local_temp=self.local_temp,
            cur_temp=self.cur_temp,
            status=status,
            last_update=datetime.datetime.now().time(),
            cur_color=cur_color,
            stat_color=stat_color,
        )

    # The callback for when the client connects to the broker
    @staticmethod
    def on_connect(client, userdata, flags, rc):
        # Print result of connection attempt
        log.info(f"Connected and subscribed to {status_topic} with result code {str(rc)}")
        client.subscribe(status_topic)
        client.subscribe(local_temp_topic)
        client.subscribe(temp_topic)

    def on_message(self, client, userdata, msg):

        # TODO: Get status from MQTT, and set colors appropriately
        # mqtt_status = 'heating'

        log.debug(f"Got {msg.payload} on {msg.topic}")
        if msg.topic == status_topic:
            self.status = msg.payload.decode()
        elif msg.topic == local_temp_topic:
            self.local_temp = float(msg.payload)
        elif msg.topic == temp_topic:
            self.cur_temp = float(msg.payload)


if __name__ == "__main__":

    display_manager = DisplayManager()

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = display_manager.on_connect
    mqtt_client.on_message = display_manager.on_message

    mqtt_client.username_pw_set(**MQTT_AUTH)
    mqtt_client.connect(broker)
    mqtt_client.loop_start()

    display = Display(
        port=0,
        cs=1,
        dc=20,
        rst=21,
        rotation=90,
        offset_top=3,
    )

    last_modified_time = -1

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

        mqtt_client.publish(local_temp_topic, f"{calibrated_local_temp:.1f}")

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
                mqtt_client.publish(remote_temp_topic, f"{recv_temp:.1f}")
                break

            except TimeoutError:
                # If you fail to read the radio, reset everything and try again a couple times.

                mqtt_client.publish(remote_temp_topic, "")

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

            mqtt_client.publish(temp_topic, f"{cur_temp:.1f}")


        else:
            invalid_responses += 1
            continue

        if invalid_responses > 100:
            log.warning(
                ">100 invalid responses received. Turning off thermostat until I get valid responses."
            )

        log.temp(
            f"{time.time():.0f},{calibrated_remote_temp:.2f},{calibrated_local_temp:.2f}"
        )
        time.sleep(1.0)

        display_manager.update_display()