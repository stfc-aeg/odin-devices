"""Test Cases for the AD5694 class from odin_devices
Adam Neaves, STFC Detector Systems Software Group
"""

import sys

import pytest

if sys.version_info[0] == 3:  # pragma: no cover
    from unittest.mock import Mock, call
else:                         # pragma: no cover
    from mock import Mock, call

sys.modules['smbus'] = Mock()
from odin_devices.ad5694 import AD5694
from odin_devices.i2c_device import I2CDevice, I2CException


class ad5694TestFixture(object):
    """Container class used in fixtures for testing driver behaviour"""

    def __init__(self):
        self.address = 0xc
        self.driver = AD5694(self.address)


@pytest.fixture(scope="class")
def test_ad5694_driver():
    """Fixture used in driver test cases"""

    test_driver_fixture = ad5694TestFixture()
    yield test_driver_fixture


class TestAD5694():

    def test_fake(self, test_ad5694_driver):
        # dummy test case as placeholder
        assert True
