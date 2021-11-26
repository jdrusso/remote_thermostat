import pytest
from thermostat import pi_zero_thermostat

def test_thermostat_initialize():

    _thermostat = pi_zero_thermostat.Thermostat(temp_control_pin=13,
                                                temp_select_pin=16,
                                                fan_pin=26)
