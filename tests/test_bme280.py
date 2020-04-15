

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
            [0x00, 0x46, 0x6D, 0xE2, 0x67, 0x32, 0x00,  # T:P, 6:18 bytes
            0x3F, 0x95, 0x32, 0xD6, 0xD0, 0x0B, 0xED, 0x1E, 0x8A, 0xFF, 0xF9, 0xFF, 0xAC, 0x26, 0x0A, 0xD8, 0xBD, 0x10],    # Read T,P coefficients
            [0x0, 0x4B],  # Read H1 coefficient
            [0x00, 0x66, 0x01, 0x00, 0x14, 0x08, 0x00, 0x1E],      # Read H2 coefficients
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
        test_bme280_device.assert_transfer_any_call(
            [0x88, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        test_bme280_device.assert_transfer_any_call([0xa1, 0x00])
        test_bme280_device.assert_transfer_any_call(
            [0xe1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

        assert test_bme280_device.device.spi.mode == 0
        assert len(test_bme280_device.device.buffer) == 25

    def test_temperature(self, test_bme280_device):
        test_bme280_device.set_transfer_return_values([
            [0x00, 0x00, 0x00, 0x00],  # _get_status()
            [0x00, 0x80, 0x9F, 0x00],  # raw_temperature
        ])

        print(test_bme280_device.device.temperature)

    def test_pressure(self, test_bme280_device):
        test_bme280_device.set_transfer_return_values([
            [0x00, 0x00, 0x00, 0x00],  # _get_status()
            [0x00, 0x80, 0x9F, 0x00],  # raw_temperature
            [0x00, 0x62, 0x09, 0x00],  # adc
        ])
        print(test_bme280_device.device.pressure)

        test_bme280_device.set_transfer_return_values([
            [0x00, 0x00, 0x00, 0x00],  # _get_status()
            [0x00, 0x80, 0x9F, 0x00],  # raw_temperature
            [0x00, 0x00, 0x00, 0x00],  # adc maximum
            [0x00, 0x00, 0x00, 0x00],  # _get_status()
            [0x00, 0x80, 0x9F, 0x00],  # raw_temperature
            [0x00, 0xFF, 0xFF, 0xFF],  # adc minimum
            # Calculations are done by subtracting the read value,
            # hence maximum has a read value of all 0s.
        ])
        assert test_bme280_device.device.pressure == 1100
        assert test_bme280_device.device.pressure == 300

    def test_humidity(self, test_bme280_device):
        test_bme280_device.set_transfer_return_values([
            [0x00, 0x00, 0x00, 0x00],  # _get_status
            [0x00, 0x80, 0x9F, 0x00],  # _raw_temperature
            [0x00, 0x68, 0x9A],        # hum
        ])
        print(test_bme280_device.device.humidity)

        # Ensuring that max and minimum values are returned if read value is too low/high

        test_bme280_device.set_transfer_return_values([
            [0x00, 0x00, 0x00, 0x00],  # _get_status
            [0x00, 0x80, 0x9F, 0x00],  # _raw_temperature
            [0x00, 0xFF, 0xFF],        # hum maximum
            [0x00, 0x00, 0x00, 0x00],  # _get_status
            [0x00, 0x80, 0x9F, 0x00],  # _raw_temperature
            [0x00, 0x00, 0x00],        # hum minimum
        ])
        assert test_bme280_device.device.humidity == 100
        assert test_bme280_device.device.humidity == 0