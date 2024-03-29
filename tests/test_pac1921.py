"""
Tests for PAC1921 power monitors. The driver is I2CDevice-derived.

To Test:
    - [x] Address assignment with direct allocation and resistance
    - [x] Prodid manufacturer tests check right area and raise error on fail
    - [x] Invalid measurement type supplied to init raises error
    - [x] Not supplying a pin does not cause error, but uses register read functions
    - [x] Register read/write functionality method is correct for bitfields (read-modify-write)
    - [x] Functions exporting mode info is correct: pin_control_enabled, get_name, get_address...
    - Pin Control Mode
        - [x] Check that the integration time is held for the correct duration on trigger
        - [x] Check that the pin is toggled on trigger
    - Readout
        - [x] Check that example values (using datasheet examples) are read out correctly for
                each mode
        - [x] Check that overflows are caught, and result in warnings
        - [x] Check that the read function cannot be called without configuring first
        - [x] Check that if in freerun mode, reading will re-enter integration automatically
    - ADC and Filtering Configuration
        - [x] Check that adc resolution is set correctly, and takes only valid values
        - [x] Check that post filtering is set correctly, and takes only valid values
        - [x] Check that integration mode is re-entered in whatever mode is being used so that
                the changes take effect
    - Gain Configuration
        - [x] Check that di and dv gain are set correctly, and take only valid values
        - [x] Check that integration mode is re-entered in whatever mode is being used so that
                the changes take effect
    - [ ] Check that forcing the config update will update the chip with internally stored values
            for the ADC sampling, post filtering, dv and di gain
    - [x] FreeRun Configuration
        - [x] Check that an invalid number of samples is caught, and a correct number of samples
                results in registers being set correctly.
        - [x] Check that the mode is sent correctly to the device
        - [x] Check that the integration is actually started immediately
        - [x] Check that stopping free-run integration actually stops it, and stops read() from
                being called successfully.
    - [x] Pin Control Config
        - [x] Check that lack of a read interrupt pin will result in failure
        - [x] Check that measurement is power
        - [x] Check that integration time is 'allowed' based on di or dv resolution
        - [x] Make sure that the system is primed in read mode by pin control
        - [x] Make sure that the measurement type is set, with pin control mode
    - [ ] Check that setting a new measurement type means read cannot be activated until a control
            mode is configured
    - Synchronised Array
        - [x] Check that devices can be added to the array both at init and with add_device
            - [x] Check that the device type is checked
            - [x] Check that the device must be in pin control mode
        - Integration
            - [x] Check that the array integration time has taken effect
            - [x] Check that if integration time is supplied at init and devices are added later,
                it still takes effect
            - [x] Check that an invalid integration time is caught
            - [x] Check that set_integration_time() function successfully changes the integration time
            - [x] Check that the correct pin is used for integration (array one), even if the pins
                already had assigned pins.
        - [x] Check that get_names returns valid supplied names of devices
        - Read Devices
            - [x] Check that a lack of devices throws an error
            - [x] Check that the measurements for each device are read and associated with the
                    correct device

"""

import sys
import pytest
import time

if sys.version_info[0] == 3:                # pragma: no cover
    from unittest.mock import Mock, MagicMock, call, patch
    from importlib import reload as reload
else:                                       # pragma: no cover
    from mock import Mock, MagicMock, call, patch

sys.modules['smbus'] = MagicMock()
sys.modules['gpiod.Line'] = MagicMock()
import odin_devices.pac1921                 # Needed so that module can be reloaded
from odin_devices.pac1921 import PAC1921, PAC1921_Synchronised_Array, Measurement_Type, OverflowException
import smbus
from odin_devices.i2c_device import I2CDevice
import gpiod

prodid_success_mock = MagicMock()

"""
This is the percentage accuracy required when reporting values using a simulated register count.
"""
PASSING_PERCENTAGE_ACCURACY = 0.1

class pac1921_test_fixture(object):
    def __init__(self):

        with patch.object(PAC1921,'_check_prodid_manufacturer') as prodid_success_mock: # Force ID check success
            self.device = PAC1921(i2c_address = 0x5A)

        self.device._i2c_device = Mock()
        self.mock_gpio_pin = gpiod.Line()            # Create mock pin

@pytest.fixture(scope="class")
def test_pac1921():
    test_driver_fixture = pac1921_test_fixture()
    yield test_driver_fixture

def assert_within_percent(val_a, val_b, percentage):
    """
    Checks that value b is within a certain percentage difference of value a.
    """
    assert abs((val_a-val_b)/val_a) <= (percentage / 100.0), \
            "Values {}, {} differ more than {}%".format(val_a, val_b, percentage)


