"""Test cases for the I2CTContainer class from odin_devices.
Tim Nicholls, STFC Application Engineering Group
"""

import sys

import pytest

if sys.version_info[0] == 3:  # pragma: no cover
    from unittest.mock import Mock, call
else:                         # pragma: no cover
    from mock import Mock, call

sys.modules['smbus'] = Mock()
from odin_devices.i2c_device import I2CDevice, I2CException
from odin_devices.i2c_container import I2CContainer


class I2CContainerTestFixture(object):
    """Container class used in fixtures for testing driver behaviour"""

    def __init__(self):
        self.container = I2CContainer()
        self.container.pre_access = Mock()


@pytest.fixture(scope="class")
def test_i2c_container():
    """Fixture used in driver test cases"""

    test_container_fixture = I2CContainerTestFixture()
    yield test_container_fixture


class TestI2CContainer():

    def test_attach_new_device(self, test_i2c_container):

        device = test_i2c_container.container.attach_device(I2CDevice, 0x20)
        assert device in test_i2c_container.container._attached_devices

    def test_attach_existing_device(self, test_i2c_container):

        device = I2CDevice(0x21)
        test_i2c_container.container.attach_device(device)
        assert device in test_i2c_container.container._attached_devices

    def test_attach_bad_device(self, test_i2c_container):

        class DummyDevice(object):
            def __init__(self, *args, **kwargs):
                pass

        assert_message = 'must be of type or an instance of I2CDevice or I2CContainer'
        with pytest.raises(I2CException) as excinfo:

            test_i2c_container.container.attach_device(DummyDevice, 0x20)

            assert assert_message in excinfo

    def test_device_callback_called(self, test_i2c_container):

        device = test_i2c_container.container.attach_device(I2CDevice, 0x22)
        device.write8(0, 1)
        test_i2c_container.container.pre_access.assert_called_with(test_i2c_container.container)

    def test_remove_device(self, test_i2c_container):

        device = test_i2c_container.container.attach_device(I2CDevice, 0x23)

        test_i2c_container.container.remove_device(device)
        assert device not in test_i2c_container.container._attached_devices

    def test_remove_missing_device(self, test_i2c_container):

        device = I2CDevice(0x24)

        assert_message = 'Device %s was not attached to this I2CContainer' % device
        with pytest.raises(I2CException) as excinfo:
            test_i2c_container.container.remove_device(device)

            assert assert_message in excinfo.value
