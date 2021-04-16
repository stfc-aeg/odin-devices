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

class MAX5306 (SPIDevice):
    def __init__(self, Vref: float, bus, device, bipolar=False):

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

        self.reset()

    def _send_command(self, command: int, data: int):
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

        self.write_16(word_bytes)

    def reset(self):
        self._send_command(_COMMAND_RESET, 0)

    def set_output(self, output_number: int, output_voltage: float):
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

        # Load the DAC value into the input register for the selected output number
        self._send_command(_COMMAND_SET_INPUT_REG[output_number], dac_value)

        # Latch the input register to the DAC register for the specified output
        # (only necessary if nLDAC is not held low externally)
        ldac_select_data = 0b1 << (output_number+ 3)
        self._send_command(_COMMAND_LATCH_DAC_OUTPUTS, ldac_select_data)

