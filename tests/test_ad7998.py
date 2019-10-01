"""Test cases for the AD7998 class from odin_devices.
Tim Nicholls, STFC Detector Systems Software Group
Adam Neaves, STFC Detector Systems Software Group
"""

import sys

import pytest

if sys.version_info[0] == 3:  # pragma: no cover
    from unittest.mock import Mock
else:                         # pragma: no cover
    from mock import Mock

sys.modules['smbus'] = Mock()
from odin_devices.ad7998 import AD7998
from odin_devices.i2c_device import I2CException


class ad7998TestFixture(object):
    """Container class used in fixtures for testing driver behaviour"""

    def __init__(self):
        self.address = 0x20
        self.driver = AD7998(self.address)

    def set_read_return_value(self, value):
        self.driver.bus.read_word_data.return_value = value


@pytest.fixture(scope="class")
def test_ad7998_driver():
    """Fixture used in driver test cases"""

    test_driver_fixture = ad7998TestFixture()
    yield test_driver_fixture


class TestAD7998():

    # def set_read_return_value(self, value):

    #     self.ad7998.bus.read_word_data.return_value = value

    def test_init_sets_cycle_register(self, test_ad7998_driver):

        test_ad7998_driver.driver.bus.write_byte_data.assert_called_with(
            test_ad7998_driver.address,
            3, 1)

    def test_read_raw(self, test_ad7998_driver):

        channel = 1
        test_ad7998_driver.set_read_return_value(0x3412)

        val = test_ad7998_driver.driver.read_input_raw(channel)
        assert val == 0x1234

    def test_read_raw_illegal_channel(self, test_ad7998_driver):

        channel = 12
        with pytest.raises(I2CException) as excinfo:
            val = test_ad7998_driver.driver.read_input_raw(channel)

            assert "Illegal channel {} requested".format(channel) in excinfo.value

    def test_read_input_scaled_fs(self, test_ad7998_driver):

        channel = 1
        test_ad7998_driver.set_read_return_value(0xff1f)

        val = test_ad7998_driver.driver.read_input_scaled(channel)
        assert val == 1.0

    def test_read_input_scaled_zero(self, test_ad7998_driver):

        channel = 2
        test_ad7998_driver.set_read_return_value(0x0020)

        val = test_ad7998_driver.driver.read_input_scaled(channel)
        assert val == 0.0

    def test_read_input_scaled_midscale(self, test_ad7998_driver):

        channel = 7
        test_ad7998_driver.set_read_return_value(0x0078)

        val = test_ad7998_driver.driver.read_input_scaled(channel)
        assert val == 2048.0 / 4095.0
