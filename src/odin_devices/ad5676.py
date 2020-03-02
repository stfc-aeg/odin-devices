"""AD5676R device class.

This class implements support for the AD5676R DAC.

For device information, see datasheet pdf available at:
https://www.analog.com/media/en/technical-documentation/data-sheets/ad5672r_5676r.pdf

Core knowledge is that the device writes and reads 3 bytes at a time.
The first byte is a command and an address (4 bits each), the remaining two bytes are data.
"""

import logging
from odin_devices.spi_device import SPIDevice


class AD5676R(SPIDevice):

    def __init__(self):
        """Initialise the AD5676R device. Many of the settings are sorted automatically in spi_device.
        SPIDevice.__init__ is provided bus, device, bits_per_word (optional) and hz (optional).
        Settings can be adjusted with the functions in spi_device.
        :No parameters are required to launch this device:
        """
        SPIDevice.__init__(self, 0, 0)

        # This device is compatible with SPI modes 1 and 2
        # Data is sampled on the falling edge of the clock pulse
        self.set_mode(1)
        # All reads/writes are 3-bytes
        self.BUFFER = bytearray(3)
        for i in range(3):
            self.BUFFER[i] = 0
        self.Vref = 2.5  # 2.5V = 0xFFFF


    def input_register_write(self, register, voltage):
        """Write to the dedicated input register for each DAC individually.
        If LDAC is low, the input register is transparent. Otherwise, controlled by the LDAC mask register.
        :param register: selected register to write to (0000 --> 0111)
        :params byte1
                byte2: bytes to be written, MSB
        """
        # Command for write_to_input is 0001 = 0x10 in the command byte
        self.BUFFER[0] = 0x10 | register
        # Presumably writing with voltages? Not anything else to write...
        # ...unless specified in the function itself.
        dac_val = int(float(voltage)/2.5 * 0xFFFF)
        dac_msb = (dac_val  >> 8) & 0XFF
        dac_lsb = dac_val & 0XFF

        self.BUFFER[1] = dac_msb
        self.BUFFER[2] = dac_lsb
        self.write_bytes(self.BUFFER)

        #  # Keeping these here in case it is decided another method of data input is preferable
        # self.BUFFER[1] = byte_1
        # self.BUFFER[2] = byte_2

    def input_into_dac(self, DAC_byte):
        """Load DAC registers and outputs with the contents of the selected input register, and update the DAC outputs directly.
        Data bits D0 to D7 specify which DAC registers have data from the input register transferred to the DAC register. Data is transferred when the bit is 1.

        :param register: Specified register
        :param DAC_byte: a user-provided byte with the DACs they want updated specified
        """
        # Command for DAC input register load is 0010 = 0x20
        self.BUFFER[0] = 0x20
        # Is there another way to deliver the DAC-specifying byte?
        self.BUFFER[2] = DAC_byte 

        self.transfer(self.BUFFER)


    def write_to_dac(self, channel, voltage):
        """Write to and update DAC Channel n. Updating the DAC channel changes its output voltage, with a variable maximum depending on the GAIN pin.
        If the GAIN pin is tied to GND, all DACs have an output span of 0V to Vref (2.5V).
        If the GAIN pin is tied to Vlogic, all DACs output a span of 0V to 2*Vref(5V).

        :param channel: the provided DAC channel,
                        must be between 0000 and 0111 inclusive.
        :param voltage: the provided voltage
        
        """
        # Command for DAC register update is 0010 = 0x30.
        self.BUFFER[0] = 0x30 | channel

        # Voltage/Vref * max value 
        dac_val = int(float(voltage)/2.5 * 0xFFFF)
        dac_msb = (dac_val  >> 8) & 0xFF
        dac_lsb = dac_val & 0xFF

        # some modification may be needed to allow for 2*vref gain bit
        self.BUFFER[1] = dac_msb
        self.BUFFER[2] = dac_lsb

        self.write_bytes(self.BUFFER)

        # #### EXAMPLE ####
        # self.write_24(0x30 | channel, dac_msb, dac_lsb)


    def power_down(self, DAC_binary):
        """Power down the device or change its mode of operation. These modes are programmable by setting the 16 data bits in the input shift register. Two bits refer to each DAC, where DB0, DB1 refer to DAC channel 0.
        00 is normal operation. The two power-down options are as follows:
        01 connects the output internally to GND through a 1kΩ resistor,
        11 leaves it open-circuited (tristate).
        :param DAC_binary: a binary string that 
        """
        # The command for DAC power up/down is 0100 = 0x40
        self.BUFFER[0] = 0x40

        power_msb = (DAC_binary >> 8) & 0xFF
        power_lsb = DAC_binary & 0xFF
        # How to take this data?
        self.BUFFER[1] = power_msb
        self.BUFFER[2] = power_lsb 

        self.write_bytes(self.BUFFER)



    def LDAC_mask_register(self, DAC_byte):
        """When writing to the DAC, load the 8-bit LDAC register. 
        Default: 0: the LDAC pin works normally. Setting the bits to 1 forces that DAC channel to ignore transitions on the LDAC pin, regardless of the LDAC pin's state.
        This allows you to select which channels respond to the LDAC pin.
        Address bits are ignored.
        :param DAC_byte: D0 to D7 determine which DAC channels are adjusted.
        """
        # The command for LDAC mask register is 0101 = 0x50
        self.BUFFER[0] = 0x50

        self.write_bytes(self.BUFFER)


    def software_reset(self):
        """This function resets the DAC to the power-on reset code.
        """
        # The command for software reset is 0110 = 0x60
        self.BUFFER[0] = 0x60
        self.BUFFER[1] = 0x12
        self.BUFFER[2] = 0x34

        self.write_bytes(self.BUFFER)


    def internal_reference_setup(self):
        pass


    def register_readback(self, register):
        """Selects a register and then reads from it.
        This device does this over two separate but sequential writes.

        :param register: the register to read from.
        :returns: results[1:], the contents of the register read from
        """
        # Command for readback register enable  is 1001 = 0x90
        self.BUFFER[0] = 0x90 | register
        self.write_bytes(self.BUFFER)

        # A second write is needed to read back from the previous write
        self.BUFFER[0] = 0x00
        results = self.transfer(self.BUFFER)
        return results[1:]


    def update_all_input_channels(self, voltage):
        """Update all input register channels simultaneously with the input data. The address bits are ignored.
        :param data: the data to be written
        """
        # Function for updating all channels of an input register is 1010 = 0xA0
        self.BUFFER[0] = 0xA0

        dac_val = int(float(voltage)/2.5 * 0xFFFF)
        dac_msb = (dac_val  >> 8) & 0xFF
        dac_lsb = dac_val & 0xFF

        self.BUFFER[1] = dac_msb
        self.BUFFER[2] = dac_lsb

        self.write_bytes(self.BUFFER)



    def update_all_dac_input_channels(self, byte1, byte2):
        """Update all DAC register and input register channels simultaneously with the input data. The address bits are ignored.
        """
        # Function for updating all input/DAC register channels is 1011 = 0xB0
        self.BUFFER[0] = 0xB0

        dac_val = int(float(voltage)/2.5 * 0xFFFF)
        dac_msb = (dac_val  >> 8) & 0xFF
        dac_lsb = dac_val & 0xFF

        self.BUFFER[1] = dac_msb
        self.BUFFER[2] = dac_lsb

        self.write_bytes(self.BUFFER)