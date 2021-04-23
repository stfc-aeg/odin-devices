from odin_devices.i2c_device import I2CDevice
from enum import Enum

import logging

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

# Register Map
_VBUS_RESULT_REG = 0x10     # 16-bits from 0x10 to 0x11
_VSENSE_RESULT_REG = 0x12   # 16-bits from 0x12 to 0x13
_VPOWER_RESULT_REG = 0x1D   # 16-bits from 0x1D to 0x1E

# Default POR values
_DV_GAIN_DEFAULT = 1
_DI_GAIN_DEFAULT = 1
_I_RES_DEFAULT = 11
_V_RES_DEFAULT = 11
_I_POST_FILT_EN_DEFAULT = False
_V_POST_FILT_EN_DEFAULT = False

class PAC1921_Synchronised_Array(object):

    def __init__(self, device_list=None, nRead_int_pin=None, integration_time=None):

        if device_list is not None:
            for device in device_list:
                # Add the device to the array
                self.add_device(device)

                # Check for an integration control pin if one was not supplied
                if nRead_int_pin is None:
                    if device._has_nRead_int_pin():
                        nRead_int_pin = device._get_nRead_int_pin()

                # Inherit integration time if any device has one and if one was not supplied
                if integration_time is None:
                    if device._integration_time is not None:
                        integration_time = device._integration_time

        if nRead_int_pin is None:
            raise ValueError("No nREAD/int pin given in array init or array devices")
        self._nRead_int_pin = nRead_int_pin

        self._integration_time = integration_time

    def add_device(self, device: PAC1921):
        if type(device) is not PAC1921:
            raise TypeError("Device should be a PAC1921 Instance")
        if device.get_integration_mode() != INTEGRATION_MODE_PinControlled:
            raise ValueError("Device should be configured for pin-controlled integration mode")
        self._device_list.append(device)

    def set_integration_time(self, integration_time):
        self._integration_time = integration_time

    def integrate_read_devices(self):
        # Check that the integration time has been set
        if self._integration_time is None:
            raise Exception("Integration time is not set")

        # Trigger the pin-controlled integration
        self._trigger_pin_integration(self._integration_time, self._nRead_int_pin)

        # Form a list of decoded outputs
        decoded_outputs = []
        for device in self._device_list:
            decoded_outputs.append(devicec._read_decode_output())

        return decoded_outputs


