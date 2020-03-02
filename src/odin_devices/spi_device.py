"""SPIDevice - SPI device access class.

This class is a base access class for SPI devices, partly derived from the Adafruit_GPIO/spi class available at:
https://github.com/adafruit/Adafruit_Python_GPIO/blob/master/Adafruit_GPIO/SPI.py

Basic SPI functions are available, along with settings adjustment.

Michael Shearwood, STFC Detector Systems Software Group.
"""

import spidev
import logging

# exception class?

class SPIDevice():
    """SPIDevice class.
    This class allows settinds adjustment and read and write functions for the SPI device for varying numbers of bytes.
    """

    def __init__(self, bus, device, bits_per_word=8, hz=500000):
        """Initialise SPI object."""
        
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)

        self.spi.max_speed_hz = hz
        self.spi.bits_per_word = 8  # Can be 8 or 16
        self.spi.mode = 1


    def set_clock_hz(self, hz):  # Not sure if necessary, written in anyway
        """Set the SPI clock speed in hz."""
        self.spi.max_speed_hz = hz


    def set_bits_per_word(self, bits):
        """Set the SPI bits per word. Should be between 8 and 16."""
        self.spi.bits_per_word = bits


    def set_mode(self, mode):
        """Set the SPI mode which dictates the clock polarity and phase. Must be 0, 1, 2 or 3. For the meaning: [https://en.wikipedia.org/wiki/Serial_Peripheral_Interface#Clock_polarity_and_phase]"""
        if mode < 0 or mode > 3:
            logging.debug("Mode must be between 0 and 3 inclusive.")
            return
        self.spi.mode = mode


    def read_bytes(self, n):
        """Read n number of bytes from an SPI device and return them."""
        results = self.spi.readbytes(n)
        return results


    def write_bytes(self, values, start=0, end=None):  
        """Write a list of values to the SPI device.
        Optional start and end parameters to only write/avoid writing certain bytes."""
        if end is None:
            end = len(values)
        self.spi.writebytes2(values[start:end])


    def transfer(self, data):  
        """Write the contents of data from the specified register (first byte in data) and simultaneously read a number of bytes equal to len(data) back from the MISO line."""
        result = self.spi.xfer2(data)
        return result
        #The result of the transfer is an array equal in length to what was written. The second byte onwards will be in response to what was written.


    def close():
        """Disconnect from the SPI device."""
        self.spi.close()


#######################################################################
#  in construction  #
#######################################################################

    def create_buffer(self, length, address):
        """A function which will create a BUFFER for the read/write functions to use.
        The first byte is replaced with the address """
        BUFFER = bytearray(length)
        BUFFER[0] = address
        return BUFFER


    def write_8(self, data):
        """Write one byte"""
        BUFFER = create_buffer(1, data)  # The 'address' in create_bytes will be the data
        self.spi.writebytes(BUFFER)


    def write_16(self, address, data):
        """Write two bytes: one address, one data. MSB. Handling of bytes should be done in the class for the device itself.
        """
        BUFFER = create_buffer(2, address)
        BUFFER[1] = data

        self.spi.writebytes2(BUFFER)


    def write_24(self, address, data_1, data_2):
        """Write three bytes: one address, two data. MSB. Handling of bytes should be done in the class for the device itself.
        """
        BUFFER = create_buffer(3, address)
        BUFFER[1] = data_1
        BUFFER[2] = data_2

        self.spi.writebytes(BUFFER)


    # Reading any number of bytes without needing to write should be done with read_bytes, which will read n number of bytes. e.g.: read_bytes(3)

    # Reading while needing to provide an address (or writing to prompt a read from a previously given address) should be done with the transfer function...
    # ...because readbytes() will not write.
    # Buffered-transfer will provide a transfer of specified length, and otherwise function as the various writes will. One function or more?

    def buffered_transfer(self, length, address=0, data_list=0):
        """Write out the address and data bytes (defaults to zero if nothing needs to be written) using a buffer of given length.
        """
        BUFFER = create_buffer(length, address)
        for i in range(1, len(data_list) + 1):
            BUFFER[i] = data_list[i]

        self.spi.xfer2(BUFFER)