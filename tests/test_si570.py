"""Test Cases for the SI570 class from odin_devices
Adam Neaves, STFC Detector Systems Software Group
"""

import sys

import pytest

if sys.version_info[0] == 3:  # pragma: no cover
    from unittest.mock import Mock, call
else:                         # pragma: no cover
    from mock import Mock, call

sys.modules['smbus'] = Mock()
from odin_devices.si570 import SI570
from odin_devices.i2c_device import I2CDevice, I2CException


class si570TestFixture(object):

    def __init__(self):
        self.driver = SI570()


@pytest.fixture(scope="class")
def test_si570_driver():
    test_fixture = si570TestFixture()
    yield test_fixture


class TestSI570():

    @pytest.mark.skip(reason="Getting an out of index error")
    def test_fake(self, test_si570_driver):
        # dummy test case as placeholder
        assert True
