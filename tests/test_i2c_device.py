"""Test cases for the I2CTContainer class from odin_devices.
Tim Nicholls, STFC Application Engineering Group
"""

import sys

import pytest

if sys.version_info[0] == 3:  # pragma: no cover
    from unittest.mock import Mock, MagicMock, call
else:                         # pragma: no cover
    from mock import Mock, MagicMock, call

smbus_mock = MagicMock()
sys.modules['smbus'] = smbus_mock

from odin_devices.i2c_device import I2CDevice, I2CException


class dummy_cm():
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class I2CDeviceTestFixture(object):
    """Container class used in fixtures for testing driver behaviour"""

    def __init__(self):
        self.device_busnum = 1
        self.device_address = 0x70
        self.device_debug = True
        self.device = I2CDevice(self.device_address, self.device_busnum, self.device_debug)
        self.device.pre_access = Mock()


@pytest.fixture(scope="class")
def test_i2c_device():
    """Fixture used in driver test cases"""

    test_i2c_fixture = I2CDeviceTestFixture()
    yield test_i2c_fixture


class TestI2CDevice(object):

    EXC_MODE_NONE, EXC_MODE_TRAP, EXC_MODE_RAISE = range(3)
    EXC_MODES = [EXC_MODE_NONE, EXC_MODE_TRAP, EXC_MODE_RAISE]
    EXC_MODE_NAME = ['exception_mode_none', 'exception_mode_trap', 'exception_mode_raise']

    # @classmethod
    # def setup_class(cls):

    #     cls.device_busnum = 1
    #     cls.device_address = 0x70
    #     cls.device_debug = True
    #     cls.device = I2CDevice(cls.device_address, cls.device_busnum, cls.device_debug)
    #     cls.device.pre_access = Mock()

    def test_device_init(self, test_i2c_device):

        assert test_i2c_device.device_address == test_i2c_device.device.address
        assert test_i2c_device.device_busnum  == test_i2c_device.device.busnum
        assert test_i2c_device.device_debug   == test_i2c_device.device.debug

    def test_change_default_bus(self, test_i2c_device):

        default_i2c_bus = 0
        I2CDevice.set_default_i2c_bus(default_i2c_bus)

        new_device = I2CDevice(test_i2c_device.device_address, debug=test_i2c_device.device_debug)
        assert default_i2c_bus == new_device.busnum

    def test_pre_access_called(self, test_i2c_device):

        test_i2c_device.device.write8(1, 20)
        test_i2c_device.device.pre_access.assert_called_with(test_i2c_device.device)

    def test_enable_exceptions(self, test_i2c_device):

        test_i2c_device.device.enable_exceptions()
        assert test_i2c_device.device._enable_exceptions

    def test_disable_exceptions(self, test_i2c_device):

        test_i2c_device.device.disable_exceptions()
        assert not test_i2c_device.device._enable_exceptions

    @pytest.mark.parametrize("exc_mode", EXC_MODES)
    @pytest.mark.parametrize(
        "method, smbus_method, args, exp_rc",
        [
            ('write8', 'write_byte_data', (1, 0x70), None),
            ('write16', 'write_word_data', (2, 0x12), None),
            ('writeList', 'write_i2c_block_data', (3, [1, 2, 3, 4]), None),
            ('readU8', 'read_byte_data', (4,), 0xab),
            ('readS8', 'read_byte_data', (5,), -127),
            ('readU16', 'read_word_data', (6,), 0x1234),
            ('readS16', 'read_word_data', (7,), 0x4567),
            ('readList', 'read_i2c_block_data', (8, 4), [1000, 1001, 1002, 1003])
        ]
    )
    def test_device_access(self, method, smbus_method, exc_mode, args, exp_rc, test_i2c_device):

        cached_side_effect = getattr(test_i2c_device.device.bus, smbus_method).side_effect

        if exc_mode == self.EXC_MODE_NONE:
            side_effect = None
            exc_enable = False
            getattr(test_i2c_device.device.bus, smbus_method).return_value = exp_rc
        elif exc_mode == self.EXC_MODE_TRAP:
            side_effect = IOError('mocked error')
            exc_enable = False
            exp_rc = I2CDevice.ERROR
        elif exc_mode == self.EXC_MODE_RAISE:
            side_effect = IOError('mocked error')
            exc_enable = True
        else:
            raise Exception('Illegal exception test mode {}'.format(exc_mode))

        getattr(test_i2c_device.device.bus, smbus_method).side_effect = side_effect
        test_i2c_device.device.enable_exceptions() if exc_enable else test_i2c_device.device.disable_exceptions()

        rc = None
        exception_message = 'error from device'

        if exc_enable:
            with pytest.raises(I2CException) as excinfo:
                rc = getattr(test_i2c_device.device, method)(*args)
                assert rc == exp_rc
                assert exception_message in excinfo.value
        else:
            with dummy_cm():
                rc = getattr(test_i2c_device.device, method)(*args)
                assert rc == exp_rc

        getattr(test_i2c_device.device.bus, smbus_method).side_effect = cached_side_effect
