"""SPIDevice - SPI device access class.

This class is a base access class for SPI devices.
It is partly derived from the Adafruit_GPIO/spi class available at:
https://github.com/adafruit/Adafruit_Python_GPIO/blob/master/Adafruit_GPIO/SPI.py

Basic SPI functions are available, along with settings adjustment.

Michael Shearwood, STFC Detector Systems Software Group.
"""

import spidev
import logging

# exception class?


class SPIDevice():
    """SPIDevice class.

    This class allows settings adjustment and read and write functions for the SPI device.
    """

    def __init__(self, bus, device, bits_per_word=8, hz=500000):
        """Initialise SPI object."""
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)

        self.spi.max_speed_hz = hz
        self.spi.bits_per_word = bits_per_word  # Can be 8 or 16
        self.spi.mode = 1
        self.buffer = None

    def set_buffer_length(self, n):
        """Set the length of the write buffer.

        The first time this is called, this will enable the buffer.

        :param n: the size of the buffer.
        """
        self.buffer = bytearray(n)

    def set_clock_hz(self, hz):  # Not sure if necessary, written in anyway
        """Set the SPI clock speed in hz.

        :param hz: the clock speed of the device.
        """
        self.spi.max_speed_hz = hz

    def set_bits_per_word(self, bits):
        """Set the SPI bits per word. Should be between 8 and 16.

        :param bits: the number of bits per word.
        """
        self.spi.bits_per_word = bits

    def set_mode(self, mode):
        """Set the SPI mode which dictates the clock polarity and phase.

        For the meaning of each of the modes:
        [https://en.wikipedia.org/wiki/Serial_Peripheral_Interface#Clock_polarity_and_phase].

        :param mode: the SPI mode. Must be 0, 1, 2 or 3.
        """
        if mode < 0 or mode > 3:
            logging.debug("Mode must be between 0 and 3 inclusive.")
            return
        self.spi.mode = mode

    def close(self):
        """Disconnect from the SPI device."""
        self.spi.close()

    def read_bytes(self, n):
        """Read n number of bytes from an SPI device and return them.

        :param n: the number of bytes to be read.
        """
        results = self.spi.readbytes(n)
        return results

    def write_bytes(self, data=None, start=0, end=None):
        """Write a list of values to the SPI device.

        Buffer will be used if set using set_buffer().
        This limits the number of bytes written to the length of buffer.
        Without it, the bytes will be written as-is.

        :param data: List of values to be written
        :param start: Optional (default 0) parameter to specify which bytes to write from.
        :param end: Option (default len(data)) parameter to specify which bytes to write up to.
        """
        if end is None:
            end = len(data)

        if data is None:
            if self.buffer is None:
                pass
                # raise SPIDeviceError  # Not implemented yet
            self.spi.writebytes2(self.buffer)
        else:
            self.spi.writebytes2(data[start:end])

    def transfer(self, data=None):
        """Write the contents of data from the given address and read the same number of bytes.

        :param data: the list of values to be written in a transfer.
        :returns result: an array equal in length to what was written.
        """
        if data is None:
            if self.buffer is None:
                pass
                # raise SPIDeviceError  # Not implemented yet
            result = self.spi.xfer2(self.buffer)
            return result
        else:
            result = self.spi.xfer2(data)
            return result

    def write_8(self, data=None):
        """Write one byte.

        If the list is greater than one byte, only the first byte will be written.

        :param data: A list of data to be written to the device.
        """
        self.spi.write_bytes(data, end=1)

    def write_16(self, data=None):
        """Write only two bytes to the device.

        If the list is greater than two bytes, only the first two bytes will be written.
        Handling of bytes should be done in the class for the device itself.

        :param data: A list of data to be written to the device.
        """
        self.spi.write_bytes(data, end=2)

    def write_24(self, data=None):
        """Write only three bytes to the device.

        If the list is greater than three bytes, only the first three bytes will be written.

        Handling of bytes should be done in the class for the device itself.

        :param data: A list of data to be written to the device.
        """
        self.spi.write_bytes(data, end=3)
