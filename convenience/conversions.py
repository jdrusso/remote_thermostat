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
