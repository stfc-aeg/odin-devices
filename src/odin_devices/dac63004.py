"""ADAC63004 class.
    Data sheet: https://www.ti.com/product/DAC63004
    Page 54: register map

Adam Davis, STFC Application Engineering Group.
"""

from odin_devices.i2c_device import I2CDevice
import logging
import math
from enum import Enum


class DAC63004(I2CDevice):
    """ADAC63004 class - DAC device converting register values to voltage or constant current
    Data sheet: https://www.ti.com/product/DAC63004
    Page 54: register map
    """

    _25rangeOffset = -0.13042
    _50rangeOffset = -10.9617
    _125rangeOffset = -11.1254
    _250rangeOffset = -10.7742
    device_registers = {
        "NOOP": {"address": 0x00, "flipped": False},
        "DAC_0_MARGIN_HIGH": {"address": 0x01, "flipped": True},
        "DAC_0_MARGIN_LOW": {"address": 0x02, "flipped": True},
        "DAC_0_VOUT_CMP_CONFIG": {"address": 0x03, "flipped": True},
        "DAC_0_IOUT_MISC_CONFIG": {"address": 0x04, "flipped": True},
        "DAC_0_CMP_MODE_CONFIG": {"address": 0x05, "flipped": True},
        "DAC_0_FUNC_CONFIG": {"address": 0x06, "flipped": True},
        "DAC_1_MARGIN_HIGH": {"address": 0x07, "flipped": True},
        "DAC_1_MARGIN_LOW": {"address": 0x08, "flipped": True},
        "DAC_1_VOUT_CMP_CONFIG": {"address": 0x09, "flipped": True},
        "DAC_1_IOUT_MISC_CONFIG": {"address": 0x0A, "flipped": True},
        "DAC_1_CMP_MODE_CONFIG": {"address": 0x0B, "flipped": True},
        "DAC_1_FUNC_CONFIG": {"address": 0x0C, "flipped": True},
        "DAC_2_MARGIN_HIGH": {"address": 0x0D, "flipped": True},
        "DAC_2_MARGIN_LOW": {"address": 0x0E, "flipped": True},
        "DAC_2_VOUT_CMP_CONFIG": {"address": 0x0F, "flipped": True},
        "DAC_2_IOUT_MISC_CONFIG": {"address": 0x10, "flipped": True},
        "DAC_2_CMP_MODE_CONFIG": {"address": 0x11, "flipped": True},
        "DAC_2_FUNC_CONFIG": {"address": 0x12, "flipped": True},
        "DAC_3_MARGIN_HIGH": {"address": 0x13, "flipped": True},
        "DAC_3_MARGIN_LOW": {"address": 0x14, "flipped": True},
        "DAC_3_VOUT_CMP_CONFIG": {"address": 0x15, "flipped": True},
        "DAC_3_IOUT_MISC_CONFIG": {"address": 0x16, "flipped": True},
        "DAC_3_CMP_MODE_CONFIG": {"address": 0x17, "flipped": True},
        "DAC_3_FUNC_CONFIG": {"address": 0x18, "flipped": True},
        "DAC_0_DATA": {"address": 0x19, "flipped": True},
        "DAC_1_DATA": {"address": 0x1A, "flipped": True},
        "DAC_2_DATA": {"address": 0x1B, "flipped": True},
        "DAC_3_DATA": {"address": 0x1C, "flipped": True},
        "COMMON_CONFIG": {"address": 0x1F, "flipped": True},
        "COMMON_TRIGGER": {"address": 0x20, "flipped": False},
        "COMMON_DAC_TRIG": {"address": 0x21, "flipped": False},
        "GENERAL_STATUS": {"address": 0x22, "flipped": False},
        "CMP_STATUS": {"address": 0x23, "flipped": False},
        "GPIO_CONFIG": {"address": 0x24, "flipped": False},
        "DEVICE_MODE_CONFIG": {"address": 0x25, "flipped": False},
        "INTERFACE_CONFIG": {"address": 0x26, "flipped": False},
        "SRAM_CONFIG": {"address": 0x2B, "flipped": False},
        "SRAM_DATA": {"address": 0x2C, "flipped": False},
        "DAC_0_DATA_8BIT": {"address": 0x40, "flipped": False},
        "DAC_1_DATA_8BIT": {"address": 0x41, "flipped": False},
        "DAC_2_DATA_8BIT": {"address": 0x42, "flipped": False},
        "DAC_3_DATA_8BIT": {"address": 0x43, "flipped": False},
        "BRDCAST_DATA": {"address": 0x50, "flipped": True},
    }

    internal_reference_voltage = 1.212
    external_reference_voltage = None
    VDD_reference_voltage = None

    class VoltageGain(Enum):
        """An enum to represent the setting for a register that determines the voltage gain and
        reference voltage for a dac

        VoltageGain.EXT_REF_1x: Gain = 1x, external reference on VREF pin,
        VoltageGain.VDD_REF_1x: Gain = 1x, VDD as reference,
        VoltageGain.INT_REF_1_5x: Gain = 1.5x, internal reference,
        VoltageGain.INT_REF_2x: Gain = 2x, internal reference,
        VoltageGain.INT_REF_3x: Gain = 3x, internal reference,
        VoltageGain.INT_REF_4x: Gain = 4x, internal reference"""
        EXT_REF_1x = 0b0
        VDD_REF_1x = 0b10000000000
        INT_REF_1_5x = 0b100000000000
        INT_REF_2x = 0b0110000000000
        INT_REF_3x = 0b1000000000000
        INT_REF_4x = 0b1010000000000

    class VoltagePowerDownMode(Enum):
        """An enum used to represent the way in which the voltage output of a DAC will be powered
        down

        VoltagePowerDownMode.POW_DOWN_10k: Power-down VOUT-X with 10 KΩ to AGND
        VoltagePowerDownMode.POW_DOWN_100k: Power-down VOUT-X with 100 KΩ to AGND
        VoltagePowerDownMode.POW_DOWN_HI_Z: Power-down VOUT-X with Hi-Z to AGND"""
        POW_DOWN_10k = 0b10
        POW_DOWN_100k = 0b100
        POW_DOWN_HI_Z = 0b110

    class CurrentRange(Enum):
        """An enum used to represent each of the discrete ranges you can have selected for a dacs
        current output

        CurrentRange.RANGE_0_25 = 0 - 25 microamps
        CurrentRange.RANGE_0_50 = 0 - 50 microamps
        CurrentRange.RANGE_0_125 = 0 - 125 microamps
        CurrentRange.RANGE_0_250 = 0 - 250 microamps
        CurrentRange.RANGE_0_negative_24 = 0 - -24 microamps
        CurrentRange.RANGE_0_negative_48 = 0 - -48 microamps
        CurrentRange.RANGE_0_negative_120 = 0 - -120 microamps
        CurrentRange.RANGE_0_negative_240 = 0 - -240 microamps
        CurrentRange.RANGE_negative_25_25 = -25 - 25 microamps
        CurrentRange.RANGE_negative_50_50 = -50 - 50 microamps
        CurrentRange.RANGE_negative_125_125 = -125 - 125 microamps
        CurrentRange.RANGE_negative_250_250 = -250 - 250 microamps"""
        RANGE_0_25 = 0b0
        RANGE_0_50 = 0b1000000000
        RANGE_0_125 = 0b10000000000
        RANGE_0_250 = 0b11000000000
        RANGE_0_negative_24 = 0b100000000000
        RANGE_0_negative_48 = 0b101000000000
        RANGE_0_negative_120 = 0b110000000000
        RANGE_0_negative_240 = 0b111000000000
        RANGE_negative_25_25 = 0b1000000000000
        RANGE_negative_50_50 = 0b1001000000000
        RANGE_negative_125_125 = 0b1010000000000
        RANGE_negative_250_250 = 0b1011000000000

    def __init__(
        self,
        address,
        busnum,
        external_reference_voltage=None,
        VDD_reference_voltage=None,
        **kwargs,
    ):
        """Initialise this device, setting the i2c address and bus, with the option to set the
        external and VDD reference voltages

        Args:
            address (int): the I2C address of this device
            busnum (int): the i2c bus this device is on
            external_reference_voltage (float, optional): the external reference voltage being
            provided to this device. Defaults to None.
            VDD_reference_voltage (float, optional): the VDD reference voltage being provided to
            this device. Defaults to None.
        """
        I2CDevice.__init__(self, address, busnum, **kwargs)
        self.external_reference_voltage = external_reference_voltage
        self.VDD_reference_voltage = VDD_reference_voltage

    def read_register_address(self, register_name):
        """Get the address of the specified register by name, returning none
        if the name does not match any registers.

        Args:
            register_name (string): the name of the register we want to get the address for
        """
        if register_name in self.device_registers:
            return self.device_registers[register_name]["address"]
        else:
            raise KeyError("Register " + register_name + " does not match any known registers.")

    def read_modify_write(self, register_name, mask, value):
        """Perform a read-modify-write operation on a register.

        Args:
            register_name (string): Address of the register to modify.
            mask (int): Bit mask specifying the bits to modify.
            value (int): 16-bit integer value to apply to the masked bits.
        """
        current_value = self.read_register(
            self.read_register_address(register_name),
            self.device_registers[register_name]["flipped"],
            False,
        )
        modified_value = (current_value & ~mask) | (value & mask)
        self.write_register(
            self.read_register_address(register_name),
            modified_value,
            self.device_registers[register_name]["flipped"],
        )

    def write_register(self, register_address, value, flipped=False, debug=False):
        """Write a 16-bit value to a register accessed using the address

        Args:
            register_address (int): Address of the register to write.
            value (int): 16-bit integer value to write to the register.
            flipped (bool, optional): For certain registers, the first 8 bits and the last 8 bits
            are read in the wrong order. If flipped is set to true, it swaps the first and last 8
            bits to fix this.
            debug (bool, optional): If true, print the operation that happened. Used for testing
            and debugging. Defaults to False.
        """
        if flipped:
            self.write16flipped(register_address, value)
        else:
            self.write16(register_address, value)
        if debug:
            print(
                "Wrote value "
                + str(bin(value))
                + " to register at address "
                + str(hex(register_address)))

    def read_register_by_name(self, name, debug=True):
        """Read a 16-bit value from a register accessed using the name

        Args:
            name (string): name of the register to read from.
            debug (bool, optional): For certain registers, the first 8 bits and the last 8 bits are
            read in the wrong order. If flipped is set to true, it swaps the first and
            last 8 bits to fix this. Defaults to True.

        Raises:
            KeyError: If no register is found with a name matching that provided, a KeyError is
            raised as an invalid name was entered.

        Returns:
            int: the value stored in the register that was read (16 bit value)
        """
        if name in self.device_registers.keys():
            register_address = self.device_registers[name]["address"]
            flipped = self.device_registers[name]["flipped"]
            if flipped:
                result = self.readU16flipped(register_address)
            else:
                result = self.readU16(register_address)
            if debug:
                print(
                    "Read register at address "
                    + str(hex(register_address))
                    + " as "
                    + str(bin(result))
                )
            return result
        else:
            raise KeyError("No register found matching name '" + name + "'.")

    def read_register(self, register_address, flipped=False, debug=False):
        """Read a 16-bit value from a register accessed using the address

        Args:
            register_address (int): Address of the register to read from.
            flipped (bool, optional): For certain registers, the first 8 bits and the last 8 bits
            are read in the wrong order. If flipped is set to true, it swaps the first and
            last 8 bits to fix this. Defaults to False.
            debug (bool, optional): If true, print the operation that happened. Used for testing
            and debugging. Defaults to False.

        Returns:
            int: the value read from the register at the provided address (16 bit value)
        """
        if flipped:
            result = self.readU16flipped(register_address)
        else:
            result = self.readU16(register_address)
        if debug:
            print(
                "Read register at address "
                + str(hex(register_address))
                + " as "
                + str(bin(result))
            )
        return result

    def write16flipped(self, reg, value):
        """Write a 16-bit value to the specified register/address pair, replacing the first 8 bits
        with the last 8 bits and vice versa

        Args:
            reg (int): the address of the register to write to
            value (int): the value to write to the register
        """
        try:
            # flip the first and last 8 bits around
            flipped_value = ((value & 0xFF00) >> 8) | ((value & 0x00FF) << 8)
            # write the flipped value
            self.bus.write_word_data(self.address, reg, flipped_value)
        except IOError as err:
            logging.error("--------------------------------------------------")
            logging.error("Error: " + str(err))
            logging.error(
                "Write16 failed to write value "
                + str(bin(value))
                + " to register "
                + str(hex(reg))
            )
            logging.error("--------------------------------------------------")
            return -1

    def readU16flipped(self, reg):
        """Read an unsigned 16-bit value from the I2C device, replacing the first 8 bits
        with the last 8 bits and vice versa

        Args:
            reg (int): the address of the register to read

        Returns:
            int: the value read from the register at the provided address (16 bit value)
        """
        try:
            original = self.bus.read_word_data(self.address, reg)
            # flip the first and last 8 bits around
            result = ((original & 0xFF00) >> 8) | ((original & 0x00FF) << 8)
            return result
        except IOError as err:
            logging.error("--------------------------------------------------")
            logging.error("Error: " + str(err))
            logging.error("Read16 failed to read value from register " + str(hex(reg)))
            logging.error("--------------------------------------------------")
            return -1

    def put_dac_into_current_mode(
        self, index, voltageTermination=VoltagePowerDownMode.POW_DOWN_HI_Z
    ):
        """Set the dac at the provided index into current output mode, powering down the voltage
        mode in the method specified

        Args:
            index (int): the index (0,1,2 or 3) of the dac to set into current output mode
            voltageTermination (VoltagePowerDownMode, optional): The mode we want to use to power
            down the voltage output
            VoltagePowerDownMode.POW_DOWN_10k: Power-down VOUT-X with 10 KΩ to AGND
            VoltagePowerDownMode.POW_DOWN_100k: Power-down VOUT-X with 100 KΩ to AGND
            VoltagePowerDownMode.POW_DOWN_HI_Z: Power-down VOUT-X with Hi-Z to AGND
            Defaults to VoltagePowerDownMode.POW_DOWN_HI_Z.

        Raises:
            IndexError: Raised if an invalid index is provided - only accepted indexes are 0, 1, 2
            or 3
        """
        # There are only 4 dacs, so check there is a valid index
        if index >= 0 and index <= 3:
            # Build the mask and value to write based on the index of the dac we want to enable.
            # To set a dac to current, we want to write 110 to the appropriate section on the
            # COMMON_CONFIG register.
            # The 11 sets the voltage output for the dac to Hi-Z power down mode
            # The 0 sets the current output for the dac to powered up mode
            # See page 61 in the data sheet for more info on the COMMON_CONFIG register
            mask = 0b111 << (3 * index)
            write = voltageTermination.value << (3 * index)

            self.read_modify_write("COMMON_CONFIG", mask, write)
        else:
            raise IndexError("Index " + str(index) + " is not a valid index (0,1,2 or 3).")

    def put_dac_into_voltage_mode(self, index):
        """Set the dac at the provided input to voltage output mode, powering down current mode

        Args:
            index (int): a number between zero and 3, telling us which dac we want to put into
            voltage mode

        Raises:
            IndexError: Raised when an invalid index is provided - only accepted indexes are 0, 1,
            2 or 3
        """

        # There are only 4 dacs, so check there is a valid index
        if index >= 0 and index <= 3:
            # Build the mask and value to write based on the index of the dac we want to enable.
            # To set a dac to voltage, we want to write 001 to the appropriate section on the
            # COMMON_CONFIG register.
            # The 00 sets the voltage output for the dac to powered up mode
            # The 1 sets the current output for the dac to powered down mode
            # See page 61 in the data sheet for more info on the COMMON_CONFIG register
            mask = 0b111 << (3 * index)
            write = 0b001 << (3 * index)
            self.read_modify_write("COMMON_CONFIG", mask, write)
        else:
            raise IndexError("Index " + str(index) + " is not a valid index (0,1,2 or 3).")

    def set_dac_current_range(self, current_range: CurrentRange, index):
        """specify a current range for the dac at the provided index

        Args:
            current_range (CurrentRange): the range you want to set
                CurrentRange.RANGE_0_25 = 0 - 25 microamps
                CurrentRange.RANGE_0_50 = 0 - 50 microamps
                CurrentRange.RANGE_0_125 = 0 - 125 microamps
                CurrentRange.RANGE_0_250 = 0 - 250 microamps
                CurrentRange.RANGE_0_negative_24 = 0 - -24 microamps
                CurrentRange.RANGE_0_negative_48 = 0 - -48 microamps
                CurrentRange.RANGE_0_negative_120 = 0 - -120 microamps
                CurrentRange.RANGE_0_negative_240 = 0 - -240 microamps
                CurrentRange.RANGE_negative_25_25 = -25 - 25 microamps
                CurrentRange.RANGE_negative_50_50 = -50 - 50 microamps
                CurrentRange.RANGE_negative_125_125 = -125 - 125 microamps
                CurrentRange.RANGE_negative_250_250 = -250 - 250 microamps
            index (int): the index of the dac we want to specify the current range for
        """
        # Change the current range for the DAC with the index provided. The value provided should
        # be a binary string, one of those listed above.
        # See page 58 for more info on the DAC_X_IOUT_MISC_CONFIG register
        self.read_modify_write(
            "DAC_" + str(index) + "_IOUT_MISC_CONFIG",
            0b1111000000000,
            current_range.value,
        )

    def set_external_reference_voltage(self, new_reference_voltage):
        """set the external reference voltage to a new value

        Args:
            new_reference_voltage (float): the new reference voltage you are setting
        """
        self.external_reference_voltage = new_reference_voltage

    def set_VDD_reference_voltage(self, new_reference_voltage):
        """set the VDD reference voltage to a new value

        Args:
            new_reference_voltage (float): the new reference voltage you are setting
        """
        self.VDD_reference_voltage = new_reference_voltage

    def set_dac_voltage(self, index, voltage):
        """Set the output for the given index to the given voltage based on the reference voltage

        Args:
            index (int): the index of the dac we want to specify the voltage for
            voltage (int): the voltage we want to set the output to

        Raises:
            Exception: This error will be raised if when the VOUT_CMP_CONFIG register for the dac
            of the provided index is read back, the result is not a valid reference voltage type
            110 and 111 are the only invalid results possible
            Exception: This error will be raised if the reference voltage value for the current
            setting has not been set by the user and remains at its default value, None
        """
        setting = (
            self.read_register_by_name("DAC_" + str(index) + "_VOUT_CMP_CONFIG")
            & 0b1110000000000
        )
        setting = setting >> 10
        reference_voltage = None
        gain = None

        if setting == 0b0:
            reference_voltage = self.external_reference_voltage
            gain = 1
        elif setting == 0b001:
            reference_voltage = self.VDD_reference_voltage
            gain = 1
        elif setting == 0b010:
            reference_voltage = self.internal_reference_voltage
            gain = 1.5
        elif setting == 0b011:
            reference_voltage = self.internal_reference_voltage
            gain = 2
        elif setting == 0b100:
            reference_voltage = self.internal_reference_voltage
            gain = 3
        elif setting == 0b101:
            reference_voltage = self.internal_reference_voltage
            gain = 4
        else:
            raise Exception(
                "Error - reference voltage setting not recognized ("
                + str(bin(setting))
                + ")"
                )
        if reference_voltage is not None:
            value_to_write = round(voltage * 4096 / (reference_voltage * gain))
            self._set_dac_output(value_to_write, index, False)
        else:
            raise Exception(
                "No reference voltage value provided for the current reference voltage setting " +
                "(Check you have set values for the VDD and external reference inputs)."
                )

    def set_dac_current_micro_amps(self, index, current):
        """Set the current range to an appropriate value for the current requested, then calculate
        the value that needs to be written to get the current we want and write that value.

        Args:
            index (int): the index of the dac we want to set the current for
            current (int): the amount of microamps we want to set the current to

        Raises:
            Exception: Raised when the user provided a current greater than 250 or less than -240,
            since those values are not supported by the hardware
        """
        if current > 250 or current < -240:
            raise Exception("Invalid current - current must be between -240 and 250.")
        range = None
        value_to_write = None
        # get the range based on the current entered
        if current > 125:
            range = DAC63004.CurrentRange.RANGE_0_250
            value_to_write = math.floor(
                (256 * abs(current) / 250) + self._250rangeOffset
            )
        elif current > 50:
            range = DAC63004.CurrentRange.RANGE_0_125
            value_to_write = math.floor(
                (256 * abs(current) / 125) + self._125rangeOffset
            )
        elif current > 25:
            range = DAC63004.CurrentRange.RANGE_0_50
            value_to_write = math.floor((256 * abs(current) / 50) + self._50rangeOffset)
        elif current > 0:
            range = DAC63004.CurrentRange.RANGE_0_25
            value_to_write = math.floor((256 * abs(current) / 25) + self._25rangeOffset)
        elif current > -24:
            range = DAC63004.CurrentRange.RANGE_0_negative_24
            value_to_write = math.floor((20000 * abs(current) / 1957) - 12)  # +13.04241
        elif current > -48:
            range = DAC63004.CurrentRange.RANGE_0_negative_48
            value_to_write = math.floor((2000 * abs(current) / 391) - 13)  # +13.16266
        elif current > -120:
            range = DAC63004.CurrentRange.RANGE_0_negative_120
            value_to_write = math.floor((4000 * abs(current) / 1951) - 13)  # +13.18298
        elif current >= -240:
            range = DAC63004.CurrentRange.RANGE_0_negative_240
            value_to_write = math.floor(
                (10000 * abs(current) / 9751) - 13.1
            )  # +13.1966

        self.set_dac_current_range(range, index)
        # write the value to the register
        self._set_dac_output(value_to_write, index, True)

    def set_dac_voltage_gain(self, voltage_gain: VoltageGain, index):
        """set the voltage gain for the dac with the provided index

        Args:
            voltage_gain (VoltageGain): a setting which determines the amount of gain we want and
            the reference voltage we are using for this dac
                VoltageGain.EXT_REF_1x: Gain = 1x, external reference on VREF pin,
                VoltageGain.VDD_REF_1x: Gain = 1x, VDD as reference,
                VoltageGain.INT_REF_1_5x: Gain = 1.5x, internal reference,
                VoltageGain.INT_REF_2x: Gain = 2x, internal reference,
                VoltageGain.INT_REF_3x: Gain = 3x, internal reference,
                VoltageGain.INT_REF_4x: Gain = 4x, internal reference
            index (int): the index of the dac we want to specify the voltage gain for
        """
        # Change the gain for the DAC with the index provided. Gain should be a binary string, one
        # of those listed above.
        # See page 57 in the manual for more details on the DAC_X_VOUT_CMP_CONFIG register
        self.read_modify_write(
            "DAC_" + str(index) + "_VOUT_CMP_CONFIG",
            0b0001110000000000,
            voltage_gain.value,
        )

    def _set_dac_output(self, value, index, current=False):
        """Set the value in the DAC-X-DATA register (where X is the index) to the value provided,
        changing the current or voltage output based on the value provided

        See page 61 in the manual for more info on the DAC_X_DATA register

        Args:
            value (int): an 8 bit if current, or 12 bit if voltage integer detailing the value to
            write to set the dac output
            index (int): the index of the dac we want to write to
            current (bool, optional): whether we are writing a current value or a voltage value.
            Defaults to False.
        """
        value = value << 4
        if current:
            value = value << 4
        self.read_modify_write("DAC_" + str(index) + "_DATA", 0b1111111111110000, value)

    def set_all_dacs_to_voltage(self, gain=VoltageGain.EXT_REF_1x):
        """Switch all dacs into voltage output mode, setting the provided gain for each one

        Args:
            gain (VoltageGain, optional): gain and voltage reference setting to apply to all the
            voltage outputs. Defaults to VoltageGain.EXT_REF_1x.
                VoltageGain.EXT_REF_1x: Gain = 1x, external reference on VREF pin,
                VoltageGain.VDD_REF_1x: Gain = 1x, VDD as reference,
                VoltageGain.INT_REF_1_5x: Gain = 1.5x, internal reference,
                VoltageGain.INT_REF_2x: Gain = 2x, internal reference,
                VoltageGain.INT_REF_3x: Gain = 3x, internal reference,
                VoltageGain.INT_REF_4x: Gain = 4x, internal reference
        """
        # set the gain for each dac, default is EXT_REF_1x which equates to 1x external reference
        # on VREF pin
        self.set_dac_voltage_gain(gain, 0)
        self.set_dac_voltage_gain(gain, 1)
        self.set_dac_voltage_gain(gain, 2)
        self.set_dac_voltage_gain(gain, 3)
        # switch each dac into voltage output mode
        self.put_dac_into_voltage_mode(0)
        self.put_dac_into_voltage_mode(1)
        self.put_dac_into_voltage_mode(2)
        self.put_dac_into_voltage_mode(3)

    def set_all_dacs_to_current(self, current_range=CurrentRange.RANGE_0_250):
        """switch all dacs into current output mode and set all their ranges to the provided range

        Args:
            current_range (CurrentRange, optional): The range all the dacs should use for their
            current. Defaults to CurrentRange.RANGE_0_250
                CurrentRange.RANGE_0_25 = 0 - 25 microamps
                CurrentRange.RANGE_0_50 = 0 - 50 microamps
                CurrentRange.RANGE_0_125 = 0 - 125 microamps
                CurrentRange.RANGE_0_250 = 0 - 250 microamps
                CurrentRange.RANGE_0_negative_24 = 0 - -24 microamps
                CurrentRange.RANGE_0_negative_48 = 0 - -48 microamps
                CurrentRange.RANGE_0_negative_120 = 0 - -120 microamps
                CurrentRange.RANGE_0_negative_240 = 0 - -240 microamps
                CurrentRange.RANGE_negative_25_25 = -25 - 25 microamps
                CurrentRange.RANGE_negative_50_50 = -50 - 50 microamps
                CurrentRange.RANGE_negative_125_125 = -125 - 125 microamps
                CurrentRange.RANGE_negative_250_250 = -250 - 250 microamps
        """
        # Set the current range for each dac, defaulting to 0010 which equates to 0-250 μA
        self.set_dac_current_range(current_range, 0)
        self.set_dac_current_range(current_range, 1)
        self.set_dac_current_range(current_range, 2)
        self.set_dac_current_range(current_range, 3)
        # Set each dac into current output mode
        self.put_dac_into_current_mode(0, DAC63004.VoltagePowerDownMode.POW_DOWN_HI_Z)
        self.put_dac_into_current_mode(1, DAC63004.VoltagePowerDownMode.POW_DOWN_HI_Z)
        self.put_dac_into_current_mode(2, DAC63004.VoltagePowerDownMode.POW_DOWN_HI_Z)
        self.put_dac_into_current_mode(3, DAC63004.VoltagePowerDownMode.POW_DOWN_HI_Z)


if __name__ == "__main__":
    u34 = DAC63004(0x48, 3)
    u34.read_all_registers()
    # u34.set_all_dacs_to_voltage()
    u34.set_all_dacs_to_current(DAC63004.CurrentRange.RANGE_0_250)
    current = int(input("Enter current "))
    u34.set_dac_current_micro_amps(0, current)
    u34.set_dac_current_micro_amps(1, current)
    u34.set_dac_current_micro_amps(2, current)
    u34.set_dac_current_micro_amps(3, current)
