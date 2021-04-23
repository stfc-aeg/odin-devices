"""MAX5306 - device access class for the MAX5306 12-bit 8-channel SPI DAC.

This class implements support for the MAX5306 SPI DAC, which has 8 channels with a 12-bit DAC for
each. All channels share a Vref voltage reference.

Although the MAX5306 is capable of write-thru with daisy-chained devices, this has not yet been
implemented.

Joseph Nobes, Grad Embedded Sys Eng, STFC Detector Systems Software Group
"""

from odin_devices.spi_device import SPIDevice, SPIException
import logging

# 4-bit SPI command fields
_COMMAND_RESET = 0b0001                 # Reset all registers
_COMMAND_SET_INPUT_REG = {1: 0b0010,    # Set the input register for individual channels
                          2: 0b0011,
                          3: 0b0100,
                          4: 0b0101,
                          5: 0b0110,
                          6: 0b0111,
                          7: 0b1000,
                          8: 0b1001}
_COMMAND_INPUT_WRITETHRU__1_4 = 0b1010  # Set the input register with writethru for outputs 1-4
_COMMAND_INPUT_WRITETHRU__5_8 = 0b1011  # Set the input register with writethru for outputs 5-8
_COMMAND_SET_INPUT_ALL = 0b1101         # Set the input registers for all outputs (no latch)
_COMMAND_SET_OUTPUT_ALL = 0b1100        # Set the DAC and input registers for all outputs
_COMMAND_LATCH_DAC_OUTPUTS = 0b1110     # Latch selected input register values to their output DACs
_COMMAND_SET_POWER = 0b1111             # Set power mode for given output. See _POWER_SET_LSBS_x

_POWER_SET_LSBS_POWERUP = 0b11          # Power up the output
_POWER_SET_LSBS_SHUTDOWN1 = 0b01        # Set output to high impedance
_POWER_SET_LSBS_SHUTDOWN2 = 0b10        # Ground output through 1kohm
_POWER_SET_LSBS_SHUTDOWN3 = 0b00        # Ground output through 100kohm (default output state)

