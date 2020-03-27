"""Test cases for spi_device from odin_devices.

Due to the optional buffer functionality not having a disable feature,
the functions are not tested in the order they appear in spi_device."""

import sys

import pytest

if sys.version_info[0] == 3:
    from unittest.mock import Mock, MagicMock, call
else:
    from mock import Mock, MagicMock, call

spidev_mock = MagicMock()
sys.modules['spidev'] = spidev_mock

from odin_devices.spi_device import SPIDevice, SPIException


class SPIDeviceTestFixture(object):
    """Container class used in fixtures for testing driver behaviour."""

    def __init__(self):
        self.address = 1
        self.bus = 1
        self.debug = True
        self.device = SPIDevice(self.bus, self.address,bits_per_word=8, hz=500000, debug=self.debug)
        self.max_speed_hz = 100000
        self.bits_per_word = 16
        self.buffer = None
        self.mode = 1

    def set_transfer_read_return_value(self, value):
        self.device.spi.xfer2.return_value = value
        self.device.spi.readbytes.return_value = value


@pytest.fixture(scope="class")
def test_spi_device():
    """Fixture used in device test cases."""

    test_spi_fixture = SPIDeviceTestFixture()
    yield test_spi_fixture


class TestSPIDevice(object):

    EXC_MODE_NONE, EXC_MODE_TRAP, EXC_MODE_RAISE = range(3)
    EXC_MODES = [EXC_MODE_NONE, EXC_MODE_TRAP, EXC_MODE_RAISE]
    EXC_MODE_NAME = ['exception_mode_none', 'exception_mode_trap', 'exception_mode_raise']

    def test_enable_exceptions(self, test_spi_device):
        test_spi_device.device.enable_exceptions()
        assert test_spi_device.device._enable_exceptions == True

    def test_disable_exceptions(self, test_spi_device):
        test_spi_device.device.disable_exceptions()
        assert test_spi_device.device._enable_exceptions == False

    def test_device_init(self, test_spi_device):

        assert test_spi_device.bus     == test_spi_device.device.bus
        assert test_spi_device.address == test_spi_device.device.device
        assert test_spi_device.debug   == test_spi_device.device.debug

    def test_write_bytes_none(self, test_spi_device):
        # Testing that writebytes2 is not called without data or buffer
        test_spi_device.device.write_bytes()
        test_spi_device.device.spi.writebytes2.assert_not_called()

    def test_transfer_none(self, test_spi_device):
        # Testing that xfer2 is not called without data or buffer
        test_spi_device.device.transfer()
        test_spi_device.device.spi.xfer2.assert_not_called()

    def test_buffer_or_data(self, test_spi_device):
        # Neither data nor buffer
        # buffer is set in another test, so this must be done first
        values = test_spi_device.device.buffer_or_data()
        assert values == -1

        # With buffer -- create/edit buffer to ensure that values references it
        len_buffer = 4
        test_spi_device.device.set_buffer_length(len_buffer)
        test_spi_device.device.buffer[0] = 1
        values = test_spi_device.device.buffer_or_data()
        assert values == bytearray([1, 0, 0, 0])

        # With data -- different to previous test of buffer
        values = test_spi_device.device.buffer_or_data(bytearray([0x02, 0x00, 0x00]))
        assert values == bytearray([0x02, 0x00, 0x00])

    def test_set_clock_hz(self, test_spi_device):
        new_hz = 300000
        test_spi_device.device.set_clock_hz(new_hz)
        assert test_spi_device.device.spi.max_speed_hz == new_hz

    def test_set_bits_per_word(self, test_spi_device):
        new_bits = 8
        test_spi_device.device.set_bits_per_word(new_bits)
        assert test_spi_device.device.spi.bits_per_word == new_bits

    def test_set_mode(self, test_spi_device):
        valid_mode = 1
        test_spi_device.device.set_mode(valid_mode)
        assert test_spi_device.device.spi.mode == valid_mode

        invalid_mode = 4
        test_spi_device.device.set_mode(invalid_mode)
        assert test_spi_device.device.spi.mode == valid_mode

    def test_close(self, test_spi_device):
        test_spi_device.device.close()
        test_spi_device.device.spi.close.assert_called()

    def test_read_bytes(self, test_spi_device):
        test_spi_device.device.read_bytes(4)
        test_spi_device.device.spi.readbytes.assert_called_with(4)



    def test_transfer(self, test_spi_device):
        test_spi_device.set_transfer_read_return_value([0x56, 0x78, 0x90])

        val = test_spi_device.device.transfer([0x01, 0x23, 0x34])

        test_spi_device.device.spi.xfer2.assert_called_with([0x01, 0x23, 0x34])
        assert val == [0x56, 0x78, 0x90]

    # To be parametrized?
    def test_write_n(self, test_spi_device):
        data = [0x01, 0x23, 0x45, 0x56]
        test_spi_device.device.write_8(data)
        test_spi_device.device.spi.writebytes2.assert_called_with([0x01])

        test_spi_device.device.write_16(data)
        test_spi_device.device.spi.writebytes2.assert_called_with([0x01, 0x23])

        test_spi_device.device.write_24(data)
        test_spi_device.device.spi.writebytes2.assert_called_with([0x01, 0x23, 0x45])

    @pytest.mark.parametrize("exc_mode", EXC_MODES)
    @pytest.mark.parametrize(
        "method, spidev_method, args, exp_rc",
        [
            ('write_bytes', 'writebytes2', ([0x01, 0x23, 0x34]), None),
            ('transfer', 'xfer2', ([0x01, 0x23, 0x34]), [0x01, 0x23, 0x34]),
            ('read_bytes', 'readbytes', (3), [0x01, 0x23, 0x34]),
        ]
    )
    def test_device_access(self, method, spidev_method, exc_mode, args, exp_rc, test_spi_device):

        cached_side_effect = getattr(test_spi_device.device.spi, spidev_method).side_effect

        if exc_mode == self.EXC_MODE_NONE:
            side_effect = None
            exc_enable = False
            getattr(test_spi_device.device.spi, spidev_method).return_value = exp_rc
        elif exc_mode == self.EXC_MODE_TRAP:
            side_effect = IOError('mocked error')
            exc_enable = False
            exp_rc = SPIDevice.ERROR
        elif exc_mode == self.EXC_MODE_RAISE:
            side_effect = IOError('mocked error')
            exc_enable = True
        else:
            raise Exception('Invalid exception test mode {}'.format(exc_mode))

        getattr(test_spi_device.device.spi, spidev_method).side_effect = side_effect
        test_spi_device.device.enable_exceptions() if exc_enable else test_spi_device.device.disable_exceptions()

        rc = None
        exception_message = 'error from device'

        if exc_enable:
            with pytest.raises(SPIException) as excinfo:
                rc = getattr(test_spi_device.device, method)(args)
                assert rc == exp_rc
                assert exception_message in excinfo.value
        else:
            rc = getattr(test_spi_device.device, method)(args)
            assert rc == exp_rc

        getattr(test_spi_device.device.spi, spidev_method).side_effect = cached_side_effect

