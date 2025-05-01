"""
Test Cases for the DAC63004 class from odin_devices
Jack Santiago, STFC Detector Systems Software Group
"""

import sys
import pytest  # type: ignore
import re

if sys.version_info[0] == 3:  # pragma: no cover
    from unittest.mock import Mock, mock_open, patch

    BUILTINS_NAME = "builtins"
else:  # pragma: no cover
    from mock import Mock, mock_open, patch

    BUILTINS_NAME = "__builtin__"

sys.modules["smbus"] = Mock()
sys.modules["logging"] = Mock()  # Track calls to logger.warning

from odin_devices.dac63004 import DAC63004


class dac63004TestFixture(object):
    def __init__(self):
        self.dac63004 = DAC63004(0x48, 3)  # Create with default address

        # Create virtual registers, init to 0x00
        self.device_registers = {
            "NOOP": {"address": 0x00, "flipped": False, "value": 0x00},
            "DAC_0_MARGIN_HIGH": {"address": 0x01, "flipped": True, "value": 0x00},
            "DAC_0_MARGIN_LOW": {"address": 0x02, "flipped": True, "value": 0x00},
            "DAC_0_VOUT_CMP_CONFIG": {"address": 0x03, "flipped": True, "value": 0x00},
            "DAC_0_IOUT_MISC_CONFIG": {"address": 0x04, "flipped": True, "value": 0x00},
            "DAC_0_CMP_MODE_CONFIG": {"address": 0x05, "flipped": True, "value": 0x00},
            "DAC_0_FUNC_CONFIG": {"address": 0x06, "flipped": True, "value": 0x00},
            "DAC_1_MARGIN_HIGH": {"address": 0x07, "flipped": True, "value": 0x00},
            "DAC_1_MARGIN_LOW": {"address": 0x08, "flipped": True, "value": 0x00},
            "DAC_1_VOUT_CMP_CONFIG": {"address": 0x09, "flipped": True, "value": 0x00},
            "DAC_1_IOUT_MISC_CONFIG": {"address": 0x0A, "flipped": True, "value": 0x00},
            "DAC_1_CMP_MODE_CONFIG": {"address": 0x0B, "flipped": True, "value": 0x00},
            "DAC_1_FUNC_CONFIG": {"address": 0x0C, "flipped": True, "value": 0x00},
            "DAC_2_MARGIN_HIGH": {"address": 0x0D, "flipped": True, "value": 0x00},
            "DAC_2_MARGIN_LOW": {"address": 0x0E, "flipped": True, "value": 0x00},
            "DAC_2_VOUT_CMP_CONFIG": {"address": 0x0F, "flipped": True, "value": 0x00},
            "DAC_2_IOUT_MISC_CONFIG": {"address": 0x10, "flipped": True, "value": 0x00},
            "DAC_2_CMP_MODE_CONFIG": {"address": 0x11, "flipped": True, "value": 0x00},
            "DAC_2_FUNC_CONFIG": {"address": 0x12, "flipped": True, "value": 0x00},
            "DAC_3_MARGIN_HIGH": {"address": 0x13, "flipped": True, "value": 0x00},
            "DAC_3_MARGIN_LOW": {"address": 0x14, "flipped": True, "value": 0x00},
            "DAC_3_VOUT_CMP_CONFIG": {"address": 0x15, "flipped": True, "value": 0x00},
            "DAC_3_IOUT_MISC_CONFIG": {"address": 0x16, "flipped": True, "value": 0x00},
            "DAC_3_CMP_MODE_CONFIG": {"address": 0x17, "flipped": True, "value": 0x00},
            "DAC_3_FUNC_CONFIG": {"address": 0x18, "flipped": True, "value": 0x00},
            "DAC_0_DATA": {"address": 0x19, "flipped": True, "value": 0x00},
            "DAC_1_DATA": {"address": 0x1A, "flipped": True, "value": 0x00},
            "DAC_2_DATA": {"address": 0x1B, "flipped": True, "value": 0x00},
            "DAC_3_DATA": {"address": 0x1C, "flipped": True, "value": 0x00},
            "COMMON_CONFIG": {"address": 0x1F, "flipped": True, "value": 0x00},
            "COMMON_TRIGGER": {"address": 0x20, "flipped": False, "value": 0x00},
            "COMMON_DAC_TRIG": {"address": 0x21, "flipped": False, "value": 0x00},
            "GENERAL_STATUS": {"address": 0x22, "flipped": False, "value": 0x00},
            "CMP_STATUS": {"address": 0x23, "flipped": False, "value": 0x00},
            "GPIO_CONFIG": {"address": 0x24, "flipped": False, "value": 0x00},
            "DEVICE_MODE_CONFIG": {"address": 0x25, "flipped": False, "value": 0x00},
            "INTERFACE_CONFIG": {"address": 0x26, "flipped": False, "value": 0x00},
            "SRAM_CONFIG": {"address": 0x2B, "flipped": False, "value": 0x00},
            "SRAM_DATA": {"address": 0x2C, "flipped": False, "value": 0x00},
            "DAC_0_DATA_8BIT": {"address": 0x40, "flipped": False, "value": 0x00},
            "DAC_1_DATA_8BIT": {"address": 0x41, "flipped": False, "value": 0x00},
            "DAC_2_DATA_8BIT": {"address": 0x42, "flipped": False, "value": 0x00},
            "DAC_3_DATA_8BIT": {"address": 0x43, "flipped": False, "value": 0x00},
            "BRDCAST_DATA": {"address": 0x50, "flipped": True, "value": 0x00},
        }

    def virtual_registers_en(self, en):
        if en:
            self.dac63004.bus.read_byte_data.side_effect = self.read_virtual_regmap
            self.dac63004.bus.write_byte_data.side_effect = self.write_virtual_regmap
            self.dac63004.bus.read_word_data.side_effect = self.read_virtual_regmap
            self.dac63004.bus.write_word_data.side_effect = self.write_virtual_regmap
        else:
            self.dac63004.bus.read_byte_data.side_effect = None
            self.dac63004.bus.write_byte_data.side_effect = None

    def read_virtual_regmap(self, address, register):
        for reg in self.device_registers.keys():
            if self.device_registers[reg]["address"] == register:
                return self.device_registers[reg]["value"]
        raise KeyError("No register matching address " + hex(register))

    def write_virtual_regmap(self, address, register, value):
        for reg in self.device_registers.keys():
            if self.device_registers[reg]["address"] == register:
                self.device_registers[reg]["value"] = value
                return
        raise KeyError("No register matching address " + hex(register))


