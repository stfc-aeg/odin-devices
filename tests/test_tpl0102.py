"""Test Cases for the TPL0102 class from odin_devices
Adam Neaves, STFC Detector Systems Software Group
"""

import sys

import pytest

if sys.version_info[0] == 3:  # pragma: no cover
    from unittest.mock import Mock, call
else:                         # pragma: no cover
    from mock import Mock, call

sys.modules['smbus'] = Mock()
from odin_devices.tpl0102 import TPL0102
from odin_devices.i2c_device import I2CDevice, I2CException


class tpl0102TestFixture(object):

    def __init__(self):
        self.driver = TPL0102()


@pytest.fixture(scope="class")
def test_tpl0102_driver():
    test_driver = tpl0102TestFixture()
    yield test_driver


class TestTPL0102():

    def test_fake(self, test_tpl0102_driver):
        # dummy test case as placeholder
        assert True
