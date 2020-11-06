"""Test cases for the bme280 from odin_devices.

Sample register values, as seen in any given set_transfer_return_values call, were used for predictable outputs, lifted from the following page:
https://learn.sparkfun.com/tutorials/sparkfun-bme280-breakout-hookup-guide/all#example-sketches. See ReadAllRegisters.ino for the specific screenshot.

Mika Shearwood, STFC Detector Systems Software Group Apprentice.
"""

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

    def __init__(self, mock_spi_dev, chip_id=0x60):

        self.mock_spi_dev = mock_spi_dev
        self.set_transfer_return_values([
            [0x0, chip_id],  # Read chip ID register
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

    def test_bad_chip_id(self):
        # A test to check the RuntimeError in the device init is raised
        # A new device is created with a bad chip ID, the error is caught
        # and error message checked
        with patch('odin_devices.spi_device.spidev.SpiDev') as MockSpiDev:
            mock_spi_dev = MockSpiDev.return_value
            with pytest.raises(RuntimeError):
                test_bme_fixture = BME280TestFixture(mock_spi_dev, chip_id=0x61)

    def test_device_init(self, test_bme280_device):

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
            [0x00, 0x0C],  # _get_status() to reach sleep(0.002) on line 135
            [0x00, 0x00],  # _get_status() to continue
            [0x00, 0x80, 0x9F, 0x00],  # raw_temperature
        ])

        assert round(test_bme280_device.device.temperature, 2) == 25.13

    def test_pressure(self, test_bme280_device):
        test_bme280_device.set_transfer_return_values([
            [0x00, 0x00],  # _get_status()
            [0x00, 0x80, 0x9F, 0x00],  # raw_temperature
            [0x00, 0x62, 0x09, 0x00],  # adc
        ])
        assert round(test_bme280_device.device.pressure, 2) == 850.00

        test_bme280_device.set_transfer_return_values([
            [0x00, 0x00],  # _get_status()
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

        # Check of ArithmeticError in pressure calculation
        test_bme280_device.device._pressure_calib[0] = 0
        test_bme280_device.set_transfer_return_values([
            [0x00, 0x00],  # _get_status()
            [0x00, 0x80, 0x9F, 0x00],  # raw_temperature
            [0x00, 0x62, 0x09, 0x00],  # adc
        ])
        with pytest.raises(ArithmeticError):
            assert not test_bme280_device.device.pressure
        # Set pressure_calib[0] back to what it was initially
        test_bme280_device.device._pressure_calib[0] = 0x953F

    def test_humidity(self, test_bme280_device):
        test_bme280_device.set_transfer_return_values([
            [0x00, 0x00],  # _get_status
            [0x00, 0x80, 0x9F, 0x00],  # _raw_temperature
            [0x00, 0x68, 0x9A],        # hum
        ])
        assert round(test_bme280_device.device.humidity, 2) == 32.19

        # Ensuring that max and minimum values are returned if read value is too low/high

        test_bme280_device.set_transfer_return_values([
            [0x00, 0x00],  # _get_status
            [0x00, 0x80, 0x9F, 0x00],  # _raw_temperature
            [0x00, 0xFF, 0xFF],        # hum maximum
            [0x00, 0x00],  # _get_status
            [0x00, 0x80, 0x9F, 0x00],  # _raw_temperature
            [0x00, 0x00, 0x00],        # hum minimum
        ])
        assert test_bme280_device.device.humidity == 100
        assert test_bme280_device.device.humidity == 0

    def test_read_config(self, test_bme280_device):
        test_bme280_device.set_transfer_return_values([[0x00, 0x00]])
        # This function is not presently used in the device
        read_config_value = test_bme280_device.device._read_config()
        test_bme280_device.device.spi.xfer2.assert_called_with(
            bytearray([0xF5, 0x00])
        )
        # 0xF5 is _BME280_REGISTER_CONFIG
        assert read_config_value == 0x00

    def test_standby_period_setter(self, test_bme280_device):

        assert test_bme280_device.device.standby_period

        with pytest.raises(ValueError):
            test_bme280_device.device.standby_period = 0x08  # Invalid -- not in BME280_STANDBY_TCS
            assert test_bme280_device.device.standby_period == 0x08

        test_bme280_device.device.standby_period = 0x06  # 10ms
        assert test_bme280_device.device.standby_period == 0x06  # assert non-default can be set
        test_bme280_device.device.standby_period = 0x06  # Set to current value

        test_bme280_device.device.standby_period = 0x02  # 125ms -- default
        assert test_bme280_device.device._t_standby == 0x02  # reset default and ensure this is done

    def test_mode_setter(self, test_bme280_device):
        # Ensure a ValueError is raised, assert a value is returned when called
        # Changing mode is handled in init
        MODE_INVALID = 0x07
        with pytest.raises(ValueError):
            test_bme280_device.device.mode = MODE_INVALID
        assert test_bme280_device.device.mode

    def test_irr_filter_setter(self, test_bme280_device):
        # Ensure a ValueError is raised, assert a value is returned when called
        with pytest.raises(ValueError):
            test_bme280_device.device.iir_filter = 0x07
        test_bme280_device.device.iir_filter = 0x01
        assert test_bme280_device.device.iir_filter == 0x01

        test_bme280_device.device.iir_filter = 0
        # Return to default of 0 (disabled)

    def test_config_property(self, test_bme280_device):
        # Ensuring the if checks in _config work correctly
        # This test also includes the normal checks in write_config
        MODE_FORCE = 0x01
        MODE_NORMAL = 0x03

        test_bme280_device.device._t_standby = 0x02
        test_bme280_device.device.iir_filter = 0x01
        test_bme280_device.device.mode = MODE_NORMAL
        # config is calculated with bitwise shift operators
        # With _t_standby == 0x02, 2 << 5 == 2 * 2^5 == 64
        # With _iir_filter == 0x01, 1 << 2 == 1 * 2^2 == 4
        # So config will be 68 with these settings
        assert test_bme280_device.device._config == 68
        # Restore settings to previous
        test_bme280_device.device.iir_filter = 0
        test_bme280_device.device.mode = MODE_FORCE


    def test_overscan_setters(self, test_bme280_device):
        # Defaults: Hum:0x01; Temp:0x01; Pres:0x05
        # = 1, 1, 16

        # Return values
        assert test_bme280_device.device.overscan_humidity
        assert test_bme280_device.device.overscan_pressure
        assert test_bme280_device.device.overscan_temperature

        with pytest.raises(ValueError):  # Invalid values
            test_bme280_device.device.overscan_humidity = 9
        with pytest.raises(ValueError):
            test_bme280_device.device.overscan_pressure = 9
        with pytest.raises(ValueError):
            test_bme280_device.device.overscan_temperature = 9

        # Valid values: ensuring sets are correct
        # _write_ctrl_meas() is generic so does not need to be checked every time
        test_bme280_device.device.overscan_humidity = 0x01
        assert test_bme280_device.device._overscan_humidity == 0x01
        test_bme280_device.device.overscan_pressure = 0x05
        assert test_bme280_device.device._overscan_pressure == 0x05
        test_bme280_device.device.overscan_temperature = 0x01
        assert test_bme280_device.device._overscan_temperature == 0x01

    def test_measurement_time(self, test_bme280_device):
        # The measurement times and maximums are predictable
        # They rely on the overscan settings
        # With the settings Hum, Temp, Pres being 0x01, 0x01, 0x05 (1, 1, 16)
        # Typical will be 1 + (2*1) + (2*16 + 0.5) + (2*1 + 0.5) = 38.0
        # Max will be 1.25 + (2.3*1) + (2.3*16 + 0.575) + (2.3*1 + 0.575) = 43.8
        assert test_bme280_device.device.measurement_time_typical == 38.0
        assert test_bme280_device.device.measurement_time_max == 43.8

    def test_altitude(self, test_bme280_device):
        # Testing that, when provided a sea_level_pressure, the device can calculate an altitude
        test_bme280_device.device.sea_level_pressure = 1028
        test_bme280_device.set_transfer_return_values([
            [0x00, 0x00, 0x00, 0x00],  # _get_status()
            [0x00, 0x80, 0x9F, 0x00],  # raw_temperature
            [0x00, 0x62, 0x09, 0x00],  # adc
        ])  # Identical pressure calculation to above
        # Pressure ~= 850.00
        # Alt = 44330 * (1 - ((850.00/1028)^0.1903) = 1575.3 to one decimal place
        assert round(test_bme280_device.device.altitude, 1) == 1575.3
