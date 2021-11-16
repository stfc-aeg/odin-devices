from odin_devices.i2c_device import I2CDevice as _I2CDevice
import sys

if sys.version_info[0] == 3:                # pragma: no cover
    from enum import Enum as _Enum, auto as _auto
else:                                       # pragma: no cover
    from aenum import Enum as _Enum, auto as _auto

import logging as _logging
import time as _time

_GPIO_AVAIL = True
try:
    import gpiod
except Exception:
        _GPIO_AVAIL = False
        templogger = _logging.getLogger('odin_devices.pac1921')
        templogger.warning("No support for GPIO, FreeRun mode only")

# The PAC1921 uses a resistance to ground to determine address.
# Note that -1 represents 'open'
_ADDRESS_RESISTANCE_MAPPING = {0:     0b1001100,
                               120:   0b1001101,
                               220:   0b1001110,
                               330:   0b1001111,
                               470:   0b1001000,
                               620:   0b1001001,
                               820:   0b1001010,
                               1000:  0b1001011,
                               1300:  0b0101000,
                               1800:  0b0101001,
                               2200:  0b0101010,
                               3000:  0b0101011,
                               4300:  0b0101100,
                               6800:  0b0101101,
                               12000: 0b0101110,
                               -1:    0b0011000}

# Valid gain settings for DI_GAIN and DV_GAIN and corresponding register values
_Dx_GAIN_ENCODING = {1:   0b000,
                     2:   0b001,
                     4:   0b010,
                     8:   0b011,
                     16:  0b100,
                     32:  0b101,
                     64:  0b110,
                     128: 0b111}

# Number of Samples Setting for Free Run Mode (SMPL)
_SMPL_NUM_SAMPLES_ENCODING = {1:    0b0000, # Default
                              2:    0b0001,
                              4:    0b0010,
                              8:    0b0011,
                              16:   0b0100,
                              32:   0b0101,
                              64:   0b0110,
                              128:  0b0111,
                              256:  0b1000,
                              512:  0b1001,
                              1024: 0b1010,
                              2048: 0b1011} # There are other combinations that evaulate to 2048

# Register Map
_VBUS_RESULT_REG = 0x10     # 16-bits from 0x10 to 0x11
_VSENSE_RESULT_REG = 0x12   # 16-bits from 0x12 to 0x13
_POWER_RESULT_REG = 0x1D    # 16-bits from 0x1D to 0x1E
_OVERFLOW_STATUS_REG = 0x1C # Last 3 MSBs are VSOV, VBOV, VPOV
_SMPL_REG = 0x01            # 4 bits from 7 to 4
_PRODUCT_ID_REG = 0xFD      # Product ID should be 0b01011011
_MANUFACTURER_ID_REG = 0xFE # Manufacturer ID should be 0b01011101

# Default POR values
_DV_GAIN_DEFAULT = 1
_DI_GAIN_DEFAULT = 1
_I_RES_DEFAULT = 11
_V_RES_DEFAULT = 11
_I_POST_FILT_EN_DEFAULT = False
_V_POST_FILT_EN_DEFAULT = False

# Expected Identification Values
_EXPECTED_PRODUCT_ID        = 0b01011011
_EXPECTED_MANUFACTURER_ID   = 0b01011101

class Measurement_Type (_Enum):
    POWER = _auto()
    VBUS = _auto()
    CURRENT = _auto()   # Measured via Vsense over Rsense

class _Integration_Mode (_Enum):
    FreeRun = _auto()
    PinControlled = _auto()


