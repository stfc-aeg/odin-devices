"""Test cases for AD5676 class from odin_devices.
Mika Shearwood, STFC Detector Systems Software Group Apprentice.
"""

import sys
import pytest

if sys.version_info[0] == 3:
    from unittest.mock import Mock, MagicMock, call
else:
    from mock import Mock, MagicMock, call

spidev_mock = MagicMock()
sys.modules['spidev'] = spidev_mock

from odin_devices.ad5676 import AD5676R


class AD5676DeviceTestFixture(object):
    """Container class used in fixtures for testing driver behaviour."""

    def __init__(self):
        self.device = AD5676R()

    def set_transfer_return_value(self, value):
        self.device.spi.xfer2.return_value = value


@pytest.fixture(scope="class")
def test_ad5676_device():
    """Fixture used in device test cases."""

    test_ad5676_fixture = AD5676DeviceTestFixture()
    yield test_ad5676_fixture


class TestAD5676Device(object):

    def test_init_settings(self, test_ad5676_device):

        assert test_ad5676_device.device.spi.mode == 1
        assert len(test_ad5676_device.device.buffer) == 3
        assert test_ad5676_device.device.Vref == 2.5

    def test_input_register_write(self, test_ad5676_device):

        test_ad5676_device.device.input_register_write(register=1, voltage=2.5)
        # Voltage conversion (voltage/2.5 * 0xFFFF). 2.5V = 0xFFFF
        # The command byte is 0x11, msb = 0xFF, lsb = 0xFF
        test_ad5676_device.device.spi.writebytes2.assert_called_with(
            bytearray([0x11, 0xff, 0xff]))

    def test_input_into_dac(self, test_ad5676_device):

        test_ad5676_device.device.input_into_dac(DAC_byte = 0x23)
        # The command byte is 0x20, there is no register
        test_ad5676_device.device.spi.writebytes2.assert_called_with(
            bytearray([0x20, 0x00, 0x23]))

    def test_write_to_dac(self, test_ad5676_device):

        test_ad5676_device.device.write_to_dac(channel=1, voltage=2.5)
        # 2.5V = 0xFFFF. Command byte is 0x30 | 0x01
        test_ad5676_device.device.spi.writebytes2.assert_called_with(
            bytearray([0x31, 0xFF, 0xFF]))

    def test_power_down(self, test_ad5676_device):

        test_ad5676_device.device.power_down(DAC_binary=0xCCCC)
        # Command byte is 0x40
        # DAC_binary has two bits per channel. Here, 11001100 11001100.
        test_ad5676_device.device.spi.writebytes2.assert_called_with(
            bytearray([0x40, 0xCC, 0xCC]))

    def test_LDAC_mask_register(self, test_ad5676_device):

        test_ad5676_device.device.LDAC_mask_register(DAC_byte=0xCC)
        # Command byte is 0x50
        # DAC_byte is just 11001100.
        test_ad5676_device.device.spi.writebytes2.assert_called_with(
            bytearray([0x50, 0x00, 0xCC]))

    def test_software_reset(self, test_ad5676_device):

        test_ad5676_device.device.software_reset()
        # Command byte is 0x60. Written is 0x1234 to execute reset function.
        test_ad5676_device.device.spi.writebytes2.assert_called_with(
            bytearray([0x60, 0x12, 0x34]))

    def test_register_readback(self, test_ad5676_device):

        test_ad5676_device.set_transfer_return_value([0x00, 0x98, 0x76])

        value = test_ad5676_device.device.register_readback(register=1)
        # Two writes performed, one write and one transfer
        # Command byte is 0x90 | 0x01 on write, and 0x00 on transfer.
        test_ad5676_device.device.spi.writebytes2.assert_called_with(
            bytearray([0x91,0x00, 0x00]))
        test_ad5676_device.device.spi.xfer2.assert_called_with(
            bytearray([0x00, 0x00, 0x00]))
        assert value == [0x98, 0x76]

    def test_update_all_input_channels(self, test_ad5676_device):

        test_ad5676_device.device.update_all_input_channels(voltage=2.5)
        # Command byte is 0xA0
        test_ad5676_device.device.spi.writebytes2.assert_called_with(
            bytearray([0xA0, 0xFF, 0xFF]))

    def test_update_all_dac_input_channels(self, test_ad5676_device):

        test_ad5676_device.device.update_all_dac_input_channels(voltage=2.5)
        # Command byte is 0xB0
        test_ad5676_device.device.spi.writebytes2.assert_called_with(
            bytearray(b'\xb0\xff\xff'))  # same as bytearray([0xB0, etc.])
