from odin_devices.i2c_device import I2CDevice as _I2CDevice
from enum import Enum as _Enum, auto as _auto

import logging as _logging
import time as _time

_GPIO_AVAIL = True
try:
    import gpiod as _gpiod
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
    CURRENT = _auto()

class _Integration_Mode (_Enum):
    FreeRun = _auto()
    PinControlled = _auto()


class PAC1921(object):
    def __init__(self, i2c_address=None, address_resistance=None, name='PAC1921', nRead_int_pin=None, r_sense=None, measurement_type=None):
        #Rsense must be supplied unless the measurement is voltage

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
        if self._nRead_int_pin is None:
            raise Exception("Cannot drive pin, no pin was supplied")

        # Disable register read/int control
        self._write_register_bitfield(1, 1, 0x01, 0b0)

        # Set read mode
        self._nRead_int_pin.set_value(1)

        self._nRead_int_state = True

    def _pin_set_read(self):
        if self._nRead_int_pin is None:
            raise Exception("Cannot drive pin, no pin was supplied")

        # Disable register read/int control
        self._write_register_bitfield(1, 1, 0x01, 0b0)

        # Set read mode
        self._nRead_int_pin.set_value(0)

        self._nRead_int_state = False

    def _register_set_integration(self):
        # Enable register read/int control
        self._write_register_bitfield(1, 1, 0x01, 0b1)

        # Set integration mode
        self._write_register_bitfield(0, 1, 0x01, 0b1)

        self._nRead_int_state = True

    def _register_set_read(self):
        # Enable register read/int control
        self._write_register_bitfield(1, 1, 0x01, 0b1)

        # Set read mode
        self._write_register_bitfield(0, 1, 0x01, 0b0)

        self._nRead_int_state = False

    def _trigger_pin_integration(self, integration_time_ms):

        # Set the pin to integrate mode
        self._pin_set_integration()

        # Wait for time integration time to be reached
        _time.sleep(integration_time_ms / 1000.0)

        # Set the pin to read mode
        self._pin_set_read()

    def _get_address_from_resistance(address_resistance):
        if address_resistance in _ADDRESS_RESISTANCE_MAPPING.keys():
            return _ADDRESS_RESISTANCE_MAPPING[address_resistance]
        else:
            raise ValueError("Invalid address resistance supplied")

    def _write_register_bitfield(self, start_bit, bit_width, register, new_value):
        # Write a selection of bits within a register. For this device, single-byte fields suffice.

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

            return power_result

    def _has_nRead_int_pin(self):
        return (self._nRead_int_pin is not None)

    def _get_nRead_int_pin(self):
        return self._nRead_int_pin

    def _set_nRead_int_pin(self, nRead_int_pin):
        if nRead_int_pin is not None:
            if type(nRead_int_pin) is not _gpiod.Line:
                raise TypeError("nRead_int_pin should be of type gpiod.Line, "
                                "either from gpiod directly or the odin_devices gpio_bus driver")

        self._nRead_int_pin = nRead_int_pin

    def pin_control_enabled(self):
        return (self._integration_mode == _Integration_Mode.PinControlled)

    def get_name(self):
        return self._name

    def get_address(self):
        return self._i2c_device.address

    def config_resolution_filtering(self, adc_resolution=None, post_filter_en=None):
        # Completely optional

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
        # Completely optional

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
            if dv_gain not in _Dx_GAIN_ENCODING.keys():
                raise ValueError(
                        "DV Gain not valid. Choose from {}".format(_Dx_GAIN_ENCODING.keys()))

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
        # Force a config update for the resolution, filtering and gain by writing the values stored
        # in the driver to the device.
        self.config_gain(di_gain = self._di_gain, dv_gain = self._dv_gain)
        self.config_resolution_filtering(adc_resolution=self._i_resolution,
                                         post_filter_en=self._i_post_filter_en)
        self._logger.debug('Device configuration forced to mirror driver copy')

    def config_freerun_integration_mode(self, num_samples=None):
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

    def set_measurement_type(self, measurement_type: Measurement_Type):
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

    def integrate_and_read(self):
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
        if self._integration_mode == _Integration_Mode.FreeRun:
            self._register_set_read()

            # Config must be run again to start integration.
            self._freerun_config_complete = False

            self._logger.debug(
                    'Free-run integration mode ended, device can now sleep. Run config to wake')
        else:
            # In pin-controlled mode, device will sleep by default until integrate_and_read called
            self._logger.debug('This does nothing in pin-controlled mode')


class PAC1921_Synchronised_Array(object):

    def __init__(self, device_list=None, nRead_int_pin=None, integration_time_ms=None):

        self._logger = _logging.getLogger('odin_devices.PAC1921.array')

        self._integration_device = None
        self._device_list = []
        if device_list is not None:
            for device in device_list:
                # Check that the device has been configured for pin control properly, since this
                # would normally be checked in the integrate method that is now only called for
                # one of the devices
                if not device._pincontrol_config_complete:
                    # Force device to use pin control, ignore error about no pin (it is assumed
                    # that another device will have the pin. If not, this will be caught later)
                    try:
                        device.config_pincontrol_integration_mode()
                    except Exception as e:
                        if 'requires a nRead_int pin' in e.args[0]:
                            pass
                        else:
                            raise

                # Add the device to the array
                self.add_device(device)

                # Ensure that the device will respond to a pin control event (disable register ctrl)
                device._write_register_bitfield(1, 1, 0x01, 0b0)

                # Check for an integration control pin if one was not supplied
                if nRead_int_pin is None:
                    if device._has_nRead_int_pin():
                        self._integration_device = device

                # Inherit integration time if any device has one and if one was not supplied
                if integration_time_ms is None:
                    if device._integration_time_ms is not None:
                        integration_time_ms = device._integration_time_ms

        # If no devices already had nRead_int pins assigned, use the one supplied
        if self._integration_device is None:
            if nRead_int_pin is not None:
                self._integration_device = self._device_list[0] # Pick first device
                self._integration_decice._set_nRead_int_pin(nRead_int_pin)  # Assign supplied pin
            else:
                # No pin was supplied, and no instances supplied had a pin
                if nRead_int_pin is None and self._integration_device is None:
                    raise ValueError(
                            "No pin given or present in any device. nRead_int_pin is required")

        self._integration_time_ms = integration_time_ms

    def add_device(self, device: PAC1921):
        if type(device) is not PAC1921:
            raise TypeError("Device should be a PAC1921 Instance")
        if not device.pin_control_enabled():
            raise ValueError("Device should be configured for pin-controlled integration mode")
        self._device_list.append(device)

        self._logger.info('New device {} added to array'.format(device._name))

    def set_integration_time(self, integration_time):
        self._integration_time_ms = integration_time

    def integrate_read_devices(self):
        # Check that the integration time has been set
        if self._integration_time_ms is None:
            raise Exception("Integration time is not set")

        # Trigger the pin-controlled integration on one device
        self._integration_device._trigger_pin_integration(self._integration_time_ms)

        # Form a list of decoded outputs combined with names
        decoded_outputs = []
        for device in self._device_list:
            decoded_outputs.append(device._read_decode_output())

        return (self.get_names(), decoded_outputs)

    def get_names(self):
        names = []
        for device in self._device_list:
            names.append(device.get_name())
        return names
