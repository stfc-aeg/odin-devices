"""
Analog AD5259: 256-position I2C Digital Potentiometer

The AD5259 is a digital potentiometer with 256 RDAC wiper positions between its A/B terminals.
If is available in several variants with diferent R_AB total impedances ranging from 5k-100k.
Wiper settings are stored in non-volatile memory.

This driver allows for device operation with various amounts of provided information (at device
instantiation or added later through access functions / function parameters). With no information
besides device address, the wiper count can be set, and the wiper can be set to a ratio (using
the 'simple', less-accurate version of the function).

If the voltages at terminals A and B are known (V_A, V_B), setting a voltage at terminal W is
possible.

If the total resistance between terminals A and B (R_AB) is supplied, the functions for setting/
getting a resistance between AW and BW become available. In addition, the functions for setting/
getting voltages/ratio in potentionmeter mode will be more accurate, as it becomes possible to
take into account the ratio between internal resistance and the parasitic wiper resistance R_W.
The user will be warned of this if they instantiate the device without R_AB.

Joseph Nobes, Embedded Sys Eng, STFC Detector Systems Software Group
"""

from odin_devices.i2c_device import I2CDevice, I2CException
import logging

class AD5259(I2CDevice):
    # I2C Instructions
    _INS_RDAC = (0b000 << 5)    # Write / read RDAC (wiper) count
    _INS_EEPROM = (0b001 << 5)  # Write / read EEPROM (stored count)
    _INS_WP = (0b010 << 5)      # Write protection
    _INS_NOP = (0b100 << 5)     # No Operation / enter idle
    _INS_STORE_EEPROM_TO_RDAC = (0b101 << 5)    # Restore EEPROM value to RDAC count
    _INS_STORE_RDAC_TO_EEPROM = (0b110 << 5)    # Save RDAC value to EEPROM

    @staticmethod
    def ad_pins_to_address(AD0, AD1):
        """
        Convert known pin values to an I2C address

        :param AD0: AD0 pin value, boolean
        :param AD1: AD1 pin value, boolean
        :return:    I2C address device expected at
        """
        AD0_val = (0b10011 if AD0 else 0b00110) << 2
        AD1_val = (1 if AD1 else 0) << 1
        return (0b0 | AD1_val | AD0_val)

    def __init__(self, address, busnum=None, resistance_AB_kohms=None, voltage_A=None, voltage_B=None):
        """
        Initialise the device

        :param address:                 I2C address of device. Use AD5259.ad_pins_to_address() to get from pins.
        :param busnum:                  (optional) I2C bus number
        :param resistance_AB_kohms:     (optional) Device total resistance between A->B. If not supplied, setting
                                        proportions and voltages will be less accurate, and setting resistances
                                        between A/B and the wiper will be unavailable. Supplied in kiloohms.
        :param voltage_A:               (optional) Voltage at terminal A, used when setting wiper voltages.
        :param voltage_B:               (optional) Voltage at terminal B, used when setting wiper voltages.
        """

        # Set up the logger
        #TODO
        self._logger = logging.getLogger('odin_devices.ad5259@i2c:{}:0x{}'.format(busnum,hex(address)))

        # Set up the I2CDevice
        super(AD5259, self).__init__(address=address, busnum=busnum)

        self._V_A = None
        self._V_B = None
        self._R_AB = None   # in ohms
        self._R_W = 75      # Wiper parasitic resistance, typical

        # Warn the user if they have not supplied the total resistance
        if resistance_AB_kohms:
            self.set_resistance_AB_kohms(resistance_AB_kohms)
        else:
            self._logger.warning("""
            A-B terminal resistance (R_AB) has not been supplied: resistance setting will not be available,
            and wiper proportion (including voltage) getting / setting will have reduced accuracy.
            """)

        # Both terminal voltages must be supplied to be useful, so warn if either not supplied
        if voltage_A:
            self.set_voltage_A(voltage_A)
        if voltage_B:
            self.set_voltage_B(voltage_B)
        if voltage_A is None or voltage_B is None:
            self._logger.warning("""
            Either terminal A voltage (V_A), terminal B voltage (V_B), or both, have not been supplied. This
            means voltage setting / getting functions will not be available.
            """)

    def set_resistance_AB_kohms(self, resistance_AB_kohms):
        """
        Set the AB total resistance. This is a property of the device and is not adjustable.
        Available devices: 5k, 10k, 50k, 100k
        :param resistance_AB_kohms:  Device AB resistance in kiloohms
        """
        if resistance_AB_kohms in [5, 10, 50, 100]:
            # Store in ohms to make calculations easier
            self._R_AB = resistance_AB_kohms * 1000
            self._logger.debug('Set A->B resistance (R_AB) to {}kohms'.format(resistance_AB_kohms))
        else:
            raise Exception('Invalid A->B resistance value ({}kohms), valid values: 5, 10, 50, 100'.format(resistance_AB_kohms))

    def set_voltage_A(self, voltage_A):
        """
        Set the terminal A voltage, known by the user, for use in calculations
        :param voltage_A:     Terminal A voltage (float)
        """
        self._V_A = float(voltage_A)
        self._logger.debug('Set terminal A voltage (V_A) to {}v'.format(voltage_A))

    def set_voltage_B(self, voltage_B):
        """
        Set the terminal B voltage, known by the user, for use in calculations
        :param V_B:     Terminal B voltage (float)
        """
        self._V_B = float(voltage_B)
        self._logger.debug('Set terminal B voltage (V_B) to {}v'.format(voltage_B))

    def set_wiper_count(self, count):
        count = int(count) & 0xFF
        self.write8(self._INS_RDAC, count)
        self._logger.debug('Set wiper count {}/256'.format(count))

    def get_wiper_count(self):
        count = self.readU8(self._INS_RDAC)
        self._logger.debug('Read wiper count: {}/256'.format(count))
        return count

    def read_eeprom(self):
        count = self.readU8(self._INS_EEPROM)
        self._logger.debug('Read EEPROM: {}/256'.format(count))
        return count

    def write_eeprom(self, count):
        count = int(count) & 0xFF
        self.write8(self._INS_EEPROM, count)
        self._logger.debug('Wrote EEPROM: {}/256'.format(count))

    def store_wiper_count(self):
        """
        Store the current wiper setting in the EEPROM.
        """
        self.write8(self._INS_STORE_RDAC_EEPROM, 0)

    def restore_wiper_count(self):
        """
        Restore the stored wiper setting from the EEPROM to RDAC.
        """
        self.write8(self._INS_STORE_EEPROM_RDAC, 0)

    def _get_resistance_terminal_to_wiper(self, terminal_is_A):
        """
        Get the calculated resistance between terminal A or B and the wiper W in ohms.

        This is only possible if R_AB is known.
        :param terminal_is_A:       Set True if using A terminal, false for B
        """

        if not self._R_AB:
            raise Exception('Getting direct resistances is not possible without specifying R_AB')

        # Get the count value
        D = self.get_wiper_count()

        # Calculate the theoretical resistance between terminal and the wiper based on count
        # From datasheet Rheostat section
        if terminal_is_A:
            return (((256 - D) / 256) * self._R_AB) + (2 * self._R_W)
        else:
            return ((D / 256) * self._R_AB) + (2 * self._R_W)

    def _set_resistance_terminal_to_wiper(self, target_resistance_ohms, terminal_is_A):
        """
        Set the resistance between terminal A or B and the wiper W. The closest possible value will
        be chosen, if it is valid.

        This is only possible if R_AB is known.
        :param target_resistance_ohms:  Target resistance that will be set
        :param terminal_is_A:       Set True if using A terminal, false for B
        """

        if not self._R_AB:
            raise Exception('Setting direct resistances is not possible without specifying R_AB')

        # Calculate the theoretical value of D that would give the desired output (float)
        # Reversed from datasheet Rheostat section
        if terminal_is_A:
            D_raw = 256 - ((target_resistance_ohms - (2 * self._R_W)) * (256 / self._R_AB))
        else:
            D_raw = (target_resistance_ohms - (2 * self._R_W)) * (256 / self._R_AB)

        # Check that this value is in range
        if D_raw < 0 or D_raw >= 255.5:
            raise Exception('Invalid R_AW target resistance for {}k potentiometer: {}k'.format(
                self._R_AB / 1000, target_resistance_ohms / 1000))

        # Round to the closest integer value
        D = round(D_raw, 0)

        # Set the count required for the closest possible value
        self.set_wiper_count(D)

        # Report the actual resistance value achieved
        self._logger.debug('Set resistance between terminal {} and the wiper to {}kohms (count {})'.format(
            'A' if terminal_is_A else 'B',
            self._get_resistance_terminal_to_wiper(terminal_is_A),
            D
        ))

    def set_resistance_AW(self, target_resistance_ohms):
        """
        Set the resistance between terminal A and the wiper W. The closest possible value will
        be chosen.

        This is only possible if R_AB is known.

        :param target_resistance_ohms:  Target resistance that will be set
        """
        self._set_resistance_terminal_to_wiper(target_resistance_ohms, terminal_is_A=True)

    def set_resistance_BW(self, target_resistance_ohms):
        """
        Set the resistance between terminal B and the wiper W. The closest possible value will
        be chosen.

        This is only possible if R_AB is known.

        :param target_resistance_ohms:  Target resistance that will be set
        """
        self._set_resistance_terminal_to_wiper(target_resistance_ohms, terminal_is_A=False)

    def get_resistance_AW(self):
        """
        Get the calculated resistance between terminal A or B and the wiper W in ohms.

        This is only possible if R_AB is known.
        """
        return self._get_resistance_terminal_to_wiper(terminal_is_A=True)

    def get_resistance_BW(self):
        """
        Get the calculated resistance between terminal A or B and the wiper W in ohms.

        This is only possible if R_AB is known.
        """
        return self._get_resistance_terminal_to_wiper(terminal_is_A=False)

    def get_wiper_voltage(self, voltage_A=None, voltage_B=None):
        """
        Calculate the voltage that should be on the wiper based on the currently set wiper count.

        This requires knowledge of the voltage at terminals A and B, which must either have been set
        already or be supplied to this function. Supplied arguments will override any stored setting.

        If the A->B total resistance has been supplied, a more accurate result will be achieved, but
        if not, a simpler approximation will be used.

        :param voltage_A:         Optional voltage at terminal A override (float)
        :param voltage_B:         Optional voltage at terminal B override (float)
        """

        # Check that V_A and V_B are available either from params or stored values
        if (voltage_A is None and self._V_A is None) or (voltage_B is None and self._V_B is None):
            raise Exception('Cannot set a wiper voltage without supplying terminal voltages V_A and V_B')
        functional_V_A = voltage_A if voltage_A is not None else self._V_A  # Function overrides, but does not overwrite stored value
        functional_V_B = voltage_B if voltage_B is not None else self._V_B  # Function overrides, but does not overwrite stored value

        # Calculate the voltage that is expected from this wiper setting. If R_AB is available, use the
        # accurate formula that takes account of R_W, otherwise, the simplified one.
        if self._R_AB:
            self._logger.debug('Using accurate formula to calculate wiper voltage')
            voltage = ((self.get_resistance_BW() / self._R_AB) * functional_V_A) + ((self.get_resistance_AW() / self._R_AB) * functional_V_B)
        else:
            self._logger.debug('Using simple formula to calculate wiper voltage')
            D = self.get_wiper_count()
            voltage = ((D / 256) * functional_V_A) + (((256 - D) / 256) * functional_V_B)

        self._logger.debug('Calculated wiper voltage: {}v'.format(voltage))
        return voltage

    def set_wiper_voltage(self, target_v, voltage_A=None, voltage_B=None):
        """
        Set the wiper count to achieve a target voltage.

        This requires knowledge of the voltage at terminals A and B, which must either have been set
        already or be supplied to this function. Supplied arguments will override any stored setting.

        If the A->B total resistance has been supplied, a more accurate result will be achieved, but
        if not, a simpler approximation will be used.

        :param target_v:    The voltage to be achieved, in volts (float)
        :param voltage_A:         Optional voltage at terminal A override (float)
        :param voltage_B:         Optional voltage at terminal B override (float)
        """

        # Check that V_A and V_B are available either from params or stored values
        if (voltage_A is None and self._V_A is None) or (voltage_B is None and self._V_B is None):
            raise Exception('Cannot set a wiper voltage without supplying terminal voltages V_A and V_B')
        functional_V_A = voltage_A if voltage_A is not None else self._V_A  # Function overrides, but does not overwrite stored value
        functional_V_B = voltage_B if voltage_B is not None else self._V_B  # Function overrides, but does not overwrite stored value

        # Check that the voltage is actually between V_A and V_B (note that either can be higher)
        if not ((functional_V_A <= target_v and target_v <= functional_V_B) or (functional_V_B <= target_v and target_v <= functional_V_A)):
            raise Exception('Target voltage {}v is out of bounds of terminal voltages: V_A: {}, V_B: {}'.format(
                target_v, functional_V_A, functional_V_B))

        # Calculate the theoretical wiper count required to achieve the target voltage (float)
        # Uses the accurate formula if R_AB is present, else the simple one that does not take the R_W
        # parasitic impedance of the wiper into account. Re-arranged from datasheet Potentiometer section.
        if self._R_AB:
            self._logger.debug('Using accurate formula to calculate target count for target wiper voltage {}v'.format(target_v))
            # Accurate formula inverse and substituted to be interms of only R_AW
            R_AW_target = ((target_v * self._R_AB) - (functional_V_A * self._R_AB) - (4 * functional_V_A * self._R_W)) / (functional_V_B - functional_V_A)

            # Use the existing function to work out required count from desired terminal A -> wiper impedence
            self.set_resistance_AW(R_AW_target)
        else:
            self._logger.debug('Using simple formula to calculate target count for target wiper voltage {}v'.format(target_v))
            D_target_raw = (target_v - functional_V_B) * (256 / (functional_V_A - functional_V_B))
            D_target = round(D_target_raw, 0)
            self.set_wiper_count(D_target)

        # Print out the back calculated wiper voltage reverse-calculated voltage
        self._logger.debug('Finished setting wiper voltage to {}v, count {}, actual voltage: {}'.format(
            target_v, self.get_wiper_count(), self.get_wiper_voltage(voltage_A=voltage_A, voltage_B=voltage_B)
        ))

    def set_wiper_proportion(self, proportion):
        """
        Set the wiper proportionally with no other information. 0 is at B, 1 is at A.

        :param proportion:  Target proportion, 0-1 (float)
        """

        proportion = float(proportion)
        if proportion < 0 or proportion > 1:
            raise Exception('Invalid proportion, must be between 0 and 1')

        # Max is 255
        self.set_wiper_count(int(proportion * 255))

        self._logger.debug('Setting proportion from terminal A:B of {} (count {})'.format(proportion, self.get_wiper_count()))
