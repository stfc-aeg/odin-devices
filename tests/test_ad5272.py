"""Test Cases for the AD5272 class from odin_devices
Adam Neaves, STFC Detector Systems Software Group
"""

import sys

import pytest

if sys.version_info[0] == 3:  # pragma: no cover
    from unittest.mock import MagicMock, call
else:                         # pragma: no cover
    from mock import MagicMock, call

sys.modules['smbus'] = MagicMock()
from odin_devices.ad5272 import AD5272
from odin_devices.i2c_device import I2CDevice, I2CException


class ad5272TestFixture(object):
    """Container class used in fixtures for testing driver behaviour"""

    def __init__(self):
        self.driver = AD5272()


@pytest.fixture(scope="class")
def test_ad5272_driver():
    """Fixture used in driver test cases"""

    test_driver_fixture = ad5272TestFixture()
    yield test_driver_fixture


class TestAD5272():

    def test_fake(self, test_ad5272_driver):
        # dummy test case as placeholder
        assert True
