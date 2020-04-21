"""Test cases for the Max31856 device from odin_devices.
Michael Shearwood, STFC Detector Systems Software Group Apprentice.
"""

import sys

import pytest

if sys.version_info[0] == 3:
    from unittest.mock import Mock, MagicMock, call
else:
    from mock import Mock, MagicMock, call

spidev_mock = MagicMock()
sys.modules['spidev'] = spidev_mock

from odin_devices.max31856 import Max31856


class Max31856DeviceTestFixture(object):
    """Container class used in fixtures for testing driver behaviour."""

    def __init__(self):
        self.device = Max31856()

    def set_transfer_return_value(self, value):
        self.device.spi.xfer2.return_value = value


@pytest.fixture(scope="class")
def test_max31856_device():
    """Fixture used in device test cases."""

    test_max31856_fixture = Max31856DeviceTestFixture()
    yield test_max31856_fixture


class TestMax31856Device(object):

    def test_init_settings(self, test_max31856_device):
        test_max31856_device.device.spi.reset_mock()
        test_max31856_device.device.__init__()

        assert test_max31856_device.device.spi.max_speed_hz == 500000
        assert test_max31856_device.device.spi.mode == 1
        assert test_max31856_device.device.spi.bits_per_word == 8
        assert len(test_max31856_device.device.buffer) == 2

        assert test_max31856_device.device.spi.writebytes2.call_count == 3
        assert test_max31856_device.device.spi.xfer2.call_count == 1

    def test_temperature(self, test_max31856_device):
        # The reset is necessary to ensure that call_count is correct and independent
        test_max31856_device.device.spi.reset_mock()

        # Temperatures are stored in three-byte sequences and fetched with
        # the 'raw_temp =' transfer in temperature().
        # In order shown here, the bytes represent 256, 16, 1, 1/16, 1/256, 1/4096 °C.
        test_max31856_device.set_transfer_return_value(bytes([0x01, 0x60, 0x00]))
        assert test_max31856_device.device.temperature == 22

        assert test_max31856_device.device.spi.writebytes2.call_count == 2
        assert test_max31856_device.device.spi.xfer2.call_count == 2
