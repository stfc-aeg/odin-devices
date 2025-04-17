"""
Driver for supporting the Microchip MIC284 Two-Zone Thermal Supervisor.

This device measures 8-bit temperature readings from two sources:
    1. Internal
    2. External

It uses an I2C interface.

As well as provinding temperature readings, the device also provides an overtemperature alarm
that can be read out or registered using an output pin. The limit for this overtemperature alarm
is programmable.

Joseph Nobes, Grad Embedded Sys Eng, STFC Detector Systems Software Group
"""
import logging
from odin_devices.i2c_device import I2CDevice
try:
    _GPIOD_SUPPORTED = True
    import gpiod
except ModuleNotFoundException:
    _GPIOD_SUPPORTED = False

class MIC284():
    """
    Register Addresses:
    """
    _REG_TEMP0 = 0x00       # Local Temperature
    _REG_CONFIG = 0x01      # Configuration Register
    _REG_T_HYST0 = 0x02     # Local Hysteresis
    _REG_T_SET0 = 0x03      # Local Temperature Setpoint
    _REG_TEMP1 = 0x10       # Remote Temperature
    _REG_T_HYST1 = 0x12     # Remote Hysteresis
    _REG_T_SET1 = 0x13      # Remote Temperature Setpoint
    _REG_nCRIT1 = 0x22      # Overtemperature Hysteresis
    _REG_CRIT1 = 0x23       # Overtemperature Temperature Setpoint

    def __init__(self, address, busnum, debug=False, int_pin=None):

        # Check if the supplied pin is valid and configured as an input
        self._int_pin = None
        if int_pin is not None and _GPIOD_SUPPORTED:
            if int_pin.direction is not gpiod.Line.DIRECTION_INPUT:
                raise Exception('Supplied GPIO line for interrupt pin is not configured as an input pin')
            self._int_pin = int_pin

        self._device = I2CDevice(address=address, busnum=busnum, debug=debug)
        self._logger = logging.getLogger('MIC284@{}@{}'.format(hex(address), busnum))

        # Some configuration values are cached in the driver, but should be read the first
        # time in case the device is not in the power-on-reset default state.
        self._shutdown_cached = None
        self._fault_queue_depth_cached = None
        self._interrupt_mode_cached = None

        self._logger.info('Init MIC284 Thermal Supervisor Complete')

    @staticmethod
    def part_to_address(partno, a0):
        """
        Work out the anticipated I2C address of the device based on its part number
        (ending) and the address pins.

        :param partno:      The last digit of the part number N, in pattern MIC284-N
        :param a0:          The value of the address pin, 1 for high, 0 for low
        :return address:    The I2C address at which the device should be found
        """
        return (0b1001000 | partno << 1 | a0)

    @staticmethod
    def _convert_to_temperature(reg_byte):
        """
        Convert the byte read back from the device to a temperature.
        The value is in 2's complement.
        """
        return ((reg_byte & 0b10000000) * -1) + (0b1111111 & reg_byte)

    @staticmethod
    def _convert_from_temperature(temperature):
        """
        Convert a supplied numerical limit into a byte value that can be written into
        the limit registers.
        """
        # Check limits
        if temperature < -128 or temperature > 127:
            raise Exception('Temperature supplied must be between -128 to 127 DegC')

        # Conversion to 2's complement 8-bit
        if temperature >= 0:
            return temperature
        else:
            return 0b10000000 | (temperature + 128)

    def read_temperature_internal(self):
        if self.get_shutdown():
            raise Exception('Cannot read, device in shutdown')

        return MIC284._convert_to_temperature(self.read_register(MIC284._REG_TEMP0))

    def read_temperature_external(self):
        if self.get_shutdown():
            raise Exception('Cannot read, device in shutdown')

        return MIC284._convert_to_temperature(self.read_register(MIC284._REG_TEMP1))

    def set_interrupt_mode(self, interrupt_mode):
        """
        Set the interrupt/comparator mode for the /INT pin and S0/S1 flags:

            - In interrupt mode, S0/1 event flags will remain active until any register
                is read. This also goes for the interrupt pin, which will remain active
                until the same event.

                In addition:
                    - If the event was triggered by an overtemperature condition, the
                        temperature must be brought below the lower bound again (T_HYSTx)
                        before it will be re-asserted, even if the temperature remains
                        over the upper threshold.
                    - The opposite is true for an undertemperature condition.
            - In comparator mode (default), S0/1 event flags will remain while the
                triggering conditions are true. The interrupt pin will be asserted while
                the temperature is out of range.

        This setting does not affect the /CRIT pin or CRIT1 flag.

        :param interrupt_mode:      Boolean, set True to enable interrupt mode
        """
        if self._interrupt_mode_cached is not interrupt_mode:
            reg_old = self.read_register(MIC284._REG_CONFIG)
            reg_new = (reg_old & 0b11111101) | (0b10 if interrupt_mode else 0b00)
            self._device.write8(MIC284._REG_CONFIG, reg_new)

    def get_interrupt_mode(self):
        if self._interrupt_mode_cached is None:
            config = self.read_register(MIC284._REG_CONFIG)
            self._interrupt_mode_cached = bool((config & 0b10) > 0)

        return self._interrupt_mode_cached

    def set_throsholds_internal(self, setpoint=None, hysteresis=None):
        """
        Set event flag / interrupt threshold temperatures for the internal temperature
        sensor. Either setpoint or hysteresis temperature can be supplied, or both.

        :param setpoint:    If the temperature rises above this point, high temperature
                            fault will be registered. Default level 81C
        :param hysteresis:  If the temperature falls below this point, a low temperature
                            fault will be registered. Default level 76C
        """
        self._device.write8(MIC284._REG_T_SET0, MIC284._convert_from_temperature(setpoint))
        self._device.write8(MIC284._REG_T_HYST0, MIC284._convert_from_temperature(hysteresis))
        self._logger.info(
            'Set internal sensor thresholds to setpoint {}C, hysteresis {}C'.format(
                setpoint, hysteresis))

    def get_thresholds_internal(self):
        setpoint_degrees = MIC284._convert_to_temperature(self.read_register(MIC284._REG_T_SET0))
        hysteresis_degrees = MIC284._convert_to_temperature(self.read_register(MIC284._REG_T_HYST0))
        return (setpoint_degrees, hysteresis_degrees)

    def set_thresholds_external(self, setpoint=None, hysteresis=None):
        """
        Set event flag / interrupt threshold temperatures for the external temperature
        sensor. Either setpoint or hysteresis temperature can be supplied, or both.

        :param setpoint:    If the temperature rises above this point, high temperature
                            fault will be registered. Default level 97C
        :param hysteresis:  If the temperature falls below this point, a low temperature
                            fault will be registered. Default level 92C
        """
        self._device.write8(MIC284._REG_T_SET1, MIC284._convert_from_temperature(setpoint))
        self._device.write8(MIC284._REG_T_HYST1, MIC284._convert_from_temperature(hysteresis))
        self._logger.info(
            'Set remote sensor thresholds to setpoint {}C, hysteresis {}C'.format(
                setpoint, hysteresis))

    def get_thresholds_external(self):
        setpoint_degrees = MIC284._convert_to_temperature(self.read_register(MIC284._REG_T_SET1))
        hysteresis_degrees = MIC284._convert_to_temperature(self.read_register(MIC284._REG_T_HYST1))
        return (setpoint_degrees, hysteresis_degrees)

    def set_thresholds_external_critical(self, setpoint=None, hysteresis=None):
        """
        Set critical event flag / interrupt threshold temperatures for the external temperature
        sensor. Either setpoint or hysteresis temperature can be supplied, or both. This behaves
        similarly to the normal interrupt, except that it operates the /CRIT line instead of the
        /INT line, and has a separate flag.

        :param setpoint:    If the temperature rises above this point, high temperature
                            fault will be registered. Default level 97C
        :param hysteresis:  If the temperature falls below this point, a low temperature
                            fault will be registered. Default level 92C
        """
        self._device.write8(MIC284._REG_CRIT1, MIC284._convert_from_temperature(setpoint))
        self._device.write8(MIC284._REG_nCRIT1, MIC284._convert_from_temperature(hysteresis))
        self._logger.info(
            'Set critical remote sensor thresholds to setpoint {}C, hysteresis {}C'.format(
                setpoint, hysteresis))

    def get_thresholds_external_critical(self):
        setpoint_degrees = MIC284._convert_to_temperature(self.read_register(MIC284._REG_CRIT1))
        hysteresis_degrees = MIC284._convert_to_temperature(self.read_register(MIC284._REG_nCRIT1))
        return (setpoint_degrees, hysteresis_degrees)

    def enter_shutdown(self):
        """
        Enter the shutdown mode. Interrupts will not trigger, and no conversions take place.
        All registers are still accessible.
        """
        reg_old = self.read_register(MIC284._REG_CONFIG)
        reg_new = (reg_old & 0b11111110) | 0b1
        self._device.write8(MIC284._REG_CONFIG, reg_new)

        # Remember that the device is in reset mode, don't bother readings etc
        self._shutdown_cached = True

    def exit_shutdown(self):
        """
        Exit shutdown mode.
        """
        reg_old = self.read_register(MIC284._REG_CONFIG)
        reg_new = (reg_old & 0b11111110)
        self._device.write8(MIC284._REG_CONFIG, reg_new)

        self._shutdown_cached = False

    def get_shutdown(self):
        """
        Get the current shutdown state. This is cached in the driver when read or written to.

        :return bool:   True if device is in shutdown mode
        """
        if self._shutdown_cached is None:
            config = self.read_register(MIC284._REG_CONFIG)
            self._shutdown_cached = bool((config & 0b1) > 0)

        return self._shutdown_cached

    def set_fault_queue_depth(self, N):
        """
        When triggering fault states / interrupts, the MIC284 will wait for N
        cases of the condition being true before triggering the error state.
        Default depth is 1.

        :param N:   Number of conversions matching condition required
        """
        if N not in [0b00, 0b01, 0b10, 0b11]:
            raise Exception('N must be a 2-bit value')

        reg_old = self.read_register(MIC284._REG_CONFIG)
        reg_new = reg_old & 0b11100111 | (N << 3)
        self._device.write8(MIC284._REG_CONFIG, reg_new)

        self._logger.debug(
            'Set fault queue depth to {} concurrent conversions matching conditions'.format(N)
        )

    def get_fault_queue_depth(self):
        """
        Get the current fault queue depth, cached in driver. See above.

        :return N:  Number of conversions matching condition required
        """
        if self._fault_queue_depth_cached is None:
            config = self.read_register(MIC284._REG_CONFIG)
            self._fault_queue_depth_cached = (config >> 3) & 0b11

        return self._fault_queue_depth_cached

    def read_register(self, address):

        # First read the config register, as this may contain interrupt flags that would be
        # otherwise cleared by reading any other register.
        config = self._device.readU8(MIC284._REG_CONFIG)

        # Process the config register for interrupts, and report any in the logs
        status_dict = MIC284._decode_event_status(config)
        self._status_cached = status_dict
        for interrupt in status_dict.keys():
            if status_dict[interrupt]['triggered']:
                self._logger.warning(status_dict[interrupt]['info'])

        # If the register to read is the config register, simply return it. Otherwise, 
        # read the desired address.
        if address == MIC284._REG_CONFIG:
            return config
        else:
            return self._device.readU8(address)

    def get_event_status(self):
        if self.get_shutdown():
            raise Exception('Event interrupts disabled, device in shutdown')

        # Trigger an event status update with a config read
        self.read_register(MIC284._REG_CONFIG)

        # Return the updated cached status
        return self._status_cached

    @staticmethod
    def _decode_event_status(config_reg_val):
        """
        Get status information from the fault bits.
        Note that this will clear any event if the device is in interrupt mode.
        """

        # Read the current status of the flags
        s0 = bool((config_reg_val & 0b10000000) > 0)
        s1 = bool((config_reg_val & 0b01000000) > 0)
        crit1 = bool((config_reg_val & 0b00100000) > 0)

        status_dict = {
            # Either local temp > T_SET0 or local temp < T_HYST0
            'local_interrupt': {
                'triggered': s0,
                'info': 'local temperature interrupt {}'.format('triggered' if s0 else 'clear')
            },
            'remote_interrupt': {
                'triggered': s1,
                'info': 'remote temperature interrupt {}'.format('triggered' if s1 else 'clear')
            },
            'remote_overtemp': {
                'triggered': crit1,
                'info': 'remote temperature overtemperature {}'.format('triggered' if crit1 else 'clear')
            },
            'diode_fault': {
                'triggered': (s1 and crit1),
                'info': 'remote diode fault likely; both s1 and crit1 triggered'
            },
        }

        return status_dict