class TestPAC1921():
    def test_address_assignment(self, test_pac1921):
        with patch.object(PAC1921,'_check_prodid_manufacturer') as prodid_success_mock: # Force ID check success
            # Test the I2C device is created when an address is supplied directly
            test_pac1921.device = PAC1921(i2c_address=0x5A)
            assert(test_pac1921.device._i2c_device.address == 0x5A)

            # Test the I2C device is created when a resistance is supplied
            test_pac1921.device = PAC1921(address_resistance=0)
            assert(test_pac1921.device._i2c_device.address == 0b1001100)    # From datasheet table
            test_pac1921.device = PAC1921(address_resistance=820)
            assert(test_pac1921.device._i2c_device.address == 0b1001010)    # From datasheet table
            test_pac1921.device = PAC1921(address_resistance=12000)
            assert(test_pac1921.device._i2c_device.address == 0b0101110)    # From datasheet table

            # Test that an invalid resistance results in a raised error
            with pytest.raises(ValueError, match=".*Invalid address resistance.*"):
                test_pac1921.device = PAC1921(address_resistance=80)

            # Check that if no resistance or address is supplied that an error is raised
            with pytest.raises(ValueError, match=".*Either an I2C address or address resistance value must be supplied.*"):
                test_pac1921.device = PAC1921()

    def test_write_register_bitfield(self, test_pac1921):
        # Tests the basic read/write of fields within individual registers
        writemock = MagicMock()
        readmock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:
            # Create the device under test
            test_pac1921.device = PAC1921(i2c_address=0x5A)

            # Check that writing a whole byte to a register writes the correct value
            writemock.reset_mock()
            readmock.side_effect = lambda reg: {
                    0x02: 0b00000000}[reg]      # Register 0x02 will read as 0xFF
            test_pac1921.device._write_register_bitfield(7, 8, 0x02, 0xAA)
            writemock.assert_called_with(0x02, 0xAA)

            # Check that writing three specific bits to a register writes correctly
            writemock.reset_mock()
            readmock.side_effect = lambda reg: {
                    0x02: 0b00000000}[reg]      # Register 0x02 will read as 0xFF
            test_pac1921.device._write_register_bitfield(5, 3, 0x02, 0b101)
            writemock.assert_called_with(0x02, 0b00101000)

            # Check that writing with width greater than 8 bits or less than 1 throws an error
            with pytest.raises(ValueError, match=".*bit_width must be in range.*"):
                test_pac1921.device._write_register_bitfield(7, 0, 0x02, 0b101)
            with pytest.raises(ValueError, match=".*bit_width must be in range.*"):
                test_pac1921.device._write_register_bitfield(7, 9, 0x02, 0b101)

            # Check that writing a value wider than the width throws an error
            with pytest.raises(ValueError, match=".*Value 11 does not fit in 3 bits.*"):
                test_pac1921.device._write_register_bitfield(5, 3, 0x02, 0b1011)

            # Check that writing a width greater than the start bit allows throws an error
            with pytest.raises(ValueError, match=".*bit_width must be in range.*"):
                test_pac1921.device._write_register_bitfield(1, 3, 0x02, 0b101)

            # Check that writing with an invalid start bit throws an error
            with pytest.raises(ValueError, match=".*start_bit must be in range.*"):
                test_pac1921.device._write_register_bitfield(8, 0, 0x02, 0b101)
            with pytest.raises(ValueError, match=".*start_bit must be in range.*"):
                test_pac1921.device._write_register_bitfield(-1, 9, 0x02, 0b101)

            # Check that writing an invalid register address throws an error
            with pytest.raises(KeyError, match=".*Register 0x99 is not valid.*"):
                test_pac1921.device._write_register_bitfield(7, 8, 0x99, 0xFF)

    def test_product_manufacturer_id_check(self, test_pac1921):
        test_pac1921.device._i2c_device.readU8 = MagicMock()

        # Check that a correct ID passes
        test_pac1921.device._i2c_device.readU8.side_effect = lambda reg: {0xFD:0b01011011, 0xFE:0b01011101}[reg]
        test_pac1921.device._check_prodid_manufacturer()

        # Check that an incorrect Product ID raises a relevant exception
        with pytest.raises(Exception, match=".*Product ID.*"):
            test_pac1921.device._i2c_device.readU8.side_effect = lambda reg: {0xFD:0b01011010, 0xFE:0b01011101}[reg]
            test_pac1921.device._check_prodid_manufacturer()

        # Check that an incorrect Manufacturer ID raises a relevant exception
        with pytest.raises(Exception, match=".*Manufacturer ID.*"):
            test_pac1921.device._i2c_device.readU8.side_effect = lambda reg: {0xFD:0b01011011, 0xFE:0b01011100}[reg]
            test_pac1921.device._check_prodid_manufacturer()

    def test_remaining_init_checks(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()

        temp_pin = MagicMock(spec=gpiod.Line)
        temp_pin.set_value = Mock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:

            print("readU8 result: ", I2CDevice.readU8())

            # Test that an invalid measurement type causes an error
            with pytest.raises(TypeError):
                test_pac1921.device = PAC1921(i2c_address=0x5A, measurement_type='Voltage')

            # Test that attempting to set an invalid pin type causes error (different to None)
            with pytest.raises(Exception, match=".*should be of type gpiod.Line.*"):
                test_pac1921.device = PAC1921(i2c_address=0x5A, nRead_int_pin=3)

            # Test that if a pin is supplied, the device is put into read mode with pin control
            try:
                writemock.reset_mock()     # Reset i2c write record
                readmock.return_value = 0xFF                    # Read from registers will always be all 1's
                test_pac1921.device = PAC1921(i2c_address=0x5A, nRead_int_pin=temp_pin)
                writemock.assert_any_call(1, 0b11111101)        # Assert register control was disabled (bit 1 low)
                temp_pin.set_value.assert_called_with(0)        # Assert pin control read entered

                assert(test_pac1921.device._get_nRead_int_pin() == temp_pin)    # Make sure get pin func works
            except Exception as e:
                print("writemock calls: {}".format(writemock.mock_calls))
                raise

            # Test that if a pin is not supplied, the device is put into read mode with register control
            try:
                writemock.reset_mock()     # Reset i2c write record
                readmock.return_value = 0b01                    # Read from register will be 0b01, opposite of final
                test_pac1921.device = PAC1921(i2c_address=0x5A)
                writemock.assert_any_call(1, 0b00000011)        # Assert register control was enabled
                writemock.assert_any_call(1, 0b00000000)        # Assert register control read entered
            except Exception as e:
                print("writemock calls: {}".format(writemock.mock_calls))
                raise

            # Test that get_name and get_address functions return submitted values
            test_pac1921.device = PAC1921(i2c_address=0x5A, name="testname")
            assert(test_pac1921.device.get_name() == "testname")
            assert(test_pac1921.device.get_address() == 0x5A)

    def test_di_dv_gain_configuration(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:
            test_pac1921.device = PAC1921(i2c_address=0x5A)

            # Test that invalid DI gain is caught
            with pytest.raises(ValueError):
                test_pac1921.device.config_gain(di_gain=0)

            # Test that invlaid DV gain is caught (and that DV is not allowed above 32)
            with pytest.raises(ValueError):
                test_pac1921.device.config_gain(dv_gain=64)    # Above max for dv

            # Test that setting valid DI gain sets correct bits
            try:
                writemock.reset_mock()
                readmock.return_value = 0                       # mock register initial value as 0
                test_pac1921.device.config_gain(di_gain=64)     # di gain is allowed higher than dv
                writemock.assert_called_with(0, 0b00110000)     # Reg 00 bits 5-3 should be 0b110
            except:
                print("writemock calls: {}".format(writemock.mock_calls))
                raise

            # Test that setting valid DV gain sets correct bits
            try:
                writemock.reset_mock()
                readmock.return_value = 0                       # mock register initial value as 0
                test_pac1921.device.config_gain(dv_gain=16)
                writemock.assert_called_with(0, 0b00000100)     # Reg 00 bits 2-0 should be 0b100
            except:
                print("writemock calls: {}".format(writemock.mock_calls))
                raise

            # Test that if gains change, integration mode is re-entered automatically, or the new
            # changes will not take effect
            test_pac1921.device._register_set_integration()     # Set the device into integration mode
            writemock.reset_mock()
            readmock.return_value = 0
            try:
                test_pac1921.device.config_gain(di_gain=8)
                writemock.assert_any_call(1, 0b00000000)        # Called to set read mode first
                writemock.assert_called_with(1, 0b00000001)     # Last call leaves in integration
            except Exception:
                print("set write calls: ", writemock.mock_calls)
                raise

    def test_adc_filtering_configuration(self, test_pac1921):
        # Test the ADC resolution and postfilter activation function. Note that this will currently
        # assume that the di and dv settings are being set in parallel, which is the current design
        # behaviour of the driver.

        writemock = MagicMock()
        readmock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:
            test_pac1921.device = PAC1921(i2c_address=0x5A)

            # Test that an invalid ADC resolution raises an error
            with pytest.raises(ValueError):
                test_pac1921.device.config_resolution_filtering(adc_resolution=10)

            # Test that a valid ADC resolution writes the correct bits
            try:
                writemock.reset_mock()
                readmock.return_value = 0                       # mock register initial value as 0
                test_pac1921.device.config_resolution_filtering(adc_resolution=11)
                writemock.assert_any_call(0, 0b10000000)        # 11-bit enabled for VSense
                writemock.assert_any_call(0, 0b01000000)        # 11-bit filter enabled for VBus

                writemock.reset_mock()
                readmock.return_value = 0b11111111              # mock register initial value as 1's
                test_pac1921.device.config_resolution_filtering(adc_resolution=14)
                writemock.assert_any_call(0, 0b01111111)        # 11-bit disabled for VSense
                writemock.assert_any_call(0, 0b10111111)        # 11-bit disabled for VBus
            except:
                print("writemock calls: {}".format(writemock.mock_calls))
                raise

            # Test that an invalid post_filter_en value raises an error
            with pytest.raises(ValueError):
                test_pac1921.device.config_resolution_filtering(post_filter_en=10)

            # Test that enabling the post filter writes correct bytes
            try:
                writemock.reset_mock()
                readmock.return_value = 0                       # mock register initial value as 0
                test_pac1921.device.config_resolution_filtering(post_filter_en=True)
                writemock.assert_any_call(1, 0b00001000)        # Post filter enabled for VSense
                writemock.assert_any_call(1, 0b00000100)        # Post filter enabled for VBus
            except:
                print("writemock calls: {}".format(writemock.mock_calls))
                raise

            # Test that if settings change, integration mode is re-entered automatically, or the new
            # changes will not take effect. This is the same as above test for gain.
            test_pac1921.device._register_set_integration()     # Set the device into integration mode
            writemock.reset_mock()
            readmock.return_value = 0
            try:
                test_pac1921.device.config_resolution_filtering(adc_resolution=11)
                writemock.assert_any_call(1, 0b00000000)        # Called to set read mode first
                writemock.assert_called_with(1, 0b00000001)     # Last call leaves in integration
            except Exception:
                print("set write calls: ", writemock.mock_calls)
                raise

    def test_read_decode_output_voltage(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:
            test_pac1921.device = PAC1921(i2c_address=0x5A, measurement_type=Measurement_Type.VBUS)

            # Check that the VBus Measurement functions correctly
            tmp_real_voltage = 3.0
            tmp_dv_gain = 8
            test_pac1921.device.config_gain(dv_gain=tmp_dv_gain)    # Set the gain internally
            calc_1lsb_val = (32.0/float(tmp_dv_gain)) / float(1023*64)    # From datasheet
            expected_result_count = int(tmp_real_voltage / calc_1lsb_val)
            print("1LSB should be {}v when gain is {}".format(calc_1lsb_val, tmp_dv_gain))
            print("Injected register value {} to represent {}v".format(expected_result_count, tmp_real_voltage))
            readmock.side_effect = lambda reg: {            # Set fake register to return expected count
                    0x10: (expected_result_count & 0xFF00) >> 8,    # Upper result
                    0x11: expected_result_count & 0xFF,             # Lower result
                    0x1C: 0b000}[reg]                               # Overflow status is none
            assert_within_percent(tmp_real_voltage, test_pac1921.device._read_decode_output(),
                                  PASSING_PERCENTAGE_ACCURACY)
            readmock.side_effect = None

    def test_read_decode_output_current(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:
            # Create device, initially set to voltage
            test_pac1921.device = PAC1921(i2c_address=0x5A, measurement_type=Measurement_Type.VBUS)

            # Check that changing measurement type to Current without rsense being set will fail
            with pytest.raises(Exception, match=".*Rsense.*"):
                test_pac1921.device.set_measurement_type(Measurement_Type.CURRENT)

            # Check current
            tmp_real_current = 0.200    # 200mA
            tmp_sense_resistor = 0.01   # 10 mohm
            tmp_sense_voltage = tmp_real_current * tmp_sense_resistor
            tmp_di_gain = 8
            test_pac1921.device.set_rsense(tmp_sense_resistor)
            test_pac1921.device.set_measurement_type(Measurement_Type.CURRENT)
            test_pac1921.device.config_gain(di_gain=tmp_di_gain)
            calc_1lsb_val = (0.1/(tmp_di_gain*tmp_sense_resistor)) / float(1023*64)    # From datasheet
            expected_result_count = int(tmp_real_current / calc_1lsb_val)
            print("1LSB should be {}A)when gain is {}".format(calc_1lsb_val,
                                                                   tmp_di_gain))
            print("Injected register value {} to represent {}A({}v)".format(expected_result_count,
                                                                            tmp_real_current,
                                                                            tmp_sense_voltage))
            readmock.side_effect = lambda reg: {            # Set fake register to return expected count
                    0x12: (expected_result_count & 0xFF00) >> 8,    # Upper result
                    0x13: expected_result_count & 0xFF,             # Lower result
                    0x1C: 0b000}[reg]                               # Overflow status is none
            assert_within_percent(tmp_real_current, test_pac1921.device._read_decode_output(),
                                  PASSING_PERCENTAGE_ACCURACY)
            readmock.side_effect = None

    def test_read_decode_output_power(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:

            # Set experimental values to be 'measured' by PAC1921
            real_power = 0.2  # 200mW

            # Configuration values for PAC1921
            di_gain = 8
            dv_gain = 8
            r_sense = 0.01

            # Init the device
            test_pac1921.device = PAC1921(i2c_address=0x5A,
                                          measurement_type=Measurement_Type.POWER,
                                          r_sense=r_sense)
            test_pac1921.device.config_gain(di_gain=di_gain, dv_gain=dv_gain)

            # Calculate the counter 1LSB value for this configuration
            lsb_val_W = ((0.1/(r_sense*di_gain)) * (32.0/dv_gain)) / (1023 * 64)    # From datasheet

            # Calculate the expected counter value if the input was real_power
            counter_val = int(real_power / lsb_val_W)
            print("Counter would be at {} to represent {}W".format(counter_val, real_power))

            # Mock the register reads to report the counter value, check the returned power is correct
            readmock.side_effect = lambda reg: {            # Set fake register to return expected count
                    0x1D: (counter_val & 0xFF00) >> 8,    # Upper result
                    0x1E: counter_val & 0xFF,             # Lower result
                    0x1C: 0b000}[reg]                               # Overflow status is none
            assert_within_percent(real_power, test_pac1921.device._read_decode_output(),
                                  PASSING_PERCENTAGE_ACCURACY)

    def test_read_decode_output_overflow(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:
            test_pac1921.device = PAC1921(i2c_address=0x5A, measurement_type=Measurement_Type.VBUS)

            # Check VSense overflow triggers error response with DI Gain suggestion
            with pytest.raises(OverflowException, match=".*DI_GAIN.*"):
                readmock.side_effect = lambda reg: {            # Force return of overflow flags
                        0x1C: 0b100}[reg]                               # Overflow status VSOV
                test_pac1921.device._read_decode_output()

            # Check VBus overflow triggers error response with DV Gain suggestion
            with pytest.raises(OverflowException, match=".*DV_GAIN.*"):
                readmock.side_effect = lambda reg: {            # Force return of overflow flags
                        0x1C: 0b010}[reg]                               # Overflow status VBOV
                test_pac1921.device._read_decode_output()

            # Check VPower overflow triggers error response with DV/DI Gain suggestion
            with pytest.raises(OverflowException) as err_info:
                readmock.side_effect = lambda reg: {            # Force return of overflow flags
                        0x1C: 0b001}[reg]                               # Overflow status VPOV
                test_pac1921.device._read_decode_output()
                assert(err_info.contains("DV_GAIN"))
                assert(err_info.contains("DI_GAIN"))

    def test_read_decode_output_no_measurement_type(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:

            # Init device without measurement type
            test_pac1921.device = PAC1921(i2c_address=0x5A)

            # Make sure overflow is not reported
            readmock.side_effect = lambda reg: {0x1C: 0b000}[reg]   # Overflow status is none

            with pytest.raises(ValueError, match=".*Measurement Type.*"):
                test_pac1921.device._read_decode_output()


    def test_config_pincontrol(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:

            # (Lack of gpiod module already has a test)

            # Check that lack of a supplied pin throws an error
            test_pac1921.device = PAC1921(i2c_address=0x5A,
                                          r_sense = 0.01,
                                          measurement_type=Measurement_Type.POWER)
            with pytest.raises(Exception, match=".*requires a nRead_int pin.*"):
                test_pac1921.device.config_pincontrol_integration_mode()

            # Re-configure with a pin for remaining tests
            temp_pin = MagicMock(spec=gpiod.Line)
            temp_pin.set_value = Mock()
            test_pac1921.device = PAC1921(i2c_address=0x5A,
                                          r_sense=0.01,
                                          nRead_int_pin=temp_pin,
                                          measurement_type=Measurement_Type.POWER)

            # Check that an invalid measurement mode for pin control throws an error
            test_pac1921.device.set_measurement_type(Measurement_Type.VBUS)
            with pytest.raises(Exception, match=".*measurement type.*"):
                test_pac1921.device.config_pincontrol_integration_mode()
            test_pac1921.device.set_measurement_type(Measurement_Type.POWER)

            # Check that an invalid integration time (depending on resolution) throws an error
            test_pac1921.device.config_resolution_filtering(adc_resolution=11)
            with pytest.raises(ValueError, match=".*11-bit.*integration time.*"):
                # 1500ms is not allowed for 11-bit, so throws an error
                test_pac1921.device.config_pincontrol_integration_mode(1500)
            test_pac1921.device.config_pincontrol_integration_mode(1) # Allowed for 11-bit, not 14-bit
            test_pac1921.device.config_resolution_filtering(adc_resolution=14)
            with pytest.raises(ValueError, match=".*14-bit.*integration time.*"):
                # 1ms is not allowed for 14-bit, so throws an error
                test_pac1921.device.config_pincontrol_integration_mode(1)
            test_pac1921.device.config_pincontrol_integration_mode(1500) # Allowed for 11-bit, not 14-bit

            # Check that integration mode / measurement type are set correctly in registers
            readmock.side_effect = lambda reg: {    # Set fake register to read as all 0
                    0x01: 0b00000000,                   # Sample rate read as 0b0000, => 1
                    0x02: 0b11000000}[reg]              # MXSL mode is read as VPower free-run
            writemock.reset_mock()
            test_pac1921.device.config_pincontrol_integration_mode()
            writemock.assert_any_call(0x02, 0b00000000)  # MXSL mode 0b00 is VBus pin-conrolled

            # (Integration time is checked in the pincontrol read() test)

            # Check that now pin-control is definitely selected, pin_control_enabled() is correct
            assert(test_pac1921.device.pin_control_enabled())

            # Check that the system is left in read mode
            assert(not test_pac1921.device._nRead_int_state)

    def test_config_freerun(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:

            # Init device with no pin in VBus mode
            test_pac1921.device = PAC1921(i2c_address=0x5A,
                                          r_sense = 0.01,
                                          measurement_type=Measurement_Type.VBUS)

            # Check that an invalid number of samples results in error
            with pytest.raises(KeyError, match=".*Number of samples.*"):
                test_pac1921.device.config_freerun_integration_mode(-3)

            # Check that the sample number is correctly written to registers
            readmock.side_effect = lambda reg: {    # Set fake register to read as all 0
                    0x01: 0b00000000,                   # Sample rate read as 0b0000, => 1
                    0x02: 0b00000000}[reg]              # MXSL mode is read as VPower pin-control
            writemock.reset_mock()
            test_pac1921.device.config_freerun_integration_mode(num_samples=64)
            writemock.assert_any_call(0x01, 0b01100000)  # Sample rate 0b0110 is 64 (datasheet)

            # Check that measurement type/integration mode is written correctly to registers
            readmock.side_effect = lambda reg: {    # Set fake register to read as all 0
                    0x01: 0b00000000,                   # Sample rate read as 0b0000, => 1
                    0x02: 0b00000000}[reg]              # MXSL mode is read as VPower pin-control
            writemock.reset_mock()
            test_pac1921.device.config_freerun_integration_mode(64)
            writemock.assert_any_call(0x02, 0b10000000)  # MXSL mode 0b10 is VBus free-run
            writemock.reset_mock()
            test_pac1921.device.set_measurement_type(Measurement_Type.CURRENT)
            test_pac1921.device.config_freerun_integration_mode(64)
            writemock.assert_any_call(0x02, 0b01000000)  # MXSL mode 0b01 is VSense free-run
            writemock.reset_mock()
            test_pac1921.device.set_measurement_type(Measurement_Type.POWER)
            test_pac1921.device.config_freerun_integration_mode(64)
            writemock.assert_any_call(0x02, 0b11000000)  # MXSL mode 0b11 is VPower free-run

            # Check that not supplying samples will result in the register not being written
            writemock.reset_mock()
            def check_samples_not_written(reg, val):
                if (reg == 0x01):
                    assert (val & 0b11110000) == 0, "Sample num bits were modified and shouldn't have been"
            writemock.side_effect = lambda reg, val: check_samples_not_written(reg, val)
            test_pac1921.device.config_freerun_integration_mode()   # Call without sample num

            # Check that device is left in integration mode so sampling is immediately possible
            assert(test_pac1921.device._nRead_int_state)

    def test_read_pincontrol(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()
        read_decode_mock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(PAC1921, '_read_decode_output') as read_decode_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:

            test_pac1921.device = PAC1921(i2c_address=0x5A, measurement_type=Measurement_Type.VBUS)

            # Test that if read() is called without any configuration, error raised
            with pytest.raises(Exception, match="Configuration has not been completed.*"):
                test_pac1921.device.read()

            # Init device, configure for pin control integration with given delay
            time_target_ms = 1000
            temp_pin = MagicMock(spec=gpiod.Line)
            temp_pin.set_value = Mock()
            test_pac1921.device = PAC1921(i2c_address=0x5A,
                                          measurement_type=Measurement_Type.POWER,
                                          r_sense=0.01,
                                          nRead_int_pin=temp_pin)
            test_pac1921.device.config_pincontrol_integration_mode(time_target_ms)

            # Check that the integration mode is entered and left using pin control
            pinset_read_mock = MagicMock()
            pinset_int_mock = MagicMock()
            with \
                    patch.object(PAC1921, '_pin_set_read') as pinset_read_mock, \
                    patch.object(PAC1921, '_pin_set_integration') as pinset_int_mock:
                test_pac1921.device.read()
                pinset_int_mock.assert_called()
                pinset_read_mock.assert_called()

            # Check that integration time is the time specified (rough, judged by return time)
            #time_before_ns = time.time_ns()
            time_before_s = time.time()
            test_pac1921.device.read()
            #time_after_ns = time.time_ns()
            time_after_s = time.time()
            assert_within_percent((time_after_s-time_before_s)*1000, time_target_ms, 1)

            # Check that the device is in read mode when readout takes place when started in read
            def assert_in_read_mode():
                assert (not test_pac1921.device._nRead_int_state), "Device was not in read mode"
            read_decode_mock.side_effect = lambda: assert_in_read_mode()
            test_pac1921.device._nRead_int_state = False
            test_pac1921.device.read()

            # Check that the device is in read mode when readout takes place when started in int
            def assert_in_read_mode2():
                assert (not test_pac1921.device._nRead_int_state), "Device was not in read mode"
            read_decode_mock.side_effect = lambda: assert_in_read_mode2()
            test_pac1921.device._nRead_int_state = True
            test_pac1921.device.read()


    def test_read_freerun(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()
        read_decode_mock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(PAC1921, '_read_decode_output') as read_decode_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:

            # Init device in voltage measurement mode
            test_pac1921.device = PAC1921(i2c_address=0x5A, measurement_type=Measurement_Type.VBUS)

            # Test that if read() is called without any configuration, error raised
            with pytest.raises(Exception, match="Configuration has not been completed.*"):
                test_pac1921.device.read()

            # Configure the freerun read mode without changing the current sample num
            test_pac1921.device.config_freerun_integration_mode()

            # Check that the read mode is entered using register control
            writemock.reset_mock()
            readmock.reset_mock()
            regset_read_mock = MagicMock()
            with patch.object(PAC1921, '_register_set_read') as regset_read_mock:
                test_pac1921.device.read()
                regset_read_mock.assert_called()

            # Check that read mode was entered before _read_decode_output() is called
            def assert_in_read_mode():
                assert (not test_pac1921.device._nRead_int_state), "Device was not in read mode"
            read_decode_mock.side_effect = lambda: assert_in_read_mode()
            test_pac1921.device.read()

            # Check that the device is left in integration mode for sampling to continue
            print(test_pac1921.device._nRead_int_state)
            assert(test_pac1921.device._nRead_int_state)

    def test_stop_freerun_integration(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:

            # Create device, enter freerun integration, and stop it again
            test_pac1921.device = PAC1921(i2c_address=0x5A, measurement_type=Measurement_Type.VBUS)
            test_pac1921.device.config_freerun_integration_mode()
            test_pac1921.device.stop_freerun_integration()

            # Check that device is placed into read mode to stop integration
            assert(not test_pac1921.device._nRead_int_state)

            # Check that the configuration is now invalid, and read() cannot be called
            with pytest.raises(Exception, match="Configuration has not been completed.*"):
                test_pac1921.device.read()

    def test_syncarr_init(self, test_pac1921):
        # Check that supplying an invalid pin results in failure
        with pytest.raises(TypeError, match="nRead_int_pin should be of type gpiod.Line.*"):
            test_array = PAC1921_Synchronised_Array(nRead_int_pin=3, integration_time_ms=500)

        # (Lack of support when gpiod is not present is tested elsewhere)

    def test_syncarr_add_devices_basicchecks(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()

        with patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:

            temp_pin = MagicMock(spec=gpiod.Line)
            temp_pin.set_value = Mock()
            test_array = PAC1921_Synchronised_Array(nRead_int_pin = temp_pin,
                                                    integration_time_ms = 500)
            # Check that device type is tested
            with pytest.raises(TypeError, match=".*PAC1921.*"):
                not_a_pac1921 = 3
                test_array.add_device(not_a_pac1921)

            # Check that device mode must be pin control
            first_pac1921 = PAC1921(i2c_address=0x5A, measurement_type=Measurement_Type.VBUS)
            first_pac1921.config_freerun_integration_mode()     # Put device in freerun int mode
            with pytest.raises(Exception, match=".*pin-controlled integration.*"):
                test_array.add_device(first_pac1921)

            # Check that adding devices manually is the same as adding via init
            first_pac1921 = PAC1921(i2c_address=0x5A, r_sense=0.01, measurement_type=Measurement_Type.POWER)
            second_pac1921 = PAC1921(i2c_address=0x5B, r_sense=0.01, measurement_type=Measurement_Type.POWER)
            third_pac1921 = PAC1921(i2c_address=0x5B, r_sense=0.01, measurement_type=Measurement_Type.POWER)

            init_array = PAC1921_Synchronised_Array(temp_pin, 500, [first_pac1921, second_pac1921, third_pac1921])
            after_array = PAC1921_Synchronised_Array(temp_pin, 500)

            after_array.add_device(first_pac1921)
            after_array.add_device(second_pac1921)
            after_array.add_device(third_pac1921)
            assert(init_array._device_list == after_array._device_list)

            # Check that get_names matches supplied names for devices
            assert(first_pac1921._name in init_array.get_names())
            assert(second_pac1921._name in init_array.get_names())
            assert(third_pac1921._name in init_array.get_names())
            assert(len(init_array.get_names()) == 3)

    def test_syncarr_integration(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()

        with patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:

            temp_array_pin = MagicMock(spec=gpiod.Line)
            temp_array_pin.set_value = Mock()

            # Prevent reports of overflows and r/w errors on device reads
            readmock.side_effect = lambda reg: {            # Force return of overflow flags
                    0x00: 0,                                        # Read config as 0
                    0x01: 0,                                        # Read config as 0
                    0x02: 0,                                        # Read config as 0
                    0x1D: 0,                                        # Result as 0 (irrelevant)
                    0x1E: 0,                                        # Result as 0 (irrelevant)
                    0x1C: 0b000}[reg]                               # Overflow status None

            # Check that the array integration time supplied at init affects the function duration
            time_target_ms = 900
            test_device = PAC1921(i2c_address=0x5A, r_sense=0.01, measurement_type=Measurement_Type.POWER)
            test_array = PAC1921_Synchronised_Array(nRead_int_pin=temp_array_pin,
                                                    integration_time_ms=time_target_ms,
                                                    device_list=[test_device])
            time_before_s = time.time()
            test_array.read_devices()
            time_after_s = time.time()
            assert_within_percent((time_after_s-time_before_s)*1000, time_target_ms, 1)

            # Check that the integration time adjustment function updates the function time
            test_array.set_integration_time(300)
            time_before_s = time.time()
            test_array.read_devices()
            time_after_s = time.time()
            assert_within_percent((time_after_s-time_before_s)*1000, 300, 1)

            # Check that if pins are supplied after init they still inherit the desired duration
            time_target_ms = 900
            test_array = PAC1921_Synchronised_Array(nRead_int_pin=temp_array_pin,
                                                    integration_time_ms=time_target_ms,
                                                    device_list=None)
            test_array.add_device(test_device)      # Device will have default integration time 500ms
            time_before_s = time.time()
            test_array.read_devices()
            time_after_s = time.time()
            assert_within_percent((time_after_s-time_before_s)*1000, time_target_ms, 1)

            # Check that the correct pin is used for integration, no matter what pins were assigned
            # previously to the devices
            temp_WRONG_pin = MagicMock(spec=gpiod.Line)
            temp_WRONG_pin.set_value = Mock()
            test_device = PAC1921(i2c_address=0x5A, r_sense=0.01, nRead_int_pin=temp_WRONG_pin,
                                  measurement_type=Measurement_Type.POWER)
            test_array = PAC1921_Synchronised_Array(nRead_int_pin=temp_array_pin,
                                                    integration_time_ms=time_target_ms,
                                                    device_list=[test_device])
            temp_array_pin.reset_mock()
            temp_WRONG_pin.reset_mock()
            test_array.read_devices()
            temp_array_pin.set_value.assert_any_call(1)     # Correct pin was toggled
            temp_array_pin.set_value.assert_any_call(0)
            temp_WRONG_pin.set_value.assert_not_called()    # Wrong pin was not moved

            # Check that supplying an incorrect integration time will still be caught (mechanism tested
            # in more depth elsewhere)
            with pytest.raises(ValueError):
                test_array.set_integration_time(10000)

    def test_syncarr_read(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:

            # Prevent reports of overflows and r/w errors on device reads
            readmock.side_effect = lambda reg: {            # Force return of overflow flags
                    0x00: 0,                                        # Read config as 0
                    0x01: 0,                                        # Read config as 0
                    0x02: 0,                                        # Read config as 0
                    0x1C: 0b000}[reg]                               # Overflow status None

            # Check that a lack of devices throws a error
            temp_array_pin = MagicMock(spec=gpiod.Line)
            temp_array_pin.set_value = Mock()
            test_array = PAC1921_Synchronised_Array(nRead_int_pin=temp_array_pin,
                                                    integration_time_ms=500,
                                                    device_list=None)
            with pytest.raises(Exception, match=".*No devices.*"):
                test_array.read_devices()

            # Check that measurements from each device are reported and associated with the correct device
            dev1_read_mock = Mock(); dev1_read_mock.return_value = 1.0
            dev2_read_mock = Mock(); dev2_read_mock.return_value = 2.0
            dev3_read_mock = Mock(); dev3_read_mock.return_value = 3.0
            test_device1 = PAC1921(i2c_address=0x5A, r_sense=0.01, measurement_type=Measurement_Type.POWER)
            test_device2 = PAC1921(i2c_address=0x5B, r_sense=0.01, measurement_type=Measurement_Type.POWER)
            test_device3 = PAC1921(i2c_address=0x5C, r_sense=0.01, measurement_type=Measurement_Type.POWER)
            test_device1._read_decode_output = dev1_read_mock
            test_device2._read_decode_output = dev2_read_mock
            test_device3._read_decode_output = dev3_read_mock
            test_array.add_device(test_device1)
            test_array.add_device(test_device2)
            test_array.add_device(test_device3)
            names_out, readout = test_array.read_devices()
            print(names_out, readout)
            assert(readout[names_out.index(test_device1.get_name())] == 1.0)
            assert(readout[names_out.index(test_device2.get_name())] == 2.0)
            assert(readout[names_out.index(test_device3.get_name())] == 3.0)

    def test_no_gpiod(self, test_pac1921):

        # Make sure this is the last test; it WILL mess with imports...

        with patch.dict('sys.modules', gpiod=None):
            # Remove gpiod module and re-run the initial include process for pac1921
            reload(odin_devices.pac1921)
            from odin_devices.pac1921 import PAC1921 as PAC1921_tmp

            writemock = MagicMock()
            readmock = MagicMock()

            with \
                    patch.object(PAC1921_tmp, '_check_prodid_manufacturer') as prodid_success_mock, \
                    patch.object(I2CDevice, 'write8') as writemock, \
                    patch.object(I2CDevice, 'readU8') as readmock:

                # Create the device instance
                my_pac1921 = PAC1921_tmp(i2c_address=0x5A)

                # Check that lack of gpiod throws error on pin control config
                with pytest.raises(RuntimeError, match=".*gpiod module not available.*"):
                    my_pac1921.config_pincontrol_integration_mode()

                # Check that lack of gpiod throws error on init of array
                with pytest.raises(RuntimeError, match=".*gpiod module not available.*"):
                    my_array = PAC1921_Synchronised_Array(None, 500)
