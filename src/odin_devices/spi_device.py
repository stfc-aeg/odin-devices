"""SPIDevice - SPI device access class.

This class is a base class for SPI devices, partly derived from the Adafruit_GPIO/spi class available at:
https://github.com/adafruit/Adafruit_Python_GPIO/blob/master/Adafruit_GPIO/SPI.py


"""

import spidev
import logging

# exception class?

class SPIDevice():
    """SPIDevice class.
    This class allows read and write functions for the SPI device for varying numbers of bytes.
    """

    def __init__(self, bus, device, hz):  # port/bus, device, max_speed_hz?
        """Initialise SPI object.
        param
        """
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = hz
        self.spi.bits_per_word = 8

    def set_clock_hz(self, hz):  # Not sure if necessary, written in anyway
        """Set the SPI clock speed in hz."""
        self.spi.max_speed_hz = hz

    def read_bytes(self, n):
        """Read n number of bytes from an SPI device and return them."""
        results = self.spi.readbytes(n)
        return results

    def write_bytes(self, values):  # Work out how to provide the values
        """Write a list of values to the SPI device."""
        self.spi.writebytes2(values)
        # I can see no reason to use writebytes, when writebytes2 accepts arbitrarily large lists (and can break them up if they exceed buffer size), and accepts numpy bytearrays too.

    def close(self):
        """Close SPI device communication."""
        self.spi.close()
    # Using the max31856 device as a basis for what this class needs to do

