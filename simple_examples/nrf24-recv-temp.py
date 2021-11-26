#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Example program to receive packets from the radio link
#

import RPi.GPIO as GPIO
#GPIO.setmode(GPIO.BOARD)
GPIO.setmode(GPIO.BCM)
from lib_nrf24 import NRF24
import time
import spidev



#pipes = [[0xe7, 0xe7, 0xe7, 0xe7, 0xe7], [0xc2, 0xc2, 0xc2, 0xc2, 0xc2]]

#pipes = (b"\xe1\xf0\xf0\xf0\xf0", b"\xd2\xf0\xf0\xf0\xf0")
pipes = [[0xc2, 0xc2, 0xc2, 0xc2, 0xc2], [0xf0, 0xf0, 0xf0, 0xf0, 0xf0]]


radio2 = NRF24(GPIO, spidev.SpiDev())
radio2.begin(ce_pin=25, csn_pin=0)

radio2.setRetries(15,15)

radio2.setPayloadSize(8)
radio2.setChannel(46)
radio2.setDataRate(NRF24.BR_1MBPS)
radio2.setPALevel(NRF24.PA_MIN)

#radio2.setAutoAck(True)
#radio2.enableDynamicPayloads()
#radio2.enableAckPayload()

radio2.openWritingPipe(pipes[1])
radio2.openReadingPipe(1, pipes[0])

#radio2.startListening()
#radio2.stopListening()

radio2.setCRCLength(NRF24.CRC_16)
#radio2.disableCRC()

radio2.printDetails()

time.sleep(0)

print(radio2.whatHappened())

radio2.startListening()

c=1
while True:
    akpl_buf = [c,1, 2, 3,4,5,6,7,8,9,0,1, 2, 3,4,5,6,7,8]
    pipe = [1]

    print(radio2.whatHappened())
    
    while not radio2.available(pipe):
        time.sleep(0.1)

    recv_buffer = []
    radio2.read(recv_buffer, 8)

    if recv_buffer == [128, 0, 0, 0, 0, 0, 0, 0]:
        pass
        #continue

    print ("Received:") ,
    print (recv_buffer)

    temp = int.from_bytes(recv_buffer[4:], 'little') / 100
    print("Temp is " + str(temp) + " Fahrenheit")
 
    continue
    c = c + 1
    if (c&1) == 0:
        radio2.writeAckPayload(1, akpl_buf, len(akpl_buf))
        print ("Loaded payload reply:"),
        print (akpl_buf)
    else:
        print ("(No return payload)")
