"""
Tests for PAC1921 power monitors. The driver is I2CDevice-derived.

To Test:
    - [x] Address assignment with direct allocation and resistance
    - [x] Prodid manufacturer tests check right area and raise error on fail
    - [x] Invalid measurement type supplied to init raises error
    - [x] Not supplying a pin does not cause error, but uses register read functions
    - [ ] Check read and integration mode triggers work for both pin mode an register mode
    - [ ] Register read/write functionality method is correct for bitfields (read-modify-write)
    - [x] Functions exporting mode info is correct: pin_control_enabled, get_name, get_address...
    - Pin Control Mode
        - [ ] Check that the integration time is held for the correct duration on trigger
        - [ ] Check that the pin is toggled on trigger
    - Readout
        - [ ] Check that example values (using datasheet examples) are read out correctly for
                each mode
        - [ ] Check that overflows are caught, and result in warnings
        - [ ] Check that the read function cannot be called without configuring first
        - [ ] Check that if in freerun mode, reading will re-enter integration automatically
    - ADC and Filtering Configuration
        - [ ] Check that adc resolution is set correctly, and takes only valid values
        - [ ] Check that post filtering is set correctly, and takes only valid values
        - [ ] Check that integration mode is re-entered in whatever mode is being used so that
                the changes take effect
    - Gain Configuration
        - [x] Check that di and dv gain are set correctly, and take only valid values
        - [x] Check that integration mode is re-entered in whatever mode is being used so that
                the changes take effect
    - [ ] Check that forcing the config update will update the chip with internally stored values
            for the ADC sampling, post filtering, dv and di gain
    - [ ] FreeRun Configuration
        - [ ] Check that an invalid number of samples is caught, and a correct number of samples
                results in registers being set correctly.
        - [ ] Check that the mode is sent correctly to the device
        - [ ] Check that the integration is actually started immediately
        - [ ] Check that stopping free-run integration actually stops it, and stops read() from
                being called successfully.
    - [ ] Pin Control Config
        - [ ] Check that lack of a read interrupt pin will result in failure
        - [ ] Check that measurement is power
        - [ ] Check that integration time is 'allowed' based on di or dv resolution
        - [ ] Make sure that the system is primed in read mode by pin control
        - [ ] Make sure that the measurement type is set, with pin control mode
    - [ ] Check that setting a new measurement type means read cannot be activated until a control
            mode is configured
    - Synchronised Array
        - [ ]
"""

import sys
import pytest

if sys.version_info[0] == 3:                # pragma: no cover
    from unittest.mock import Mock, MagicMock, call, patch
else:                                       # pragma: no cover
    from mock import Mock, MagicMock, call, patch

sys.modules['smbus'] = MagicMock()
sys.modules['gpiod.Line'] = MagicMock()
from odin_devices.pac1921 import PAC1921
import smbus
from odin_devices.i2c_device import I2CDevice
import gpiod

prodid_success_mock = MagicMock()

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

            # Check that if no resistance or address is supplied that an error is raised
            with pytest.raises(ValueError, match=".*Either an I2C address or address resistance value must be supplied.*"):
                test_pac1921.device = PAC1921()

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

            # Test that if a pin is supplied, the device is put into read mode with pin control
            try:
                writemock.reset_mock()     # Reset i2c write record
                readmock.return_value = 0xFF                    # Read from registers will always be all 1's
                test_pac1921.device = PAC1921(i2c_address=0x5A, nRead_int_pin=temp_pin)
                writemock.assert_any_call(1, 0b11111101)        # Assert register control was disabled (bit 1 low)
                temp_pin.set_value.assert_called_with(0)        # Assert pin control read entered
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
            # TODO

            # Test that an invalid post_filter_en value raises an error
            with pytest.raises(ValueError):
                test_pac1921.device.config_resolution_filtering(post_filter_en=10)

            # Test that enabling the post filter writes correct bytes
            # TODO

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

