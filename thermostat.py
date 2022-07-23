import RPi.GPIO as GPIO
import logging
from scheduler import Schedule

import json
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish

broker = 'homeassistant.local'
topic = 'home-assistant/thermostat'
lo_topic = f'{topic}/setpoint_low'
hi_topic = f'{topic}/setpoint_high'
hysteresis_topic = f'{topic}/hysteresis'
temp_topic = f'{topic}/temperature'
status_topic = f'{topic}/status'
temp_select_topic = f'{topic}/temp_select'
temp_control_topic = f'{topic}/temp_control'
fan_topic = f'{topic}/fan'
MQTT_AUTH = json.load(open('mqtt_credentials.json', 'r'))

class Thermostat:
    def __init__(self, temp_select_pin, temp_control_pin, fan_pin):

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

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(**MQTT_AUTH)
        self.mqtt_client.connect(broker)
        self.mqtt_client.loop_start()

    def fan_on(self):
        GPIO.output(self.fan_pin, True)
        self.fan_is_on = True
        self.mqtt_client.publish(fan_topic, True)

    def fan_off(self):
        GPIO.output(self.fan_pin, False)
        self.fan_is_on = False
        self.mqtt_client.publish(fan_topic, False)

    def heat_on(self):
        GPIO.output(self.temp_select_pin, False)
        GPIO.output(self.temp_control_pin, True)
        
        self.log.info(f"Sending MQTT message to {status_topic}")
        self.mqtt_client.publish(status_topic, 'Heating')
        self.mqtt_client.publish(temp_select_topic, False)
        self.mqtt_client.publish(temp_select_topic, True)
        
        self.fan_on()
        self.heating = True
        self.cooling = False

    def ac_on(self):
        GPIO.output(self.temp_select_pin, True)
        GPIO.output(self.temp_control_pin, True)

        self.log.info(f"Sending MQTT message to {status_topic}")
        self.mqtt_client.publish(status_topic, 'Cooling')
        self.mqtt_client.publish(temp_select_topic, True)
        self.mqtt_client.publish(temp_control_topic, True)

        self.fan_on()
        self.heating = False
        self.cooling = True

    def all_off(self, reset_hysteresis=True):
        GPIO.output(self.temp_control_pin, False)
        GPIO.output(self.temp_select_pin, False)
        self.fan_off()

        self.mqtt_client.publish(status_topic, 'Off')
        self.mqtt_client.publish(temp_select_topic, False)
        self.mqtt_client.publish(temp_control_topic, False)

        if reset_hysteresis:
            self.heating = False
            self.cooling = False

    def _set_target_temp_range(self, low_temp, high_temp, hysteresis=1):
        # This is called via update_state, and shouldn't be called directly.

        assert low_temp < high_temp, "Invalid temp range -- provide as [low, high]"
        assert low_temp < (
            high_temp - hysteresis
        ), "Temp range too small for hysteresis"

        self.mqtt_client.publish(lo_topic, low_temp)
        self.mqtt_client.publish(hi_topic, high_temp)
        self.mqtt_client.publish(hysteresis_topic, hysteresis)

        self.low_temp = low_temp
        self.high_temp = high_temp
        self.hysteresis = hysteresis

    def update_state(self, current_temp):

        self._set_target_temp_range(*self.schedule.get_current_target_temp_range())

        self.mqtt_client.publish(temp_topic, f"{current_temp:.1f}")

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
            self.mqtt_client.publish(status_topic, 'Off')
            self.log.critical("Off, maintaining")
            pass
