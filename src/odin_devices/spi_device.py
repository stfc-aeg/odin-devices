"""SPIDevice - SPI device access class.

This class is a base access class for SPI devices.
It is partly derived from the Adafruit_GPIO/spi class available at:
https://github.com/adafruit/Adafruit_Python_GPIO/blob/master/Adafruit_GPIO/SPI.py

Basic SPI functions are available, along with settings adjustment.

Michael Shearwood, STFC Detector Systems Software Group.
"""

import spidev
import logging


class SPIException(Exception):
    """SPI Exception class for wrapping underlying exception errors."""

    pass


class SPIDevice():
    """SPIDevice class.

    This class allows settings adjustment and read and write functions for the SPI device.
    """

    _enable_exceptions = False
    ERROR = -1

    @classmethod
    def enable_exceptions(cls):
        """Enable SPIDevice exceptions."""
        cls._enable_exceptions = True

    @classmethod
    def disable_exceptions(cls):
        """Disable SPIDevice exceptions."""
        cls._enable_exceptions = False

    def __init__(self, bus, device, bits_per_word=8, hz=500000, debug=False):
        """Initialise SPI object.
        
        :param bus: the number of SPI bus on host device
        :param device: device address on SPI bus
        :param bits_per_word: Optional (default 8), the number of bits per word
        :param hz: Optional (default 500000), speed of the device in hz
        :param debug: enable debug logging"""
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.bus = bus
        self.device = device

        self.spi.max_speed_hz = hz
        self.spi.bits_per_word = bits_per_word  # Can be 8 or 16
        self.spi.mode = 1
        self.buffer = None
        self.debug = debug

    def handle_error(self, access_name, register, error):
        """Handle exception condition for SPIDevice.

        If exceptions are enable, raise an exception based on the passed arguments.
        If debugging is turned on, log an error message.
        Return an error value.

        :param access_name: the name of the access where the error was caused, e.g.: transfer.
        :param register: the register from the failed write/read.
        :param error: the error message given from the failed write/read.
        :returns ERROR: a value of -1, for a check in the write/transfer functions.
        """
        err_msg = 'SPI {} error from device {:#x} register {}: {}'.format(
                  access_name, self.device, register, error
        )

        if self._enable_exceptions:
            raise SPIException(err_msg)

        if self.debug:
            logging.error(err_msg)

        return SPIDevice.ERROR

    def set_buffer_length(self, n):
        """Set the length of the write buffer.

        The first time this is called, this will enable the buffer.

        :param n: the size of the buffer.
        """
        self.buffer = bytearray(n)

    def set_clock_hz(self, hz):
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

    def buffer_or_data(self, data=None):
        """Identify whether to use self.buffer or data for writes/transfers.

        This function takes the data value provided to write_bytes or transfer.
        If data is not provided, buffer will be used for writing.
        If data is provided, then it will be used.

        :param data: Optional (default None). List of values to be written in a write or transfer.
        :returns values: a reference to data or self.buffer. If neither, then -1.
        """
        if data is None:
            if self.buffer is None:
                return self.handle_error('buffer_or_data', None,
                                         'No data provided or buffer allocated to allow for write.'
                                         )
            values = self.buffer
        else:
            values = data
        return values

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
        Without buffer, data will be written instead.

        :param data: Optional (default None). List of values to be written.
        :param start: Optional (default 0) parameter to specify which bytes to write from.
        :param end: Default None/len(data or buffer). Specify where to write up to in data/buffer.
        """
        try:
            values = self.buffer_or_data(data)
            if values == SPIDevice.ERROR:
                return
            if end is None:
                end = len(values)
            self.spi.writebytes2(values[start:end])

        except IOError as err:
            return self.handle_error('write', values[0], err)

    def transfer(self, data=None, start=0, end=None):
        """Write the contents of data from the given address and read the same number of bytes.

        Chip Select is held active between blocks.
        If held CS is necessary, this function should be used instead of write_bytes,
        and the returned results should be ignored.

        :param data: Optional (default None). List of values to be written in a transfer.
        :returns result: An array equal in length to what was written.
        :param start: Default 0. Specify where to begin writing from data/buffer.
        :param end: Default None/len(data or buffer). Specify where to write up to in data/buffer.
        """
        try:
            values = self.buffer_or_data(data)
            if values == SPIDevice.ERROR:
                return
            if end is None:
                end = len(values)
            result = self.spi.xfer2(values[start:end])
            return result

        except IOError as err:
            return self.handle_error('transfer', values[0], err)

    def write_8(self, data=None):
        """Write one byte.

        If the list is greater than one byte, only the first byte will be written.

        :param data: A list of data to be written to the device.
        """
        self.write_bytes(data, end=1)

    def write_16(self, data=None):
        """Write only two bytes to the device.

        If the list is greater than two bytes, only the first two bytes will be written.
        Handling of bytes should be done in the class for the device itself.

        :param data: A list of data to be written to the device.
        """
        self.write_bytes(data, end=2)

    def write_24(self, data=None):
        """Write only three bytes to the device.

        If the list is greater than three bytes, only the first three bytes will be written.

        Handling of bytes should be done in the class for the device itself.

        :param data: A list of data to be written to the device.
        """
        self.write_bytes(data, end=3)
