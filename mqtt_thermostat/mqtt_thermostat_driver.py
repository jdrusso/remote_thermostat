import thermostat as tstat
import RPi.GPIO as GPIO

import logging
from rich.logging import RichHandler
from rich.console import Console
import functools

FORMAT = "%(message)s"
logging.basicConfig(
    format=FORMAT,
    level=logging.DEBUG,
    datefmt="[%x %X]",
    handlers=[RichHandler()],
)
log = logging.getLogger()

heater_topic = f'{tstat.topic}/heater/set'
heater_state_topic = f'{tstat.topic}/heater'
ac_topic = f'{tstat.topic}/ac/set'
ac_state_topic = f'{tstat.topic}/ac'

ON='ON'
OFF='OFF'


class MQTTThermostat(tstat.Thermostat):

    def __init__(self, *args, **kwargs):
        GPIO.setmode(GPIO.BCM)
        kwargs.update({'start_client': False})

        MQTTThermostat.mqtt_client.on_connect = self.on_connect
        MQTTThermostat.mqtt_client.on_message = self.on_message

        super().__init__(*args, **kwargs)

    def update_state(self, current_temp):

        # Instead of manually controlling the temperature, override this to just load up the switch controls from MQTT

        pass

    def on_message(self, client,  userdata, msg):

        print(msg.topic + " " + str(msg.payload))
        # print(msg.topic)

        if msg.topic == heater_topic:

            # self.mqtt_client.publish(ac_state_topic, OFF)

            if msg.payload == b'ON':
                log.info("Got message: heater ON")
                self.mqtt_client.publish(heater_state_topic, ON)
                self.heat_on()
            elif msg.payload == b'OFF':
                log.info("Got message: heater OFF")
                self.mqtt_client.publish(heater_state_topic, OFF)
                self.heat_off()

        elif msg.topic == ac_topic:
            # self.mqtt_client.publish(heater_state_topic, OFF)

            if msg.payload == b'ON':
                log.info("Got message: AC ON")
                self.mqtt_client.publish(ac_state_topic, ON)
                self.ac_on()
            elif msg.payload == b'OFF':
                log.info("Got message: AC OFF")
                self.mqtt_client.publish(ac_state_topic, OFF)
                self.ac_off()

        else:
            # Ignore messages on other topics
            pass

    @staticmethod
    def on_connect(client, userdata, flags, rc):  # The callback for when the client connects to the broker
        print("Connected with result code {0}".format(str(rc)))  # Print result of connection attempt
        client.subscribe(ac_topic)
        client.subscribe(heater_topic)

if __name__ == "__main__":

    thermostat = MQTTThermostat(temp_control_pin=22, temp_select_pin=18, fan_pin=22)

    log.info("Starting loop")
    log.info(f"Heater topic is {heater_topic}")
    thermostat.mqtt_client.loop_forever()
