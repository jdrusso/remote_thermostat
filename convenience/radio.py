import logging
import time
from convenience.lib_nrf24 import NRF24
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
import spidev

log = logging.getLogger()


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