class PAC1921(object):
    """
    Class to enable the driving of the PAC1921 voltate/current/power monitor over I2C. The device
    can be used in either free-run or pin-controlled mode. If the latter is used, a gpiod pin must
    be supplied for nRead_int_pin (potentially supplied from odin_devices.gpio_bus).

    As a bare minimum, init the device and call config_<method>_integration_mode() to set up either
    pin-control of free-run. At this point, other settings can be configured (gain, filtering etc)
    or calling read() will return the result of the chosen measurement.
    """
    def __init__(self, i2c_address=None, address_resistance=None, name='PAC1921', nRead_int_pin=None, r_sense=None, measurement_type=None):
        """
        Create a PAC1921 device instance with an associated address. If the address is unknown but
        but the address resistance is, supply this instead (the associated I2C address will be
        derived). If pin-control is to be used, a nRead_int_pin gpiod pin will be needed.

        :param i2c_address:         Known I2C address (this or address_resistance required)
        :param address_resistance:  ADDR_SEL resistance to gnd (this or i2c_address required)
        :param name:                Friendly name of device. Useful if using multiple devices
        :param nRead_int_pin:       gpiod line for pin control (required for pin-control only)
        :param r_sense:             Rsense resistance in ohms (required for POWER, CURRENT)
        :param measurement_type:    Measurement_Type enum for POWER, CURRENT, or VBUS
        """

        # If an i2c address is not present, work one out from resistance, if supplied
        if i2c_address is None:
            if address_resistance is not None:
                i2c_address = PAC1921._get_address_from_resistance(address_resistance)
            else:
                raise ValueError(
                        "Either an I2C address or address resistance value must be supplied")

        # Init the I2C Device
        self._i2c_address = i2c_address
        self._i2c_device = _I2CDevice(self._i2c_address, debug=False)
        self._i2c_device.enable_exceptions();

        # Check the device is present on the I2C bus
        self._check_prodid_manufacturer()

        # Init logger
        self._name = name        # Name is used because there may be multiple monitors
        self._logger = _logging.getLogger('odin_devices.pac1921.' +
                                         self._name + '@' +
                                         hex(self._i2c_address))

        self._set_nRead_int_pin(nRead_int_pin)

        self._r_sense = r_sense

        # Check that the measurement type is valid
        self._measurement_type = None
        if measurement_type is not None:
            if type(measurement_type) is Measurement_Type:
                self.set_measurement_type(measurement_type)
            else:
                raise TypeError("Invalid measurement type given")

        # Store the POR values of the settings registers
        self._integration_mode = _Integration_Mode.PinControlled    # pin-ctrl default POR
        self._dv_gain = _DV_GAIN_DEFAULT
        self._di_gain = _DI_GAIN_DEFAULT
        self._i_resolution = _I_RES_DEFAULT
        self._v_resolution = _V_RES_DEFAULT
        self._v_post_filter_en = _V_POST_FILT_EN_DEFAULT
        self._i_post_filter_en = _I_POST_FILT_EN_DEFAULT

        # Place in read state so that settings can be changed before integration
        self._nRead_int_state = False
        if nRead_int_pin is not None:
            self._pin_set_read()
        else:
            self._register_set_read()

        # Force config registers update to default values (there is no way to reset the device)
        self._write_register_bitfield(7, 8, 0x00, 0)
        self._write_register_bitfield(7, 8, 0x01, 12)
        self._write_register_bitfield(7, 8, 0x02, 0)
        self._force_config_update()

        # Init progress tracking vars
        self._pincontrol_config_complete = False
        self._freerun_config_complete = False
        self._integration_time_ms = None        # Will be set in pin-control config if used

        self._logger.info('Device init complete')

    def _check_prodid_manufacturer(self):
        """
        Verifies that a PAC1921 is present at the given I2C address by reading the product and
        manufacturer ID registers. Will raise an Excption if either is not as expected.
        """
        try:
            product_id = self._i2c_device.readU8(_PRODUCT_ID_REG) & 0xFF
            manufacturer_id = self._i2c_device.readU8(_MANUFACTURER_ID_REG) & 0xFF
        except _I2CDevice.ERROR:
            raise

        if product_id != 0b01011011:
            raise Exception(
                    "Product ID {} was not valid, expected {}".format(hex(product_id),
                        hex(_EXPECTED_PRODUCT_ID)))
        if manufacturer_id != 0b01011101:
            raise Exception(
                    "Manufacturer ID {} was not valid, expected {}".format(hex(manufacturer_id),
                        hex(_EXPECTED_MANUFACTURER_ID)))

    def _pin_set_integration(self):
        """
        Puts the device in integration mode using the nRead_int_pin. Ensures that the pin control
        is not being overridden by the 'register override' for controlling mode.
        """
        if self._nRead_int_pin is None:
            raise Exception("Cannot drive pin, no pin was supplied")

        # Disable register read/int control
        self._write_register_bitfield(1, 1, 0x01, 0b0)

        # Set read mode
        self._nRead_int_pin.set_value(1)

        self._nRead_int_state = True

    def _pin_set_read(self):
        """
        Puts the device in read mode using the nRead_int_pin. Ensures that the pin control is not
        being overridden by the 'register override' for controlling mode.
        """
        if self._nRead_int_pin is None:
            raise Exception("Cannot drive pin, no pin was supplied")

        # Disable register read/int control
        self._write_register_bitfield(1, 1, 0x01, 0b0)

        # Set read mode
        self._nRead_int_pin.set_value(0)

        self._nRead_int_state = False

    def _register_set_integration(self):
        """
        Puts the device in integration mode using the register-control override. This means it can
        be done without an nRead_int_pin.
        """
        # Enable register read/int control
        self._write_register_bitfield(1, 1, 0x01, 0b1)

        # Set integration mode
        self._write_register_bitfield(0, 1, 0x01, 0b1)

        self._nRead_int_state = True

    def _register_set_read(self):
        """
        Puts the device in read mode using the register-control override. This means it can be done
        without an nRead_int_pin.
        """
        # Enable register read/int control
        self._write_register_bitfield(1, 1, 0x01, 0b1)

        # Set read mode
        self._write_register_bitfield(0, 1, 0x01, 0b0)

        self._nRead_int_state = False

    def _trigger_pin_integration(self, integration_time_ms):
        """
        Hold the device in integration mode for the period of time specified. This is used for
        integration in pin-controlled mode only.
        """
        # Place the device initially in read mode
        self._pin_set_read()
        _time.sleep(1)

        # Set the pin to integrate mode
        self._pin_set_integration()

        # Wait for time integration time to be reached
        _time.sleep(integration_time_ms / 1000.0)

        # Set the pin to read mode
        self._pin_set_read()

    @staticmethod
    def _get_address_from_resistance(address_resistance):
        """
        Derive the I2C address associated with a resistance between ADDR_SEL pin and GND.

        :param address_resistance:      Resistance between ADDR_SEL and GND in ohms
        """
        if address_resistance in _ADDRESS_RESISTANCE_MAPPING.keys():
            return _ADDRESS_RESISTANCE_MAPPING[address_resistance]
        else:
            raise ValueError("Invalid address resistance supplied")

    def _write_register_bitfield(self, start_bit, bit_width, register, new_value):
        """
        Write a value to a specified field of bits in a register. Limited to fields that fit within
        one 8-bit register.

        :param start_bit:       Position of first bit in field, numbered: 76543210
        :param bit_width:       Width of the field in bits
        :param register:        Register to which the field is written. 8-bit address.
        :param new_value:       Value to write. If it is too large to fit in specified field, an
                                Exception will be raised.
        """
        # Check the start bit is valid
        if start_bit > 7 or start_bit < 0:
            raise ValueError("start_bit must be in range 0-7")

        # Check bit_width is valid
        if bit_width < 1 or bit_width > (start_bit + 1):
            raise ValueError("bit_width must be in range 1-(start_bit+1)")

        # Check the value is valid for the bit width
        if new_value > (pow(2, bit_width) - 1):
            raise ValueError("Value {} does bit fit in {} bits".format(new_value, bit_width))

        # Read original value from register
        old_value = self._i2c_device.readU8(register)

        # Mask off original bits
        mask_top = (0xFF << (start_bit + 1)) & 0xFF
        mask_bottom = pow(2, ((start_bit + 1) - bit_width)) - 1
        mask_keep = (mask_top | mask_bottom) & 0xFF
        masked_old_value = old_value & mask_keep

        # Replace masked off bits with new slice
        new_reg_value = masked_old_value | (new_value << ((start_bit + 1) - bit_width)) & 0xFF

        # Write newly formed value to the register
        self._i2c_device.write8(register, new_reg_value)

    def _read_decode_output(self):
        """
        Read whatever result is in the result register for the selected measurement at this time.
        This does not mean the measurement has actually taken place (integration should be called
        first). Also checks for overflows reported by the device, and raises warnings if any are
        found.

        VBUS reports the result in volts, CURRENT in amps and POWER in watts.
        """
        # Check for overflows
        overflow_result = self._i2c_device.readU8(_OVERFLOW_STATUS_REG)
        if overflow_result & 0b100: # VSOV
            self._logger.warning("Overflow Detected! DI_GAIN may be too high.")
        if overflow_result & 0b010: # VBOV
            self._logger.warning("Overflow Detected! DV_GAIN may be too high.")
        if overflow_result & 0b001: # VPOV
            self._logger.warning("Overflow Detected! DI_GAIN or DV_GAIN may be too high.")

        # Decode the relevant measurement type
        if self._measurement_type is Measurement_Type.VBUS:
            # Read the raw register
            vbus_high = self._i2c_device.readU8(_VBUS_RESULT_REG)
            vbus_low = self._i2c_device.readU8(_VBUS_RESULT_REG+1)
            vbus_raw = ((vbus_high << 8) + vbus_low)
            self._logger.debug('raw result : {}'.format(vbus_raw))

            # Decode the Vbus value
            vbus_lsb_volts = (32.0 / self._dv_gain) / float(1023 * pow(2,6))
            self._logger.debug('volts per lsb: {}'.format(vbus_lsb_volts))
            vbus_result = vbus_lsb_volts * vbus_raw

            return vbus_result

        elif self._measurement_type is Measurement_Type.CURRENT:
            # Read the raw register
            vsense_high = self._i2c_device.readU8(_VSENSE_RESULT_REG)
            vsense_low = self._i2c_device.readU8(_VSENSE_RESULT_REG+1)
            vsense_raw = ((vsense_high << 8) + vsense_low)
            self._logger.debug('raw result : {}'.format(vsense_raw))

            # Decode the Vsense value
            vsense_lsb_amps = (0.1 / (self._r_sense * self._di_gain)) / float(1023 * pow(2,6))
            self._logger.debug('amps per lsb: {}'.format(vsense_lsb_amps))
            vsense_result = vsense_lsb_amps * vsense_raw

            return vsense_result

        elif self._measurement_type is Measurement_Type.POWER:
            # Read the raw register
            power_high = self._i2c_device.readU8(_POWER_RESULT_REG)
            power_low = self._i2c_device.readU8(_POWER_RESULT_REG+1)
            power_raw = ((power_high << 8) + power_low)
            self._logger.debug('raw result : {}'.format(power_raw))

            # Decode the Power value
            ipart = 0.1 / (self._r_sense * self._di_gain)
            vpart = 32.0 / self._dv_gain
            power_lsb_watts = (ipart * vpart) / float(1023 * pow(2,6))
            self._logger.debug('watts per lsb: {}'.format(power_lsb_watts))
            power_result = power_lsb_watts * power_raw

        else:
            raise ValueError("Measurement Type has not been set")

            return power_result

    def _has_nRead_int_pin(self):
        return (self._nRead_int_pin is not None)

    def _get_nRead_int_pin(self):
        return self._nRead_int_pin

    def _set_nRead_int_pin(self, nRead_int_pin):
        """
        Sets the internal nRead_int_pin for the device, and also checks that it is of the correct
        type. The pin is assumed claimed by the calling program.
        """
        if nRead_int_pin is not None:
            if not isinstance(nRead_int_pin, type(gpiod.Line)):
                raise TypeError("nRead_int_pin should be of type gpiod.Line, "
                                "either from gpiod directly or the odin_devices gpio_bus driver")

        self._nRead_int_pin = nRead_int_pin     # Still assigns if None

    def pin_control_enabled(self):
        """
        Returns true if the integration mode is pin-controlled. This DOES NOT confirm that pin-
        control has been configured yet.
        """
        return (self._integration_mode == _Integration_Mode.PinControlled)

    def get_name(self):
        """
        Return the friendly name of the device set on instantiation.
        """
        return self._name

    def get_address(self):
        """
        Return the I2C address of the device.
        """
        return self._i2c_device.address

    def config_resolution_filtering(self, adc_resolution=None, post_filter_en=None):
        """
        Configure the ADC resolution and post_filter used for measuring the VBUS and VSENSE values.
        This is optional additional configuration before integration.

        The ADC resolution does not affect the number of bits of the reported results, but does mean
        a more accurate result. Post-filtering improvs signal quality, but increases conversion time
        for a given number of samples by 50%.

        Currently both VSense and VBus settings are set the same.

        :param adc_resolution:      Number of bits of measurement resolution, either 11 or 14
        :param post_filter_en:      Enable the post filters, True or False
        """
        # Set the same resolution for both I and V (and therefore P)
        if adc_resolution is not None:
            # Check resolution is valid, and calculate bit field value
            if adc_resolution not in [11, 14]:
                raise ValueError("ADC resolution invalid, choose 11 or 14 bits")

            # Calculate bit field value
            if adc_resolution == 11:
                adc_resolution_raw = 0b1
            else:
                adc_resolution_raw = 0b0

            # Set in device
            self._write_register_bitfield(7, 1, 0x00, adc_resolution_raw)     # I Resolution
            self._write_register_bitfield(6, 1, 0x00, adc_resolution_raw)     # V Resolution

            # Set in driver
            self._i_resolution = adc_resolution
            self._v_resolution = adc_resolution

            self._logger.info(
                    'ADC resolution config as I: {} bits, V: {} bits'.format(self._i_resolution,
                                                                             self._v_resolution))

        # Set the same post filter state for I and V (and therefore P)
        if post_filter_en is not None:
            # Check input is boolean
            if type(post_filter_en) is not bool:
                raise ValueError(
                        "Post Filter EN should be boolean, not {}".format(type(post_filter_en)))

            # Calculate bit field value
            if post_filter_en:
                post_filter_en_raw = 0b1
            else:
                post_filter_en_raw = 0b0

            # Set in device
            self._write_register_bitfield(3, 1, 0x01, post_filter_en_raw)   # Vsense post filter
            self._write_register_bitfield(2, 1, 0x01, post_filter_en_raw)   # Vbus post filter

            # Set in driver
            self._i_post_filter_en = post_filter_en
            self._v_post_filter_en = post_filter_en

            self._logger.info(
                    'Post Filter EN set to I: {}, V: {}'.format(self._i_post_filter_en,
                                                                self._v_post_filter_en))

        # If in integration mode, need to enter read mode so that settings will take effect before
        # the next reading
        if self._nRead_int_state:
            self._register_set_read()
            _time.sleep(0.001)
            self._register_set_integration()

    def config_gain(self, di_gain=None, dv_gain=None):
        """
        Configure the gain multiplier independendly for VBus and VSense. Optional setting to be set
        before integration is started.

        This scales the input range by dividing from 32v for VBus and 100mV for vSense. The
        calculation adjustment will be handled automatically by the reading decode function, so set
        this based on anticipated input range for a more precise reading.

        :param di_gain:     VSense division factor. Can be 1(default), 2, 4, 8, 16, 32, 64 or 128
        :param dv_gain:     Vbus division factor. Can be 1(default), 2, 4, 8, 16, 32
        """
        # Set the DI gain if supplied
        if di_gain is not None:
            # Check that gain is valid
            if di_gain not in _Dx_GAIN_ENCODING.keys():
                raise ValueError(
                        "DI Gain not valid. Choose from {}".format(_Dx_GAIN_ENCODING.keys()))

            # Calculate bit field value
            di_gain_raw = _Dx_GAIN_ENCODING[di_gain]

            # Set in device
            self._write_register_bitfield(5, 3, 0x00, di_gain_raw)

            # Set in driver
            self._di_gain = di_gain

            self._logger.info(
                    'DI gain set to {} (encoded as 0x{})'.format(self._di_gain, di_gain_raw))

        # Set the DV gain if supplied
        if dv_gain is not None:
            # Check that gain is valid
            Dv_alllowed_values = [ g for g in _Dx_GAIN_ENCODING.keys() if g <= 32]
            if dv_gain not in Dv_alllowed_values:
                raise ValueError(
                        "DV Gain not valid. Choose from {}".format(Dv_alllowed_values))

            # Calculate bit field value
            dv_gain_raw = _Dx_GAIN_ENCODING[dv_gain]

            # Set in device
            self._write_register_bitfield(2, 3, 0x00, dv_gain_raw)

            # Set in driver
            self._dv_gain = dv_gain

            self._logger.info(
                    'DV gain set to {} (encoded as 0x{})'.format(self._dv_gain, dv_gain_raw))

        # If in integration mode, need to enter read mode so that settings will take effect before
        # the next reading
        if self._nRead_int_state:
            self._register_set_read()
            _time.sleep(0.001)
            self._register_set_integration()

    def _force_config_update(self):
        """
        Force the settings stored in the driver to be written to the device. This is used on init
        because there is no way to reset the device, so it will ensure 'known' settings are valid.
        """
        self.config_gain(di_gain = self._di_gain, dv_gain = self._dv_gain)
        self.config_resolution_filtering(adc_resolution=self._i_resolution,
                                         post_filter_en=self._i_post_filter_en)
        self._logger.debug('Device configuration forced to mirror driver copy')

    def config_freerun_integration_mode(self, num_samples=None):
        """
        Initialize the device for free-run integration mode. This (or the pincontrol version) must
        be called before the read() function can be used.

        If number of samples is supplied, it will be updated from the default/previous setting. More
        samples will take more time, up to over 1000ms minimum for power measurement with 2048
        samples (see the datasheet Table 4-5).

        Once this has been called, the device will be integrating, and the read() function can be
        called to retrieve the most recently completed reading. This call can be made repeatedly
        without having to reconfigure the device.

        If the device needs to be taken out of integrate mode (for example to save power by allowing
        it to enter sleep mode), call stop_freerun_integration(). After this is called, config will
        have to be run again to restart integration.

        :param num_samples:     Number of samples in each integration cycle. Powers of 2 from 1-2048
        """
        # If no sample number is supplied, it will not be changed. FreeRun mode will just be set.

        # Write num sample register if provided
        if num_samples is not None:
            try:
                sample_reg_value = _SMPL_NUM_SAMPLES_ENCODING[num_samples]
            except KeyError:
                raise KeyError(
                        "Number of samples must be one of " +
                        "{}".format(_SMPL_NUM_SAMPLES_ENCODING.keys()))
            self._write_register_bitfield(7, 4, _SMPL_REG, sample_reg_value)

        # Set integration mode and measurement type in device
        if self._measurement_type is Measurement_Type.CURRENT:
            combined_int_meas_field = 0b01
        elif self._measurement_type is Measurement_Type.VBUS:
            combined_int_meas_field = 0b10
        elif self._measurement_type is Measurement_Type.POWER:
            combined_int_meas_field = 0b11
        else:
            raise ValueError("Measurement Type has not been set")
        self._write_register_bitfield(7, 2, 0x02, combined_int_meas_field)

        self._pincontrol_config_complete = False
        self._freerun_config_complete = True

        self._integration_mode = _Integration_Mode.FreeRun

        self._logger.info(
                'Config for free-run integration mode with measurement type ' +
                '{} complete'.format(self._measurement_type))

        # Start the free-running integration. Will be stopped on read
        self._register_set_integration()
        self._logger.debug('Now entering integration mode for free-run')

    def config_pincontrol_integration_mode(self, integration_time_ms=500):
        """
        Initialize the device for pin-controlled integration mode. This (or the freerun version)
        must be called before the Read() function can be used.

        If an integration time is supplied, this is the time for which the device will have the
        integration mode applied using the pin. If not supplied, 500ms is the default. If this
        device is being used as part of an array, there is no need to supply an integration time,
        as it can be used to init the array to which the device list will be fed.

        Once this function is called, the read() function will perform the integration for the
        specified time and return the result. This does not need to be called again before
        successive measurements, unless the integration time needs changing.

        :param integration_time_ms:     Integration time in ms
        """
        # Check that a pin has been assigned
        if not self._has_nRead_int_pin():
            raise Exception("Pin control mode requires a nRead_int pin")

        # Check that power measurement is selected (the only mode that supports pin control)
        if self._measurement_type is not Measurement_Type.POWER:
            raise Exception(
                    "Pin control mode does not support " +
                    "measurement type: {}".format(self._measurement_type))

        # Check that the integration time is allowed based on i resolution (could also be v)
        if self._i_resolution == 14:
            if integration_time_ms > 2900 or integration_time_ms < 2.7:
                raise ValueError(
                        "In 14-bit mode, integration time must be between 2.7-2900ms")
        else:   # 11-bit
            if integration_time_ms > 1000 or integration_time_ms < 0.9:
                raise ValueError(
                        "In 11-bit mode, integration time must be between 0.9-1000ms")

        # Make sure the pin is not being overridden
        self._write_register_bitfield(1, 1, 0x01, 0b0)

        # Make sure the pin is set to READ by default
        self._pin_set_read()

        # Set integration mode and measurement type in device
        # Must be power measurement type, since this is the only one that supports pin control
        self._write_register_bitfield(7, 2, 0x02, 0b00)     # Vpower, pin-controlled

        # Store the chosen integration time for pin control on read
        self._integration_time_ms = integration_time_ms

        self._pincontrol_config_complete = True
        self._freerun_config_complete = False

        self._integration_mode = _Integration_Mode.PinControlled

        self._logger.info(
                'Config for pin-controlled integration mode with integration time ' +
                '{}ms complete'.format(integration_time_ms))

    def set_measurement_type(self, measurement_type):
        """
        Change the measurement type between Vbus voltage, Rsense current, and power. If the desired
        measurement is supplied at device instantiation, no call is necessary. If the measurement
        needs changing, this call will need to be followed by configuration of free-run or pin-
        controlled mode.

        :param measurement_type:    Measurement_Type enum CURRENT, POWER or VBUS.
        """
        if type(measurement_type) is not Measurement_Type:
            raise TypeError

        # Check r_sense was supplied if the measurement type is not vbus (others need it for decode)
        if measurement_type is not Measurement_Type.VBUS:
            if self._r_sense is None:
                raise Exception(
                    "Measurement type {} requries Rsense resistor value".format(measurement_type))

        # Note: Measurement Type is only sent to device when integration mode is chosen

        # Set type in driver
        if self._measurement_type != measurement_type or self._measurement_type is None:
            # Once measurement has been changed, config should be run again to send the setting
            self._pincontrol_config_complete = False
            self._freerun_config_complete = False
        self._measurement_type = measurement_type

        self._logger.info('Measurement type set as {}'.format(measurement_type))

    def read(self):
        """
        Read a result from the PAC1921 using the integration mode configured. The result will be
        decoded as a float value, in Volts for VBus, Amps for Rsense current, or Watts for power.
        This function can only be called after the configure_<method>_integration_mode() function
        has been called.

        If the integration mode is pin-controlled, this will automatically trigger in integration
        for the time specified when the configuration function was called. This means it will delay
        by that amount of time.

        If the integration mode is free-run, the device will already be integrating, and the latest
        result will be read from the device. Depending on the cycle time (see datasheet Table 4-5),
        the result could be up to 3s old, but the return will be immediate. Integration will be
        restarted as soon as the read is complete.

        In both modes, successive reads can be made with no other calls.
        """
        if self._integration_mode == _Integration_Mode.PinControlled:
            self._logger.info('Starting pin-controlled integration')

            # Check that the config function has been called
            if not self._pincontrol_config_complete:
                # raise error for not being configured for pincontrol
                raise Exception("Configuration for pin-control has not been completed")

            # Trigger a timed integration on the device's pin
            self._trigger_pin_integration(self._integration_time_ms, self._pin_set_read, self._pin_set_integration)
            # Note: read must now take place within tsleep (1s) before erase

            return self._read_decode_output()

        elif self._integration_mode == _Integration_Mode.FreeRun:
            # By this point, integration mode should already have been entered in config
            self._logger.info('Reading free-run integration')

            # Check that the config function has been called
            if not self._freerun_config_complete:
                # raise error for not being configured for freerun
                raise Exception("Configuration for free-run has not been completed")

            # Enter read mode to stop integration
            self._logger.debug('Free-run integration mode ended')
            self._register_set_read()
            # Note: read must now take place within tsleep (1s) before erase

            # Must read result immediately, before integration mode is re-entered
            decoded_output = self._read_decode_output()

            # Re-enter integration mode ready for the next reading to be taken
            self._register_set_integration()
            self._logger.debug('re-entered free-run integration mode for next reading')

            return decoded_output

    def stop_freerun_integration(self):
        """
        Forcibly stop the integration in free-run mode. This places the device in READ mode
        permanently, meaning the device will enter sleep mode after 1s and consume considerably
        less power. This means readings will no longer be able to be taken until the configure
        freerun function is called again. The function has no effect on pin-control mode, which
        leaves the device in read mode by default when there is no reading being taken anyway.
        """
        if self._integration_mode == _Integration_Mode.FreeRun:
            self._register_set_read()

            # Config must be run again to start integration.
            self._freerun_config_complete = False

            self._logger.debug(
                    'Free-run integration mode ended, device can now sleep. Run config to wake')
        else:
            # In pin-controlled mode, device will sleep by default until read called
            self._logger.debug('This does nothing in pin-controlled mode')


