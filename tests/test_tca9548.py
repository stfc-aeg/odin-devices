"""Test TCA9548 class from odin_devices.

Tim Nicholls, STFC Application Engineering Group
"""

import sys

import pytest

if sys.version_info[0] == 3:  # pragma: no cover
    from unittest.mock import Mock, call
else:                         # pragma: no cover
    from mock import Mock, call

sys.modules['smbus'] = Mock()
from odin_devices.tca9548 import TCA9548
from odin_devices.i2c_device import I2CDevice, I2CException


class tca9548TestFixture():

    def __init__(self):
        self.tca = TCA9548()
        self.tca_callback = Mock()
        self.tca.pre_access = self.tca_callback


@pytest.fixture(scope="class")
def test_tca9548_driver():
    driver_fixture = tca9548TestFixture()
    yield driver_fixture


class TestTCA9548():

    def test_tca_write(self, test_tca9548_driver):

        test_tca9548_driver.tca.write8(0, 123)

    def test_attach_device(self, test_tca9548_driver):

        line = 1
        address = 0x20
        device = test_tca9548_driver.tca.attach_device(line, I2CDevice, address)

        assert device.address == address
        assert device in test_tca9548_driver.tca._attached_devices
        assert test_tca9548_driver.tca._attached_devices[device] == line

    def test_attach_bad_device(self, test_tca9548_driver):

        line = 1
        address = 0x20

        class DummyDevice(object):
            def __init__(self, *args, **kwargs):
                pass

        exc_message = 'must be a type or an instance of I2CDevice or I2CContainer'
        with pytest.raises(I2CException) as excinfo:
            test_tca9548_driver.tca.attach_device(line, DummyDevice, address)

            assert exc_message in excinfo.value

    def test_remove_device(self, test_tca9548_driver):

        device = test_tca9548_driver.tca.attach_device(1, I2CDevice, 0x20)

        test_tca9548_driver.tca.remove_device(device)
        assert device not in test_tca9548_driver.tca._attached_devices

    def test_remove_missing_device(self, test_tca9548_driver):

        device_not_attached = I2CDevice(0x20)

        exc_message = 'Device %s is not attached to this TCA' % device_not_attached
        with pytest.raises(I2CException) as excinfo:
            test_tca9548_driver.tca.remove_device(device_not_attached)

            assert exc_message in excinfo.value

    def test_pre_access_callback_called(self, test_tca9548_driver):

        line = 1
        address = 0x20
        device = test_tca9548_driver.tca.attach_device(line, I2CDevice, address)

        device.write8(0, 1)

        test_tca9548_driver.tca_callback.assert_called_with(test_tca9548_driver.tca)

    def test_pre_access_callback_incomplete_detach(self, test_tca9548_driver):

        line = 1
        address = 0x20
        device = test_tca9548_driver.tca.attach_device(line, I2CDevice, address)

        del test_tca9548_driver.tca._attached_devices[device]

        exc_message = 'Device %s was not properly detached from the TCA' % device
        with pytest.raises(I2CException) as excinfo:
            device.write8(0, 1)

            assert exc_message in excinfo.value

    def test_pre_access_selects_tca_line(self, test_tca9548_driver):

        device1_line = 1
        device1_address = 0x20
        device2_line = 2
        device2_address = 0x21

        device1 = test_tca9548_driver.tca.attach_device(device1_line, I2CDevice, device1_address)
        device2 = test_tca9548_driver.tca.attach_device(device2_line, I2CDevice, device2_address)

        device1.write8(0, 1)
        assert test_tca9548_driver.tca._selected_channel == device1_line

        device2.write8(1, 2)
        assert test_tca9548_driver.tca._selected_channel == device2_line
