

import sys

import pytest

if sys.version_info[0] == 3:
    from unittest.mock import Mock, MagicMock, call, patch
else:
    from mock import Mock, MagicMock, call, patch

spidev_mock = MagicMock()
sys.modules['spidev'] = spidev_mock

from odin_devices.bme280 import BME280


class BME280TestFixture(object):
    """Container class used in fixtures for testing driver behaviour."""

    def __init__(self, mock_spi_dev):

        self.mock_spi_dev = mock_spi_dev
        self.set_transfer_return_values([
            [0x0, 0x60],  # Read chip ID register
            [0x0]*25,     # Read T,P coefficients
            [0x0, 0x0],   # Read H1 coefficient
            [0x0]*8,      # Read H2 coefficients
        ])

        self.device = BME280()

    def set_transfer_return_values(self, value):
        self.mock_spi_dev.xfer2.side_effect = value

    def assert_transfer_any_call(self, value):

        self.mock_spi_dev.xfer2.assert_any_call(bytearray(value))


@pytest.fixture(scope="class")
def test_bme280_device():
    """Fixture used in device test cases."""

    with patch('odin_devices.spi_device.spidev.SpiDev') as MockSpiDev:
        mock_spi_dev = MockSpiDev.return_value
        test_bme_fixture = BME280TestFixture(mock_spi_dev)
        yield test_bme_fixture


class TestBME280Device(object):

    def test_device_init(self, test_bme280_device):

        print (test_bme280_device.mock_spi_dev.mock_calls)

        test_bme280_device.assert_transfer_any_call([0xd0, 0x00])

        assert test_bme280_device.device.spi.mode == 0
        assert len(test_bme280_device.device.buffer) == 25