class MAX5306 (SPIDevice):
    def __init__(self, Vref: float, bus, device, bipolar=False):
        """
        MAX5306 Init. Vref is the reference connected to the device, which will be used to calculate
        DAC values to reach target output values. The bipolar parameter changes the calculation for
        output DAC value so that it will be compatible with a bipolar output stage (see the MAX5306
        datasheet)

        :param Vref:    Refernce voltage
        :param bus:     spidev bus
        :param device:  spidev device
        """

        # Check Vref is valid
        try:
            float(Vref)
        except Exception:
            raise TypeError(
                    "Vref {} cannot be converted to float".format(Vref))
        if Vref > 5.5 or Vref < 0.8:
            raise ValueError("Vref is max Vdd and min 0.8v")

        super().__init__(bus, device)

        self._Vref = Vref
        self._is_bipolar = bipolar

        self._logger = logging.getLogger('odin_devices.max5306@spidev={},{}'.format(bus, device))

        self.reset()

    def _send_command(self, command: int, data: int):
        """
        Send a 16-bit word to the device, comprised of a 4-bit command and 12-but data field.

        :param command:     4-bit command (see _COMMAND_x above)
        :param data:        12-bit data field, contents depends on command
        """

        # Check inputs are int
        if type(command) is not int or type(data) is not int:
            raise ValueError("command and data values should be int")

        # Check command and data fit in the correct number of bits
        if command > 0xF or command < 0:
            raise ValueError("Command bits ({}) must positive and fit in 4-bit field")
        if data > 0xFFF or data < 0:
            raise ValueError("Command bits ({}) must be positive and fit in 12-bit field")

        word = ((command << 12) | data) & 0xFFFF
        word_bytes = word.to_bytes(length=2, byteorder='big')

        self._logger.debug("Writing bytes 0x{}".format(word_bytes.hex()))

        #self.write_16(word_bytes)
        self.transfer(list(word_bytes), end=2)

    def _set_output_power(self, output_number: int, power_mode: int):
        """
        Set the output power state of a given output number. This can be one of four values, where
        one (_POWER_SET_LSBS_POWERUP) is powered up, and the others are various types of shutdown.

        :param output_number:       The output number to apply the new power state to
        :param power_mode:          2-bit code representing power mode. See _POWER_SET_LSBS_x above.
        """

        # Check output number is valid
        if output_number not in range(1,9):
            raise IndexError("output_number must be an integer 1-8")

        # Check power_mode is valid
        if power_mode not in [_POWER_SET_LSBS_POWERUP, _POWER_SET_LSBS_SHUTDOWN1,
                _POWER_SET_LSBS_SHUTDOWN2, _POWER_SET_LSBS_SHUTDOWN3]:
            raise ValueError("power_mode invalid")

        # Assemble data packet
        power_mode_data = 0b1 << (output_number + 3)
        power_mode_data |= (power_mode << 2)

        self._send_command(_COMMAND_SET_POWER, power_mode_data)

    def power_off_output(self, output_number):
        """
        External function for setting the power off for a given output. This simplifies things by
        using the shutdown-3 mode (output connected to ground via 100kohm resistor) since this is
        the default state outputs are in on POR.

        :param output_number:   The output to power off
        """
        self._set_output_power(output_number, _POWER_SET_LSBS_SHUTDOWN3)

    def power_on_output(self, output_number):
        """
        External function for setting the power on for a given output. This is only needed if the
        power_off_output() function has been called, or set_output() was called with set_power=True.

        :param output_number:   The output to power on
        """
        self._set_output_power(output_number, _POWER_SET_LSBS_POWERUP)

    def reset(self):
        """
        Reset the device (POR)
        """
        self._send_command(_COMMAND_RESET, 0)

    def set_output(self, output_number: int, output_voltage: float, set_power=True):
        """
        Set the output DAC to output a specified voltage. If set_power is set False, the output will
        not be powered up, and this will need doing manually with power_on_output(). The allowable
        voltage ranges are checked based on the reference voltage Vref and whether the device is
        configured for bipolar or unipolar operation.

        :param output_number:   The output the voltage will be set for
        :param output_voltage:  The output voltage that should be set
        :param set_power:       (Optional) Set False so that this output is not forced on
        """

        # If set_power is False, power_on will not be called for this output

        # Check output number is valid
        if output_number not in range(1,9):
            raise IndexError("output_number must be an integer 1-8")

        # Check output voltage is correct format
        try:
            float(output_voltage)
        except Exception:
            raise TypeError(
                    "Type {} could not be converted to float".format(type(output_voltage)))

        # Check that the target output voltage is valid for the given output mode
        if self._is_bipolar:
            if output_voltage < (-self._Vref) or output_voltage > ((2047.0/2048.0)*self._Vref):
                raise ValueError(
                        "Bipolar voltage must be between -Vref and (2047/2048)*Vref: " +
                        "\tVref = {}v\n\tVout Limit = {}v".format(self._Vref,
                                                                  (2047.0/2048.0)*self._Vref))
        else:
            if output_voltage < 0 or output_voltage > ((4095.0/4096.0)*self._Vref):
                raise ValueError(
                        "Unipolar voltage must be between 0 and (4095/4096)*Vref: " +
                        "\tVref = {}v\n\tVout Limit = {}v".format(self._Vref,
                                                                  (4095.0/4096.0)*self._Vref))

        # Calculate the value the 12-bit output DAC should be set to
        if self._is_bipolar:    # bipolar
            dac_value = 2048 * ((float(output_voltage) / float(self._Vref)) + 1)
            dac_value = int(round(dac_value, 0))
            pass
        else:                   # unipolar
            dac_value = (float(output_voltage) / float(self._Vref)) * 4096.0
            dac_value = int(round(dac_value, 0))

        # Correct values rounded to just outside limits, assuming the result is still close enough
        if dac_value == -1:
            dac_value = 0
            self._logger.warning("Value was at limit, corrected DAC calculation to 0")
        elif dac_value == 4096:
            dac_value = 4095
            self._logger.warning("Value was at limit, corrected DAC calculation to 4095")

        # Check DAC value is valid
        if dac_value < 0 or dac_value > 4095:
            raise ValueError(
                    "No valid DAC value found for output {}v ".format(output_voltage) +
                    "with Vref {}v.".format(self._Vref))

        # Make sure the output is powered up
        if set_power:
            self.power_on_output(output_number)

        # Load the DAC value into the input register for the selected output number
        self._send_command(_COMMAND_SET_INPUT_REG[output_number], dac_value)

        # Latch the input register to the DAC register for the specified output
        # (only necessary if nLDAC is not held low externally)
        ldac_select_data = 0b1 << (output_number+ 3)
        self._send_command(_COMMAND_LATCH_DAC_OUTPUTS, ldac_select_data)

