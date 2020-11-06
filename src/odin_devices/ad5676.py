"""AD5676R device class.

This class implements support for the AD5676R DAC.

For device information, see datasheet pdf available at:
https://www.analog.com/media/en/technical-documentation/data-sheets/ad5672r_5676r.pdf

Most important is that the device writes and reads 3 bytes at a time.
The first byte is a command and an address (4 bits each), the remaining two bytes are data.
"""

from odin_devices.spi_device import SPIDevice

# Command bits for functions
CMD_NO_OPERATION = 0x00
CMD_INP_REG_WRITE = 0x10
CMD_INP_TO_DAC = 0x20
CMD_WRITE_TO_DAC = 0x30
CMD_POWER_DOWN = 0x40
CMD_LDAC_MASK_REG = 0x50
CMD_SOFTWARE_RESET = 0x60
CMD_REG_READBACK = 0x90
CMD_UPDATE_ALL_INPUTS = 0xA0
CMD_UPDATE_ALL_DAC_INPUTS = 0xB0

class AD5676R(SPIDevice):
    """AD5676R class.

    This class implements support for the AD5676R device.
    """
    def __init__(self):
        """Initialise the AD5676R device. Many of the settings are set in spi_device.

        SPIDevice.__init__ is provided bus, device, bits_per_word (optional) and hz (optional).
        Settings can be adjusted with the functions in spi_device.
        """
        SPIDevice.__init__(self, 0, 0)

        # This device is compatible with SPI modes 1 and 2.
        # Data is sampled on the falling edge of the clock pulse.
        self.set_mode(1)
        # All writes and reads with the AD5676R are three bytes long.
        self.set_buffer_length(3)

        self.Vref = 2.5  # 2.5V = 0xFFFF when writing bytes

    def input_register_write(self, register, voltage):
        """Write to the dedicated input register for each DAC individually.

        If LDAC is low, the input register is transparent.
        Otherwise, controlled by the LDAC mask register.

        :param register: selected register to write to (0000 --> 0111)
        :param voltage: the provided voltage to be converted and written
        """
        # Command for write_to_input is 0001 = 0x10 in the command byte.
        # Voltage/Vref * max value
        dac_val = int(float(voltage)/2.5 * 0xFFFF)

        self.buffer[0] = CMD_INP_REG_WRITE | register
        self.buffer[1] = (dac_val >> 8) & 0XFF
        self.buffer[2] = dac_val & 0XFF

        self.write_24(self.buffer)

    def input_into_dac(self, DAC_byte):
        """Load DAC registers and outputs with the contents of the input register.

        Data bits D0 to D7 specify which DAC registers receive data from the input register.
        Data is transferred when the bit is 1.

        :param register: Specified register
        :param DAC_byte: a user-provided byte with the DACs they want updated specified
        """
        # Command for DAC input register load is 0010 = 0x20.
        self.buffer[0] = CMD_INP_TO_DAC
        self.buffer[1] = 0x00
        self.buffer[2] = DAC_byte

        self.write_24(self.buffer)

    def write_to_dac(self, channel, voltage):
        """Write to and update DAC Channel n.

        Updating the DAC channel changes its output voltage, with a variable maximum.
        If the GAIN pin is tied to GND, all DACs have an output span of 0V to Vref (2.5V).
        If the GAIN pin is tied to Vlogic, all DACs output a span of 0V to 2*Vref(5V).

        :param channel: the provided DAC channel,
                        must be between 0000 and 0111 inclusive.
        :param voltage: the provided voltage.
        """
        # Command for DAC register update is 0010 = 0x30.
        dac_val = int(float(voltage)/2.5 * 0xFFFF)

        self.buffer[0] = CMD_WRITE_TO_DAC | channel
        self.buffer[1] = (dac_val >> 8) & 0xFF
        self.buffer[2] = dac_val & 0xFF

        self.write_24(self.buffer)

    def power_down(self, DAC_binary):
        """Power down the device or change its mode of operation.

        These modes are programmable by setting the 16 data bits in the input shift register.
        Two bits refer to each DAC, where DB0, DB1 refer to DAC channel 0.
        DB2, DB3 refer to DAC channel 2, etc..
        00 is normal operation. The two power-down options are as follows:
        01 connects the output internally to GND through a 1kOhm resistor,
        11 leaves it open-circuited (tristate).

        :param DAC_binary: a binary value that specifies how each channel will operate.
        """
        # The command for DAC power up/down is 0100 = 0x40.
        self.buffer[0] = CMD_POWER_DOWN
        self.buffer[1] = (DAC_binary >> 8) & 0xFF
        self.buffer[2] = DAC_binary & 0xFF

        self.write_24(self.buffer)

    def LDAC_mask_register(self, DAC_byte):
        """When writing to the DAC, load the 8-bit LDAC register.

        Default: 0: the LDAC pin works normally.
        Option: 1: force DAC channel to ignore transitions on LDAC pin, regardless of pin's state.
        This allows you to select which channels respond to the LDAC pin.
        Address bits are ignored. D8 to D15 are zeroes.

        :param DAC_byte: D0 to D7 determine which DAC channels are adjusted.
        """
        # The command for LDAC mask register is 0101 = 0x50.
        self.buffer[0] = CMD_LDAC_MASK_REG
        self.buffer[1] = 0x00
        self.buffer[2] = DAC_byte

        self.write_24(self.buffer)

    def software_reset(self):
        """Reset DAC to power-on reset code."""
        # The command for software reset is 0110 = 0x60.
        # The bytes written after the command are 0x1234.
        self.buffer[0] = CMD_SOFTWARE_RESET
        self.buffer[1] = 0x12
        self.buffer[2] = 0x34

        self.write_24(self.buffer)

    def register_readback(self, register):
        """Select a register and then read from it.

        This device does this over two separate but sequential writes.

        :param register: the register to read from.
        :returns: results[1:], the contents of the register read from.
        """
        # Command for readback register enable is 1001 = 0x90.
        self.buffer[0] = CMD_REG_READBACK | register
        self.buffer[1] = 0x00
        self.buffer[2] = 0x00

        self.write_24(self.buffer)

        # A second write is needed to read back from the previous write.
        self.buffer[0] = 0x00
        results = self.transfer(self.buffer)
        return results[1:]

    def update_all_input_channels(self, voltage):
        """Update all input register channels simultaneously with the input data.

        The address bits are ignored.

        :param data: the data to be written
        """
        # Function for updating all input register channels is 1010 = 0xA0.
        dac_val = int(float(voltage)/2.5 * 0xFFFF)

        self.buffer[0] = CMD_UPDATE_ALL_INPUTS
        self.buffer[1] = (dac_val >> 8) & 0xFF
        self.buffer[2] = dac_val & 0xFF

        self.write_24(self.buffer)

    def update_all_dac_input_channels(self, voltage):
        """Update all DAC register and input register channels simultaneously with the input data.

        The address bits are ignored.

        :param voltage: voltage to be converted to bytes and written
        """
        # Function for updating all input/DAC register channels is 1011 = 0xB0.
        dac_val = int(float(voltage)/2.5 * 0xFFFF)

        self.buffer[0] = CMD_UPDATE_ALL_DAC_INPUTS
        self.buffer[1] = (dac_val >> 8) & 0xFF
        self.buffer[2] = dac_val & 0xFF

        self.write_24(self.buffer)
        # OR self.write_24(), buffer is assumed if set and no data provided
