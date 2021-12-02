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
    - [ ] FreeRun Configuration
        - [ ] Check that an invalid number of samples is caught, and a correct number of samples
                results in registers being set correctly.
        - [ ] Check that the mode is sent correctly to the device
        - [ ] Check that the integration is actually started immediately
        - [x] Check that stopping free-run integration actually stops it, and stops read() from
                being called successfully.
    - [ ] Pin Control Config
        - [x] Check that lack of a read interrupt pin will result in failure
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
import time

if sys.version_info[0] == 3:                # pragma: no cover
    from unittest.mock import Mock, MagicMock, call, patch
    from importlib import reload as reload
else:                                       # pragma: no cover
    from mock import Mock, MagicMock, call, patch

sys.modules['smbus'] = MagicMock()
sys.modules['gpiod.Line'] = MagicMock()
import odin_devices.pac1921                 # Needed so that module can be reloaded
from odin_devices.pac1921 import PAC1921, Measurement_Type, OverflowException
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
        #TODO
        pass

    def test_config_freerun(self, test_pac1921):
        #TODO
        pass

    def test_read_pincontrol(self, test_pac1921):
        writemock = MagicMock()
        readmock = MagicMock()
        read_decode_mock = MagicMock()

        with \
                patch.object(PAC1921, '_check_prodid_manufacturer') as prodid_success_mock, \
                patch.object(PAC1921, '_read_decode_output') as read_decode_mock, \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readU8') as readmock:

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

    def test_no_gpiod(self, test_pac1921):

        # Make sure this is the last test; it may mess with imports...

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