class PAC1921_Synchronised_Array(object):
    """
    Class to link several PAC1921 devices together in pin-controlled mode, where they are using the
    same physical pin for nRead_int. This means the integration is performed once before reading
    data from all devices. All readings will therefore be synchronised.

    Devices should be configured individually (i.e. with gain settings etc) before being added to
    the array. There is no need to have called the pin-control configuration function.

    Note that all devices will be measuring power in this mode, which is the only measurement that
    supports pin-control.
    """

    def __init__(self, nRead_int_pin, integration_time_ms, device_list=None):
        """
        Create a new array for pin-controlled PAC1921 devices sharing a nRead_int pin.

        A device list can be supplied with already instantiated PAC1921 devices. Alternatively,
        devices can be added afterwards with add_device().

        The nRead_int_pin and integration_time_ms settings supplied will override any individual
        device settings set before this. Other settings will remain the same. I.E. devices that
        have been configured with different gain settings will remain that way, and this will still
        be handled in conversion automatically.

        :param nRead_int_pin:           gpiod line for read/integration control.
        :param integration_time_ms:     Integration time in ms.
        :param device_list:             List of PAC1921 devices to add to the array (optional, can
                                        be added individually after init with add_device()).
        """
        self._device_list = []

        self._logger = _logging.getLogger('odin_devices.PAC1921.array')

        if not isinstance(nRead_int_pin, type(gpiod.Line)):
            raise TypeError("nRead_int_pin should be of type gpiod.Line, "
                            "either from gpiod directly or the odin_devices gpio_bus driver")

        self._nRead_int_pin = nRead_int_pin

        self.set_integration_time(integration_time_ms)

        if device_list is not None:
            for device in device_list:
                self.add_device(device)     # Add the device to the array

    def add_device(self, device):
        """
        Add a device to the array. Device is checked for being a PAC1921 instance and being set for
        pin-controlled mode.
        """
        if type(device) is not PAC1921:
            raise TypeError("Device should be a PAC1921 Instance")
        if not device.pin_control_enabled():
            raise ValueError("Device should be set for pin-controlled integration mode")

        # Force the device into pin control mode. The lack of a pin is ignored since only the first
        # device in the device_list will be used to actuate it.
        if not device._pincontrol_config_complete:
            self._logger.debug(
                    'Forced device {} into pin control mode'.format(device.get_name()))
            try:
                device.config_pincontrol_integration_mode()
            except Exception as e:
                if 'requires a nRead_int pin' in e.args[0]:
                    pass
                else:
                    raise

        # Ensure the device's integration control is not being overridden by register control mode.
        # This would stop integration, and would not be automatically corrected as it would be
        # normally since _pin_set_integration() is called on another instance.
        device._write_register_bitfield(1, 1, 0x01, 0b0)

        # Set the first device's nRead_int pin to the one supplied to the array
        if len(self._device_list) == 0:
            self._logger.debug(
                    'Assigning nRead_int_pin to first device: {}'.format(device.get_name()))

            # Set the device to use the array integration pin
            device._set_nRead_int_pin(self._nRead_int_pin)

            # Set the device to use the array integration time
            device.config_pincontrol_integration_mode(self._integration_time_ms)

        # Add the device to the array
        self._device_list.append(device)

        self._logger.info('New device {} added to array'.format(device._name))

    def set_integration_time(self, integration_time):
        """
        Change the integration time used for the entire array.
        """
        self._integration_time_ms = integration_time

        # If the first device has already been added, set the integration time
        if len(self._device_list) > 0:
            self._device_list[0].config_pincontrol_integration_mode(integration_time)

        self._logger.info('Array integration time set as {}ms'.format(integration_time))

    def read_devices(self):
        """
        Perform the integration and read results from all devices in turn. To avoid confusion, the
        result is a tuple of device names and results.

        Note that all devices will be measuring power in this mode, which is the only measurement that
        supports pin-control. Results are in watts.
        """
        # Check that the integration time has been set
        if self._integration_time_ms is None:
            raise Exception("Integration time is not set")

        # Check that there are devices in the array
        if len(self._device_list) == 0:
            raise Exception("No devices in array")

        # Trigger the pin-controlled integration on one device
        self._device_list[0]._trigger_pin_integration(self._integration_time_ms)

        # Form a list of decoded outputs combined with names
        decoded_outputs = []
        for device in self._device_list:
            decoded_outputs.append(device._read_decode_output())

        return (self.get_names(), decoded_outputs)

    def get_names(self):
        """
        For convenience, return the list of device names. This is in the same order as results will
        be reported.
        """
        names = []
        for device in self._device_list:
            names.append(device.get_name())
        return names
