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
        """Initialise SPI object."""
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        
        self.spi.max_speed_hz = hz
        self.spi.bits_per_word = 8
        self.spi.mode = 1

        self.BUFFER = bytearray(4)


    def set_clock_hz(self, hz):  # Not sure if necessary, written in anyway
        """Set the SPI clock speed in hz."""
        self.spi.max_speed_hz = hz


    def set_bits_per_word(self, bits):
        """Set the SPI bits per word. Should be between 8 and 16."""
        self.spi.bits_per_word = bits


    def set_mode(self, mode):
        """Set the SPI mode which dictates the clock polarity and phase. Should be 0, 1, 2 or 3. For the meaning: [https://en.wikipedia.org/wiki/Serial_Peripheral_Interface#Clock_polarity_and_phase]"""
        if mode < 0 or mode > 3:
            logging.debug("Mode must be between 0 and 3 inclusive.")
            return
        self.spi.mode = mode


    def read_bytes(self, address, n):
        """Read n number of bytes from an SPI device address and return them."""
        results = self.spi.readbytes(n)
        return results


    def write_bytes(self, values, start=0, end=None):  
        # Work out how to provide the values
        """Write a list of values to the SPI device.
        Optional start and end parameters to only write/avoid writing certain bytes."""
        if end is None:
            end = len(values)
        self.spi.writebytes2(values[start:end])


    def transfer(self, data):  # call function transfer/transaction? It seems as though max has it as a read because it writes only zeroes.
        """Write the contents of data from the specified register (first byte in data) and simultaneously read a number of bytes equal to len(data) back from the MISO line."""
        result = self.spi.xfer2(data)[1:]
        #The result of the transfer is an array equal in length to what was written. The second byte onwards will be in response to what was written.


    def close():
        """Disconnect from the SPI device."""
        self.spi.close()

    # def read_register(self, address, length, write_value=0):
    #     """Write the contents of BUFFER and simultaneously read length amount of bytes from the specified address."""
    # # BUFFER = bytearray(4)
    # # for i in range(1, end):
    # #    BUFFER[i] = write_value
    # #BUFFER[0] = address and 0x7F
    # #results = bytes((self.spi.xfer2(BUFFER[:length+1]))[1:])
    # #return results


    # end = length + 1
    # for i in range(1, end):
    #     self.BUFFER[i] = write_value  
    # self.BUFFER[0] = address & 0x7F  # 7-bit length (7F = 127)

    # results = bytes((self.spi.xfer2(self.BUFFER[:length+1]))[1:])
    # return results