

import sys

import pytest

if sys.version_info[0] == 3:
    from unittest.mock import Mock, MagicMock, call
else:
    from mock import Mock, MagicMock, call

spidev_mock = MagicMock()
sys.modules['spidev'] = spidev_mock

from odin_devices.bme280 import BME280


class BME280TestFixture(object):
    """Container class used in fixtures for testing driver behaviour."""

    def __init__(self):
        spidev_mock.transfer.return_value = [0x00, 0x60]
        self.device = BME280()


    def set_transfer_return_value(self, value):
        self.device.spi.xfer2.return_value = value


@pytest.fixture(scope="class")
def test_bme280_device():
    """Fixture used in device test cases."""

    test_bme_fixture = BME280TestFixture()
    yield test_bme_fixture


class TestBME280Device(object):

    def test_init_settings(self, test_bme280_device):
        test_bme280_device.device.spi.reset_mock()
        test_bme280_device.set_transfer_return_value([0x00, 0x60])  # _BME280_CHIPID

        assert test_bme280_device.device.spi.mode == 0
        assert len(test_bme280_device.device.buffer) == 25

