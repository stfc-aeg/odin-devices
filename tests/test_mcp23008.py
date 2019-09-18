"""Test cases for the AD7998 class from odin_devices.
Adam Neaves, STFC Detector Systems Software Group
Tim Nicholls, STFC Detector Systems Software Group
"""

import sys

import pytest

if sys.version_info[0] == 3:  # pragma: no cover
    from unittest.mock import Mock
else:                         # pragma: no cover
    from mock import Mock

sys.modules['smbus'] = Mock()
from odin_devices.mcp23008 import MCP23008


class mcp23008TestFixture(object):

    def __init__(self):
        self.address = 0x20
        self.mcp23008 = MCP23008(self.address)

        # Override the internal register buffers so that subsequent access calls have
        # sensible I2C access values, otherwise they contain references to the mocked
        # smbus calls
        self.mcp23008._MCP23008__iodir = 0
        self.mcp23008._MCP23008__gppu = 0
        self.mcp23008._MCP23008__gpio = 0

        # Explictly mock underlying I2C byte read (called by I2CDevice.readU8) to return value
        self.mcp23008.bus.read_byte_data.return_value = 0

    def get_iodir_buffer(self):

        return self.mcp23008._MCP23008__iodir

    def get_gppu_buffer(self):

        return self.mcp23008._MCP23008__gppu

    def get_gpio_buffer(self):

        return self.mcp23008._MCP23008__gpio


@pytest.fixture(scope="class")
def test_mcp23008_driver():
    driver_fixture = mcp23008TestFixture()
    yield driver_fixture


class TestMCP23008():

    def test_registers_read(self, test_mcp23008_driver):

        test_mcp23008_driver.mcp23008.bus.read_byte_data.assert_any_call(
            test_mcp23008_driver.address, MCP23008.IODIR)
        test_mcp23008_driver.mcp23008.bus.read_byte_data.assert_any_call(
            test_mcp23008_driver.address, MCP23008.GPPU)
        test_mcp23008_driver.mcp23008.bus.read_byte_data.assert_any_call(
            test_mcp23008_driver.address, MCP23008.GPIO)

    def test_setup_in(self, test_mcp23008_driver):

        pin = 3
        direction = MCP23008.IN
        expected_iodir = test_mcp23008_driver.get_iodir_buffer() | 1 << pin

        test_mcp23008_driver.mcp23008.setup(pin, direction)

        test_mcp23008_driver.mcp23008.bus.write_byte_data.assert_called_with(
            test_mcp23008_driver.address, MCP23008.IODIR, expected_iodir
        )

    def test_setup_out(self, test_mcp23008_driver):

        pin = 4
        direction = MCP23008.OUT
        expected_iodir = test_mcp23008_driver.get_iodir_buffer() & ~(1 << pin)

        test_mcp23008_driver.mcp23008.setup(pin, direction)

        test_mcp23008_driver.mcp23008.bus.write_byte_data.assert_called_with(
            test_mcp23008_driver.address, MCP23008.IODIR, expected_iodir
        )

    def test_setup_bad_direction(self, test_mcp23008_driver):

        pin = 7
        direction = 1234

        exception_message = 'expected a direction of MCP23008.IN or MCP23008.OUT'
        with pytest.raises(ValueError) as excinfo:
            test_mcp23008_driver.mcp23008.setup(pin, direction)
            assert exception_message in excinfo.value

    def test_pullup_enable(self, test_mcp23008_driver):

        pin = 1
        expected_gppu = test_mcp23008_driver.get_gppu_buffer() | (1 << pin)

        test_mcp23008_driver.mcp23008.pullup(pin, 1)
        test_mcp23008_driver.mcp23008.bus.write_byte_data.assert_called_with(
            test_mcp23008_driver.address, MCP23008.GPPU, expected_gppu
        )

    def test_pullup_disable(self, test_mcp23008_driver):

        pin = 1
        expected_gppu = test_mcp23008_driver.get_gppu_buffer() & ~(1 << pin)

        test_mcp23008_driver.mcp23008.pullup(pin, 0)
        test_mcp23008_driver.mcp23008.bus.write_byte_data.assert_called_with(
            test_mcp23008_driver.address, MCP23008.GPPU, expected_gppu
        )

    def test_input(self, test_mcp23008_driver):

        pin = 1
        val = test_mcp23008_driver.mcp23008.input(pin)
        test_mcp23008_driver.mcp23008.bus.read_byte_data.assert_called_with(
            test_mcp23008_driver.address, MCP23008.GPIO)

    def test_input_pins(self, test_mcp23008_driver):

        pins = [1, 3, 5, 7]

        pin_vals = test_mcp23008_driver.mcp23008.input_pins(pins)

        assert len(pins) == len(pin_vals)
        test_mcp23008_driver.mcp23008.bus.read_byte_data.assert_called_with(
            test_mcp23008_driver.address, MCP23008.GPIO
        )

    def test_output_high(self, test_mcp23008_driver):

        pin = 3
        val = 1
        expected_gpio = test_mcp23008_driver.get_gpio_buffer() | (1 << pin)

        test_mcp23008_driver.mcp23008.output(pin, val)
        test_mcp23008_driver.mcp23008.bus.write_byte_data.assert_called_with(
            test_mcp23008_driver.address, MCP23008.GPIO, expected_gpio
        )

    def test_output_low(self, test_mcp23008_driver):

        pin = 4
        val = 0
        expected_gpio = test_mcp23008_driver.get_gpio_buffer() & ~(1 << pin)

        test_mcp23008_driver.mcp23008.output(pin, val)
        test_mcp23008_driver.mcp23008.bus.write_byte_data.assert_called_with(
            test_mcp23008_driver.address, MCP23008.GPIO, expected_gpio
        )

    def test_output_pins(self, test_mcp23008_driver):

        pins = {1: 0, 3: 1, 2: 0, 5: 1}
        expected_gpio = test_mcp23008_driver.get_gpio_buffer()

        for pin, val in pins.items():
            if val:
                expected_gpio |= (1 << pin)
            else:
                expected_gpio &= ~(1 << pin)

        test_mcp23008_driver.mcp23008.output_pins(pins)
        test_mcp23008_driver.mcp23008.bus.write_byte_data.assert_called_with(
            test_mcp23008_driver.address, MCP23008.GPIO, expected_gpio
        )

    def test_disable_outputs(self, test_mcp23008_driver):

        expected_gpio = 0
        test_mcp23008_driver.mcp23008.disable_outputs()
        test_mcp23008_driver.mcp23008.bus.write_byte_data.assert_called_with(
            test_mcp23008_driver.address, MCP23008.GPIO, expected_gpio
        )
