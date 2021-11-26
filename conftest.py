import sys

# Kudos to https://stackoverflow.com/questions/43162722/mocking-a-module-import-in-pytest


class TestNRF24:

    ce_pin: int
    csn_pin: int

    BR_1MBPS = 0
    BR_2MBPS = 1
    BR_250KBPS = 2

    def __init__(self, gpio, spidev):
        self.gpio = gpio
        self.spidev = spidev

        # Various configuration parameters
        self.channel = None
        self.crc_length = None
        self.power_level = None
        self.data_rate = None

        # State
        self.is_listening = False
        self.begun = False

    def begin(self, csn_pin, ce_pin=0):
        self.ce_pin = ce_pin
        self.csn_pin = csn_pin
        self.begun = True

    def set_retries(self, a, b):
        pass

    def setPayloadSize(self, size):
        pass

    def setChannel(self, channel):
        self.channel = channel

    def setDataRate(self, rate):
        self.data_rate = rate

    def setPALevel(self, level):
        self.power_level = level

    def openWritingPipe(self, pipe):
        pass

    def openReadingPipe(self, idx, pipe):
        pass

    def setCRCLength(self, crc_length):
        self.crc_length = crc_length

    def printDetails(self):
        pass

    def whatHappened(self):
        pass

    def startListening(self):
        self.is_listening = True

    def available(self, pipe):
        # TODO: Add a little delay or something in here, or maybe return False
        #   and increment an internal counter from the first call to emulate
        #   not always being ready

        is_available = True

        return is_available

    def read(self, buffer, buffer_length):
        # TODO: Return some dummy data here, by modifying buffer directly
        pass


class TestGPIO:
    # TODO: This sucks as it is. I really need a way to track state in this,
    #   but that's made a little weird because this is imported as a module,
    #   and all its functions are called as static methods.
    #   So, I can't just overload some class and store state in it. Not really
    #   sure how to track state -- some way to under the hood instantiate a class
    #   and keep track of state in it?

    BCM = 'BCM'
    BOARD = 'BOARD'
    OUT = 1

    def __init__(self):
        self.pins = [False for _ in range(30)]
        self.mode = None

    @staticmethod
    def setmode(mode):
        # self.mode = mode
        pass

    @staticmethod
    def setup(pin, mode):
        pass

    @staticmethod
    def output(pin):
        pass


class SpiDev:

    def __init__(self):
        pass


nrf_module = type(sys)('lib_nrf24')
nrf_module.NRF24 = TestNRF24
sys.modules['lib_nrf24'] = nrf_module

sys.modules['RPi'] = type(sys)('RPi')
gpio_module = type(sys)('TestGPIO')
# gpio_module.setmode = TestGPIO.setmode
# gpio_module.BCM = TestGPIO.BCM
gpio_module = TestGPIO
sys.modules['RPi.GPIO'] = gpio_module

spidev_module = type(sys)('spidev')
spidev_module.SpiDev = SpiDev
sys.modules['spidev'] = spidev_module
