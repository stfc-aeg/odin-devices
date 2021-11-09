"""
Tests for PAC1921 power monitors. The driver is I2CDevice-derived.

To Test:
    - [ ] Address assignment with direct allocation and resistance
    - [ ] Prodid manufacturer tests check right area and raise error on fail
    - [ ] Invalid measurement type supplied to init raises error
    - [ ] Not supplying a pin does not cause error, but uses register read functions
    - [ ] Check read and integration mode triggers work for both pin mode an register mode
    - [ ] Register read/write functionality method is correct for bitfields (read-modify-write)
    - [ ] Functions exporting mode info is correct: pin_control_enabled, get_name, get_address...
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
        - [ ] Check that di and dv gain are set correctly, and take only valid values
        - [ ] Check that integration mode is re-entered in whatever mode is being used so that
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

from odin_devices.pac1921 import PAC1921


class pac1921_test_fixture(object):
    def __init__(self):
        # Temporarily bypassed so that it does nto stop init
        PAC1921._check_prodid_manufacturer = Mock()

        self.device = PAC1921(i2c_address = 0x5A)
        self.device.i2c_bus = Mock()

@pytest.fixture(scope="class")
def test_pac1921():
    test_driver_fixture = pac1921_test_fixture()
    yield test_driver_fixture


class TestPAC1921():
    def test_address_assignment(self, test_pac1921):
        # Test the I2C device is created when an address is supplied directly
        test_pac1921.device = PAC1921(i2c_address=0x5A)
        assert(test_pac1921.device._i2c_device.address == 0x5A)

        # Test the I2C device is created when a resistance is supplied
        # TODO

        # Check that if no resistance or address is supplied that an error is raised
        with pytest.raises(ValueError, match=".*Either an I2C address or address resistance value must be supplied.*"):
            test_pac1921.device = PAC1921()