@pytest.fixture(scope="class")
def test_dac63004_driver():
    test_driver_fixture = dac63004TestFixture()
    yield test_driver_fixture


class TestDAC63004:
    def test_read_register_address(self, test_dac63004_driver):
        with pytest.raises(KeyError, match="Register INCORRECT_NAME does not match any known registers."):
            test_dac63004_driver.dac63004.read_register_address("INCORRECT_NAME")
        assert test_dac63004_driver.dac63004.read_register_address("NOOP") == 0x00
        assert test_dac63004_driver.dac63004.read_register_address("DAC_0_MARGIN_HIGH") == 0x01
        assert test_dac63004_driver.dac63004.read_register_address("DAC_0_MARGIN_LOW") == 0x02
        assert test_dac63004_driver.dac63004.read_register_address("DAC_0_VOUT_CMP_CONFIG") == 0x03
        assert test_dac63004_driver.dac63004.read_register_address("DAC_0_IOUT_MISC_CONFIG") == 0x04
        assert test_dac63004_driver.dac63004.read_register_address("DAC_0_CMP_MODE_CONFIG") == 0x05
        assert test_dac63004_driver.dac63004.read_register_address("DAC_0_FUNC_CONFIG") == 0x06
        assert test_dac63004_driver.dac63004.read_register_address("DAC_1_MARGIN_HIGH") == 0x07
        assert test_dac63004_driver.dac63004.read_register_address("DAC_1_MARGIN_LOW") == 0x08
        assert test_dac63004_driver.dac63004.read_register_address("DAC_1_VOUT_CMP_CONFIG") == 0x09
        assert test_dac63004_driver.dac63004.read_register_address("DAC_1_IOUT_MISC_CONFIG") == 0x0A
        assert test_dac63004_driver.dac63004.read_register_address("DAC_1_CMP_MODE_CONFIG") == 0x0B
        assert test_dac63004_driver.dac63004.read_register_address("DAC_1_FUNC_CONFIG") == 0x0C
        assert test_dac63004_driver.dac63004.read_register_address("DAC_2_MARGIN_HIGH") == 0x0D
        assert test_dac63004_driver.dac63004.read_register_address("DAC_2_MARGIN_LOW") == 0x0E
        assert test_dac63004_driver.dac63004.read_register_address("DAC_2_VOUT_CMP_CONFIG") == 0x0F
        assert test_dac63004_driver.dac63004.read_register_address("DAC_2_IOUT_MISC_CONFIG") == 0x10
        assert test_dac63004_driver.dac63004.read_register_address("DAC_2_CMP_MODE_CONFIG") == 0x11
        assert test_dac63004_driver.dac63004.read_register_address("DAC_2_FUNC_CONFIG") == 0x12
        assert test_dac63004_driver.dac63004.read_register_address("DAC_3_MARGIN_HIGH") == 0x13
        assert test_dac63004_driver.dac63004.read_register_address("DAC_3_MARGIN_LOW") == 0x14
        assert test_dac63004_driver.dac63004.read_register_address("DAC_3_VOUT_CMP_CONFIG") == 0x15
        assert test_dac63004_driver.dac63004.read_register_address("DAC_3_IOUT_MISC_CONFIG") == 0x16
        assert test_dac63004_driver.dac63004.read_register_address("DAC_3_CMP_MODE_CONFIG") == 0x17
        assert test_dac63004_driver.dac63004.read_register_address("DAC_3_FUNC_CONFIG") == 0x18
        assert test_dac63004_driver.dac63004.read_register_address("DAC_0_DATA") == 0x19
        assert test_dac63004_driver.dac63004.read_register_address("DAC_1_DATA") == 0x1A
        assert test_dac63004_driver.dac63004.read_register_address("DAC_2_DATA") == 0x1B
        assert test_dac63004_driver.dac63004.read_register_address("DAC_3_DATA") == 0x1C
        assert test_dac63004_driver.dac63004.read_register_address("COMMON_CONFIG") == 0x1F
        assert test_dac63004_driver.dac63004.read_register_address("COMMON_TRIGGER") == 0x20
        assert test_dac63004_driver.dac63004.read_register_address("COMMON_DAC_TRIG") == 0x21
        assert test_dac63004_driver.dac63004.read_register_address("GENERAL_STATUS") == 0x22
        assert test_dac63004_driver.dac63004.read_register_address("CMP_STATUS") == 0x23
        assert test_dac63004_driver.dac63004.read_register_address("GPIO_CONFIG") == 0x24
        assert test_dac63004_driver.dac63004.read_register_address("DEVICE_MODE_CONFIG") == 0x25
        assert test_dac63004_driver.dac63004.read_register_address("INTERFACE_CONFIG") == 0x26
        assert test_dac63004_driver.dac63004.read_register_address("SRAM_CONFIG") == 0x2B
        assert test_dac63004_driver.dac63004.read_register_address("SRAM_DATA") == 0x2C
        assert test_dac63004_driver.dac63004.read_register_address("DAC_0_DATA_8BIT") == 0x40
        assert test_dac63004_driver.dac63004.read_register_address("DAC_1_DATA_8BIT") == 0x41
        assert test_dac63004_driver.dac63004.read_register_address("DAC_2_DATA_8BIT") == 0x42
        assert test_dac63004_driver.dac63004.read_register_address("DAC_3_DATA_8BIT") == 0x43
        assert test_dac63004_driver.dac63004.read_register_address("BRDCAST_DATA") == 0x50

    def test_flipped_read(self, test_dac63004_driver):
        test_dac63004_driver.virtual_registers_en(True)
        test_dac63004_driver.write_virtual_regmap(0x70, 0x00, 0b1001100101100110)
        assert test_dac63004_driver.dac63004.readU16flipped(0x00) == 0b0110011010011001
        test_dac63004_driver.write_virtual_regmap(0x70, 0x00, 0x00)

    def test_flipped_write(self, test_dac63004_driver):
        test_dac63004_driver.virtual_registers_en(True)
        test_dac63004_driver.dac63004.write16flipped(0x00, 0b1001100101100110)
        assert test_dac63004_driver.read_virtual_regmap(0x70, 0x00) == 0b0110011010011001
        test_dac63004_driver.write_virtual_regmap(0x70, 0x00, 0x00)

    def test_set_current_range(self, test_dac63004_driver):
        test_dac63004_driver.virtual_registers_en(True)

        test_dac63004_driver.dac63004.set_dac_current_range(DAC63004.CurrentRange.RANGE_0_25, 0)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x04) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x04) & 0x00FF) << 8) == 0b0

        test_dac63004_driver.dac63004.set_dac_current_range(DAC63004.CurrentRange.RANGE_0_50, 1)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0A) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0A) & 0x00FF) << 8) == 0b1000000000

        test_dac63004_driver.dac63004.set_dac_current_range(DAC63004.CurrentRange.RANGE_0_125, 2)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x10) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x10) & 0x00FF) << 8) == 0b10000000000

        test_dac63004_driver.dac63004.set_dac_current_range(DAC63004.CurrentRange.RANGE_0_250, 3)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x16) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x16) & 0x00FF) << 8) == 0b11000000000

        test_dac63004_driver.dac63004.set_dac_current_range(DAC63004.CurrentRange.RANGE_0_negative_24, 0)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x04) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x04) & 0x00FF) << 8) == 0b100000000000

        test_dac63004_driver.dac63004.set_dac_current_range(DAC63004.CurrentRange.RANGE_0_negative_48, 1)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0A) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0A) & 0x00FF) << 8) == 0b101000000000

        test_dac63004_driver.dac63004.set_dac_current_range(DAC63004.CurrentRange.RANGE_0_negative_120, 2)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x10) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x10) & 0x00FF) << 8) == 0b110000000000

        test_dac63004_driver.dac63004.set_dac_current_range(DAC63004.CurrentRange.RANGE_0_negative_240, 3)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x16) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x16) & 0x00FF) << 8) == 0b111000000000

        test_dac63004_driver.dac63004.set_dac_current_range(DAC63004.CurrentRange.RANGE_negative_25_25, 0)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x04) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x04) & 0x00FF) << 8) == 0b1000000000000

        test_dac63004_driver.dac63004.set_dac_current_range(DAC63004.CurrentRange.RANGE_negative_50_50, 1)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0A) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0A) & 0x00FF) << 8) == 0b1001000000000

        test_dac63004_driver.dac63004.set_dac_current_range(DAC63004.CurrentRange.RANGE_negative_125_125, 2)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x10) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x10) & 0x00FF) << 8) == 0b1010000000000

        test_dac63004_driver.dac63004.set_dac_current_range(DAC63004.CurrentRange.RANGE_negative_250_250, 3)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x16) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x16) & 0x00FF) << 8) == 0b1011000000000

    def test_set_voltage_gain(self, test_dac63004_driver):
        test_dac63004_driver.virtual_registers_en(True)

        # EXT_REF_1x
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.EXT_REF_1x, 0)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x03) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x03) & 0x00FF) << 8) & 0b1110000000000 == 0b0
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.EXT_REF_1x, 1)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x09) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x09) & 0x00FF) << 8) & 0b1110000000000 == 0b0
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.EXT_REF_1x, 2)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0F) & 0x00FF) << 8) & 0b1110000000000 == 0b0
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.EXT_REF_1x, 3)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x15) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x15) & 0x00FF) << 8) & 0b1110000000000 == 0b0

        # VDD_REF_1x
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.VDD_REF_1x, 0)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x03) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x03) & 0x00FF) << 8) & 0b1110000000000 == 0b10000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.VDD_REF_1x, 1)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x09) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x09) & 0x00FF) << 8) & 0b1110000000000 == 0b10000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.VDD_REF_1x, 2)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0F) & 0x00FF) << 8) & 0b1110000000000 == 0b10000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.VDD_REF_1x, 3)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x15) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x15) & 0x00FF) << 8) & 0b1110000000000 == 0b10000000000

        # INT_REF_1_5x
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_1_5x, 0)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x03) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x03) & 0x00FF) << 8) & 0b1110000000000 == 0b100000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_1_5x, 1)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x09) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x09) & 0x00FF) << 8) & 0b1110000000000 == 0b100000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_1_5x, 2)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0F) & 0x00FF) << 8) & 0b1110000000000 == 0b100000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_1_5x, 3)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x15) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x15) & 0x00FF) << 8) & 0b1110000000000 == 0b100000000000

        # INT_REF_2x
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_2x, 0)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x03) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x03) & 0x00FF) << 8) & 0b1110000000000 == 0b110000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_2x, 1)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x09) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x09) & 0x00FF) << 8) & 0b1110000000000 == 0b110000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_2x, 2)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0F) & 0x00FF) << 8) & 0b1110000000000 == 0b110000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_2x, 3)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x15) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x15) & 0x00FF) << 8) & 0b1110000000000 == 0b110000000000

        # INT_REF_3x
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_3x, 0)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x03) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x03) & 0x00FF) << 8) & 0b1110000000000 == 0b1000000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_3x, 1)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x09) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x09) & 0x00FF) << 8) & 0b1110000000000 == 0b1000000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_3x, 2)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0F) & 0x00FF) << 8) & 0b1110000000000 == 0b1000000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_3x, 3)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x15) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x15) & 0x00FF) << 8) & 0b1110000000000 == 0b1000000000000

        # INT_REF_4x
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_4x, 0)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x03) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x03) & 0x00FF) << 8) & 0b1110000000000 == 0b1010000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_4x, 1)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x09) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x09) & 0x00FF) << 8) & 0b1110000000000 == 0b1010000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_4x, 2)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x0F) & 0x00FF) << 8) & 0b1110000000000 == 0b1010000000000
        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_4x, 3)
        assert ((test_dac63004_driver.read_virtual_regmap(0x70, 0x15) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x15) & 0x00FF) << 8) & 0b1110000000000 == 0b1010000000000

    def test_set_current_mode(self, test_dac63004_driver):
        test_dac63004_driver.virtual_registers_en(True)

        with pytest.raises(IndexError, match=re.escape("Index -1 is not a valid index (0,1,2 or 3).")):
            test_dac63004_driver.dac63004.put_dac_into_current_mode(-1)
        with pytest.raises(IndexError, match=re.escape("Index 4 is not a valid index (0,1,2 or 3).")):
            test_dac63004_driver.dac63004.put_dac_into_current_mode(4)
        # HiZ
        test_dac63004_driver.dac63004.put_dac_into_current_mode(0)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111 == 0b110

        test_dac63004_driver.dac63004.put_dac_into_current_mode(1)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111000 == 0b110000

        test_dac63004_driver.dac63004.put_dac_into_current_mode(2)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111000000 == 0b110000000

        test_dac63004_driver.dac63004.put_dac_into_current_mode(3)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111000000000 == 0b110000000000

        # 10k
        test_dac63004_driver.dac63004.put_dac_into_current_mode(0, DAC63004.VoltagePowerDownMode.POW_DOWN_10k)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111 == 0b010

        test_dac63004_driver.dac63004.put_dac_into_current_mode(1, DAC63004.VoltagePowerDownMode.POW_DOWN_10k)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111000 == 0b010000

        test_dac63004_driver.dac63004.put_dac_into_current_mode(2, DAC63004.VoltagePowerDownMode.POW_DOWN_10k)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111000000 == 0b010000000

        test_dac63004_driver.dac63004.put_dac_into_current_mode(3, DAC63004.VoltagePowerDownMode.POW_DOWN_10k)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111000000000 == 0b010000000000

        # 100K
        test_dac63004_driver.dac63004.put_dac_into_current_mode(0, DAC63004.VoltagePowerDownMode.POW_DOWN_100k)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111 == 0b100

        test_dac63004_driver.dac63004.put_dac_into_current_mode(1, DAC63004.VoltagePowerDownMode.POW_DOWN_100k)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111000 == 0b100000

        test_dac63004_driver.dac63004.put_dac_into_current_mode(2, DAC63004.VoltagePowerDownMode.POW_DOWN_100k)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111000000 == 0b100000000

        test_dac63004_driver.dac63004.put_dac_into_current_mode(3, DAC63004.VoltagePowerDownMode.POW_DOWN_100k)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111000000000 == 0b100000000000

    def test_set_voltage_mode(self, test_dac63004_driver):
        test_dac63004_driver.virtual_registers_en(True)

        with pytest.raises(IndexError, match=re.escape("Index -1 is not a valid index (0,1,2 or 3).")):
            test_dac63004_driver.dac63004.put_dac_into_voltage_mode(-1)
        with pytest.raises(IndexError, match=re.escape("Index 4 is not a valid index (0,1,2 or 3).")):
            test_dac63004_driver.dac63004.put_dac_into_voltage_mode(4)

        test_dac63004_driver.dac63004.put_dac_into_voltage_mode(0)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111 == 0b001

        test_dac63004_driver.dac63004.put_dac_into_voltage_mode(1)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111000 == 0b001000

        test_dac63004_driver.dac63004.put_dac_into_voltage_mode(2)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111000000 == 0b001000000

        test_dac63004_driver.dac63004.put_dac_into_voltage_mode(3)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0xFF00) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x1F) & 0x00FF) << 8)) & 0b111000000000 == 0b001000000000

    def test_read_modify_write(self, test_dac63004_driver):
        test_dac63004_driver.virtual_registers_en(True)

        mask = 0b1010101010101010
        test_dac63004_driver.dac63004.read_modify_write("DAC_0_DATA", mask,  0b1100110011001100)
        assert test_dac63004_driver.read_virtual_regmap(0x70, 0x19) == 0b1000100010001000

    def test_set_dac_current(self, test_dac63004_driver):
        test_dac63004_driver.virtual_registers_en(True)

        with pytest.raises(Exception, match="Invalid current - current must be between -240 and 250."):
            test_dac63004_driver.dac63004.set_dac_current_micro_amps(0, 300)
        with pytest.raises(Exception, match="Invalid current - current must be between -240 and 250."):
            test_dac63004_driver.dac63004.set_dac_current_micro_amps(0, -300)

        test_dac63004_driver.dac63004.set_dac_current_micro_amps(0, 200)
        test_dac63004_driver.read_virtual_regmap(0x70, 0x19) == 194

        test_dac63004_driver.dac63004.set_dac_current_micro_amps(0, 100)
        test_dac63004_driver.read_virtual_regmap(0x70, 0x19) == 193

        test_dac63004_driver.dac63004.set_dac_current_micro_amps(0, 35)
        test_dac63004_driver.read_virtual_regmap(0x70, 0x19) == 168

        test_dac63004_driver.dac63004.set_dac_current_micro_amps(0, 20)
        test_dac63004_driver.read_virtual_regmap(0x70, 0x19) == 204

        test_dac63004_driver.dac63004.set_dac_current_micro_amps(0, -200)
        test_dac63004_driver.read_virtual_regmap(0x70, 0x19) == 192

        test_dac63004_driver.dac63004.set_dac_current_micro_amps(0, -90)
        test_dac63004_driver.read_virtual_regmap(0x70, 0x19) == 171

        test_dac63004_driver.dac63004.set_dac_current_micro_amps(0, -35)
        test_dac63004_driver.read_virtual_regmap(0x70, 0x19) == 166

        test_dac63004_driver.dac63004.set_dac_current_micro_amps(0, -20)
        test_dac63004_driver.read_virtual_regmap(0x70, 0x19) == 192

    def test_read_register_by_name(self, test_dac63004_driver):
        test_dac63004_driver.virtual_registers_en(True)

        with pytest.raises(KeyError, match="No register found matching name 'INCORRECT_NAME'."):
            test_dac63004_driver.dac63004.read_register_by_name("INCORRECT_NAME", False)

        test_dac63004_driver.write_virtual_regmap(0x70, 0x19, 0b1100110010011001)
        test_dac63004_driver.dac63004.read_register_by_name("DAC_0_DATA") == 0b1100110010011001
        
        test_dac63004_driver.write_virtual_regmap(0x70, 0x20, 0b1100110010011001)
        test_dac63004_driver.dac63004.read_register_by_name("COMMON_TRIGGER") == 0b1100110010011001

    def test_set_dac_voltage(self, test_dac63004_driver):
        test_dac63004_driver.virtual_registers_en(True)

        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.EXT_REF_1x, 0)
        with pytest.raises(Exception, match=re.escape("No reference voltage value provided for the current reference voltage setting (Check you have set values for the VDD and external reference inputs).")):
            test_dac63004_driver.dac63004.set_dac_voltage(0, 1)

        test_dac63004_driver.dac63004.set_external_reference_voltage(1.5)
        test_dac63004_driver.dac63004.set_VDD_reference_voltage(5)
        
        test_dac63004_driver.dac63004.read_modify_write("DAC_0_VOUT_CMP_CONFIG", 0b1110000000000, 0b1110000000000)
        with pytest.raises(Exception, match=re.escape("Error - reference voltage setting not recognized (0b111)")):
            test_dac63004_driver.dac63004.set_dac_voltage(0, 1)

        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.EXT_REF_1x, 0)

        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.EXT_REF_1x, 0)
        test_dac63004_driver.dac63004.set_dac_voltage(0, 0.15)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x19) & 65280) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x19) & 255) << 8)) >> 4 == 410

        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.VDD_REF_1x, 0)
        test_dac63004_driver.dac63004.set_dac_voltage(0, 0.2)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x19) & 65280) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x19) & 255) << 8)) >> 4 == 164

        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_1_5x, 0)
        test_dac63004_driver.dac63004.set_dac_voltage(0, 0.25)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x19) & 65280) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x19) & 255) << 8)) >> 4 == 563

        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_2x, 0)
        test_dac63004_driver.dac63004.set_dac_voltage(0, 0.3)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x19) & 65280) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x19) & 255) << 8)) >> 4 == 507

        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_3x, 0)
        test_dac63004_driver.dac63004.set_dac_voltage(0, 0.35)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x19) & 65280) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x19) & 255) << 8)) >> 4 == 394

        test_dac63004_driver.dac63004.set_dac_voltage_gain(DAC63004.VoltageGain.INT_REF_4x, 0)
        test_dac63004_driver.dac63004.set_dac_voltage(0, 0.4)
        assert (((test_dac63004_driver.read_virtual_regmap(0x70, 0x19) & 65280) >> 8) | ((test_dac63004_driver.read_virtual_regmap(0x70, 0x19) & 255) << 8)) >> 4 == 338
