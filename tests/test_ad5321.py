"""Test cases for the AD5321 class from odin_devices.
Tim Nicholls, STFC Detector Systems Software Group
Adam Neaves, STFC Detector Systems Software Group
"""

import sys

import pytest

if sys.version_info[0] == 3:  # pragma: no cover
    from unittest.mock import Mock, call
else:                         # pragma: no cover
    from mock import Mock, call

sys.modules['smbus'] = Mock()
from odin_devices.ad5321 import AD5321
from odin_devices.i2c_device import I2CDevice, I2CException


class ad5321TestFixture(object):
    """Container class used in fixtures for testing driver behaviour"""

    def __init__(self):
        self.address = 0xc
        self.driver = AD5321(self.address)


@pytest.fixture(scope="class")
def test_ad5321_driver():
    """Fixture used in driver test cases"""

    test_driver_fixture = ad5321TestFixture()
    yield test_driver_fixture


class TestAD5321():

    def test_set_output(self, test_ad5321_driver):

        # Output = 0.75 FS = 3072 ADU, = MSB 0xC, LSB 0x0

        output = 0.75
        msb = 0xc
        lsb = 0
        test_ad5321_driver.driver.set_output_scaled(output)
        test_ad5321_driver.driver.bus.write_byte_data.assert_called_with(
            test_ad5321_driver.address,
            msb, lsb)

    def test_set_output_full_scale(self, test_ad5321_driver):

        output = 1.0
        msb = 0xF
        lsb = 0xFF

        test_ad5321_driver.driver.set_output_scaled(output)
        test_ad5321_driver.driver.bus.write_byte_data.assert_called_with(
            test_ad5321_driver.address,
            msb, lsb)

    def test_set_output_lt_zero(self, test_ad5321_driver):

        output = -0.75

        with pytest.raises(I2CException) as excinfo:
            test_ad5321_driver.driver.set_output_scaled(output)

            assert 'Illegal output value {} specified'.format(output) in excinfo.value

    def test_set_output_gt_one(self, test_ad5321_driver):

        output = 1.1

        with pytest.raises(I2CException) as excinfo:
            test_ad5321_driver.driver.set_output_scaled(output)

            assert 'Illegal output value {} specified'.format(output) in excinfo.value

    def test_read_value(self, test_ad5321_driver):

        # Patch to return value of 0.5 = 2048 ADU = 0x0800, byte swapped to 0x0008
        test_ad5321_driver.driver.bus.read_word_data.return_value = 0x0008

        value = test_ad5321_driver.driver.read_value_scaled()
        assert value == 0.5