class PAC1921(I2CDevice):
    class _Integration_Mode (Enum):
        FreeRun
        PinControlled

    class _Measurement_Type (Enum):
        POWER
        VBUS
        VSENSE

    def __init__(self, i2c_address=None, address_resistance=None, name='PAC1921', nRead_int_pin=None, r_sense=None, measurement_type=None):
        #Rsense must be supplied unless the measurement is voltage

        # Init logger
        self._name = name        # Name is used because there may be multiple monitors
        self._logger = logging.getLogger('odin_devices.pac1921.' +
                                         self._name + '@' +
                                         hex(self._i2c_address))

        # If an i2c address is not present, work one out from resistance, if supplied
        if i2c_address is None:
            if address_resistance is not None:
                i2c_address = self._get_address_from_resistance(address_resistance)
            else:
                raise ValueError(
                        "Either an I2C address or address resistance value must be supplied")

        self._nRead_int_pin = nRead_int_pin
        self._r_sense = r_sense

        # Init the I2C Device
        self._i2c_address = i2c_address
        super().__init__(self._i2c_address)

        # Reset the device
        self.reset()

        # Check that the measurement type is valid
        if type(measurement_type) is _Measurement_Type:
            self.set_measurement_type(measurement_type)
        else:
            raise TypeError("Invalid measurement type given")

        self._pincontrol_config_complete = True
        self._freerun_config_complete = False
        self._integration_time = None        # Will be set in pin-control config

        # Assume that device has been reset and store default values until config is called
        self._integration_mode = _Integration_Mode.PinControlled    # pin-control default on POR
        self._dv_gain = _DV_GAIN_DEFAULT
        self._di_gain = _DI_GAIN_DEFAULT
        self._i_resolution = _I_RES_DEFAULT
        self._v_resolution = _V_RES_DEFAULT
        self._v_post_filter_en = _V_POST_FILT_EN_DEFAULT
        self._i_post_filter_en = _I_POST_FILT_EN_DEFAULT

    def _trigger_pin_integration_(integration_time, integration_pin):
        # TODO integration pin control
        pass

    def _get_address_from_resistance(address_resistance):
        if address_resistance in _ADDRESS_RESISTANCE_MAPPING.keys():
            return _ADDRESS_RESISTANCE_MAPPING[address_resistance]
        else:
            raise ValueError("Invalid address resistance supplied")

    def reset(self):
        # Reset registers
        # TODO
        # TODO Can be done with the pin if held low? Is it possible without?
        pass

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
        old_value = self.readU8(register)

        # Mask off original bits
        mask_top = (0xFF << (start_bit + 1)) 0xFF
        mask_bottom = pow(2, ((start_bit + 1) - bit_width)) - 1
        mask_keep = (mask_top | mask_bottom) & 0xFF
        masked_old_value = old_value & mask_keep

        # Replace masked off bits with new slice
        new_reg_value = masked_old_value | (value << ((start_bit + 1) - bit_width)) & 0xFF

        # Write newly formed value to the register
        self.write8(new_reg_value)

    def _read_decode_output(self):
        # TODO check for overflows?
        if self._measurement_type is _Measurement_Type.VBUS:
            # Read the raw register
            vbus_raw = self.readU16(_VBUS_RESULT_REG) >> 6

            # Decode the Vbus value
            vbus_lsb_volts = (32.0 / self._dv_gain) / float(1023 * pow(2,6))
            vbus_result = vbus_lsb_volts * vbus_raw

            return vbus_result

        elif self._measurement_type is _MeasurementType.VSENSE:
            # Read the raw register
            vsense_raw = self.readU16(_VSENSE_RESULT_REG) >> 6

            # Decode the Vsense value
            vsense_lsb_amps = (0.1 / (self._r_sense * self._di_gain)) / float(1023 * pow(2,6))
            vsense_result = vsense_lsb_amps * vsense_raw

            return vsense_result

        elif self._measurement_type is _MeasurementType.POWER:
            # Read the raw register
            power_raw = self.readU16(_POWER_RESULT_REG) >> 6

            # Decode the Power value
            ipart = 0.1 / (self._r_sense * self._di_gain)
            vpart = 32.0 / self._dv_gain
            power_lsb_watts = (ipart * vpart) / float(1023 * pow(2,6))
            power_result = power_lsb_watts * power_raw

            return power_result

    def _has_nRead_int_pin(self):
        return (self._nRead_int_pin is not None)

    def _get_nRead_int_pin(self):
        return self._nRead_int_pin

    def get_integration_mode(self):
        return self._integration_mode

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

    def config_freerun_integration_mode(self, num_samples=None):
        # If no sample number is supplied, it will not be changed. FreeRun mode will just be set.
        # TODO write num sample register, any other settings

        # TODO give estimate of integration time?

        # Set integration mode and measurement type in device
        if self._measurement_type is PAC1921.Measurement_Type.VSENSE:
            combined_int_meas_field = 0b01
        elif self._measurement_type is PAC1921.Measurement_Type.VBUS:
            combined_int_meas_field = 0b10
        elif self._measurement_type is PAC1921.Measurement_Type.POWER:
            combined_int_meas_field = 0b11
        self._write_register_bitfield(7, 2, 0x02, combined_int_meas_field)

        self._pincontrol_config_complete = False
        self._freerun_config_complete = True

    def config_pincontrol_integration_mode(self, integration_time_ms):
        # Check that a pin has been assigned
        if not self._has_nRead_int_pin():
            raise Exception("Pin control mode requires a nRead_int pin")

        # Check that power measurement is selected (the only mode that supports pin control)
        if self._measurement_type is not _Measurement_Type.POWER:
            raise Exception(
                    "Pin control mode does not support " +
                    "measurement type: {}".format(self._measurement_type))

        # Check that the integration time is allowed based on i resolution (could also be v)
        if self._i_resolution == 14:
            if integration_time_ms > 2900 or integration_time_ms < 2.7
                raise ValueError(
                        "In 14-bit mode, integration time must be between 2.7-2900ms")
        else:   # 11-bit
            if integration_time_ms > 1000 or integration_time_ms < 0.9
                raise ValueError(
                        "In 11-bit mode, integration time must be between 0.9-1000ms")

        # Set integration mode and measurement type in device
        # Must be power measurement type, since this is the only one that supports pin control
        self._write_register_bitfield(7, 2, 0x02, 0b00)     # Vpower, pin-controlled

        # Store the chosen integration time for pin control on read
        self._integration_time = integration_time

        self._pincontrol_config_complete = True
        self._freerun_config_complete = False

    def set_measurement_type(self, measurement_type: _Measurement_Type):
        if type(measurement_type) is not _Measurement_type:
            raise TypeError

        # Check r_sense was supplied if the measurement type is not vbus (others need it for decode)
        if measurement_type is not _Measurement_Type.VBUS:
            raise Exception(
                    "Measurement type {} requries Rsense resistor value".format(measurement_type))

        # Note: Measurement Type is only sent to device when integration mode is chosen

        # Set type in driver
        if self._measurement_type != measurement_type:
            # Once measurement has been changed, config should be run again to send the setting
            Self._pincontrol_config_complete = False
            Self._freerun_config_complete = False
        self._measurement_type = measurement_type

    def integrate_and_read(self):
        if self._integration_mode == INTEGRATION_MODE_PinControlled:

            # Check that the config function has been called
            if not self._pincontrol_config_complete:
                # raise error for not being configured for pincontrol
                raise Exception("Configuration for pin-control has not been completed")

            # Trigger an integration on the device's pin
            self._trigger_pin_integration(self._integration_time, self._get_nRead_int_pin())

        elif self._integration_mode == _Integration_Mode.FreeRun:

            # Check that the config function has been called
            if not self._freerun_config_complete:
                # raise error for not being configured for freerun
                raise Exception("Configuration for free-run has not been completed")

        return self._read_decode_output()
