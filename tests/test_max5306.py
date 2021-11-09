import sys

import pytest

if sys.version_info[0] == 3:
    from unittest.mock import Mock, MagicMock, call, patch
else:
    from mock import Mock, MagicMock, call, patch

spidev_mock = MagicMock()
sys.modules['spidev'] = spidev_mock

Test_Vref = 3.3

from odin_devices.max5306 import MAX5306


class MAX5306TestFixture(object):
    def __init__(self, mock_spi_dev):
        self.mock_spi_dev = mock_spi_dev
        self.device_unipolar = MAX5306(Test_Vref, 1, 1)
        self.device_bipolar = MAX5306(Test_Vref, 1, 1, bipolar=True)

    def assert_write_any_call(self, device, value):
        if device is self.device_unipolar or device is self.device_bipolar:
            #print(device.spi.writebytes2.mock_calls)
            #device.spi.writebytes2.assert_any_call(bytearray(value))
            print(device.spi.xfer2.mock_calls)
            device.spi.xfer2.assert_any_call(list(value))
        else:
            raise Exception("This device does not exist")


@pytest.fixture(scope='class')
def test_max5306_device():
    with patch('odin_devices.spi_device.spidev.SpiDev') as MockSpiDev:
        mock_spi_dev = MockSpiDev.return_value
        test_max_fixture = MAX5306TestFixture(mock_spi_dev)
        yield test_max_fixture


class TestMAX5306Device(object):

    def test_invalid_vref(self):
        # Check that the expected errors are raised when invalid Vref values are supplied
        with pytest.raises(ValueError, match=".*Vref.*"):
            temp_new_device = MAX5306(Vref=6, bus=1, device=1)
        with pytest.raises(ValueError, match=".*Vref.*"):
            temp_new_device = MAX5306(Vref=0.7, bus=1, device=1)
        with pytest.raises(ValueError, match=".*Vref.*"):
            temp_new_device = MAX5306(Vref=-0.7, bus=1, device=1)
        with pytest.raises(TypeError, match=".*Vref.*"):
            temp_new_device = MAX5306(Vref="not a valid float",  bus=1, device=1)

    def test_send_command(self, test_max5306_device):
        # TODO
        temp_new_device = MAX5306(3.3, 1, 1)

        # Check that sending a command correctly packages the command and data
        test_command = 0b1010
        test_data = 0b011001100110
        expected_output = (test_command << 12) | test_data
        expected_output_bytes = [(expected_output & 0xFF00) >> 8, expected_output & 0xFF]
        temp_new_device._send_command(test_command, test_data)
        temp_new_device.spi.xfer2.assert_any_call(list(expected_output_bytes))

        # Check that a command that does not fit is caught
        with pytest.raises(ValueError):
            temp_new_device._send_command(0b10000, test_data)
        with pytest.raises(ValueError):
            temp_new_device._send_command(-1, test_data)

        # Check that data that does not fit is caught
        with pytest.raises(ValueError):
            temp_new_device._send_command(test_command, 0xFFFF)
        with pytest.raises(ValueError):
            temp_new_device._send_command(test_command, -1)

    def test_reset_on_init(self, test_max5306_device):
        # This is actually valid if there is a call with 0b0001xxxx 0bxxxxxxxx
        test_max5306_device.assert_write_any_call(test_max5306_device.device_bipolar,
                                                        [0b00010000, 0b00000000])
        test_max5306_device.assert_write_any_call(test_max5306_device.device_unipolar,
                                                        [0b00010000, 0b00000000])

    def test_set_power(self, test_max5306_device):
        # check that power is set correctly for the correct outputs. Currently, only power-up
        # and shutdown-3 (default state) are used.

        # Set output power to power-up for output 2
        test_max5306_device.device_unipolar.power_on_output(2)

        # Set output power to shutdown-3 for output 3
        test_max5306_device.device_unipolar.power_off_output(3)

        # Check that correct data was written
        test_max5306_device.assert_write_any_call(test_max5306_device.device_unipolar,
                                                  [0b11110000, 0b00101100])

        # Check that correct data was written
        test_max5306_device.assert_write_any_call(test_max5306_device.device_unipolar,
                                                  [0b11110000, 0b01000000])

    def test_unipolar_set_output(self, test_max5306_device):
        # Set the output to datasheet example of Vref / 2
        test_max5306_device.device_unipolar.set_output(4, Test_Vref / 2.0)

        # Test correct output number, correct dac value sent to input
        # This code is for DAC output 4 with DAC value 0b1000 00000000
        test_max5306_device.assert_write_any_call(test_max5306_device.device_unipolar,
                                                        [0b01011000, 0b00000000])

        # Test correct output latched to DAC
        # This code is for DAC latch with only output 4 latched
        test_max5306_device.assert_write_any_call(test_max5306_device.device_unipolar,
                                                        [0b11100000, 0b10000000])

        # Tests limits (should not quite reach Vref)
        with pytest.raises(ValueError, match=".*Unipolar voltage.*"):
            test_max5306_device.device_unipolar.set_output(1, -0.1)
        with pytest.raises(ValueError, match=".*Unipolar voltage.*"):
            test_max5306_device.device_unipolar.set_output(1, Test_Vref)

        # Test incorrect output selection
        with pytest.raises(IndexError, match=".*output_number.*"):
            test_max5306_device.device_unipolar.set_output(10, Test_Vref)

        # Test incorrect output voltage format
        with pytest.raises(TypeError):
            test_max5306_device.device_unipolar.set_output(1, "not a float")

    def test_bipolar_set_output(self, test_max5306_device):
        # Much of the set_output function has already been tested above, so this test will focus
        # on verifying the result of the DAC calculation for bipolar output and limits

        # Set the output to datasheet example of -(1/2048)Vref (0111 1111 1111)
        test_max5306_device.device_bipolar.set_output(5, Test_Vref*((-1)/(2048.0)))

        # Test correct output number, correct dac value sent to output
        # This code is for DAC output 5 with DAC value 0b0111 1111 1111
        test_max5306_device.assert_write_any_call(test_max5306_device.device_bipolar,
                                                        [0b01100111, 0b11111111])

        # Test limits (should not quite reach Vref, but does reach -Vref)
        test_max5306_device.device_bipolar.set_output(1, -Test_Vref)    # Should be fine
        with pytest.raises(ValueError, match=".*Bipolar voltage.*"):
            test_max5306_device.device_bipolar.set_output(1, -Test_Vref - 0.1)
        with pytest.raises(ValueError, match=".*Bipolar voltage.*"):
            test_max5306_device.device_bipolar.set_output(1, Test_Vref)
