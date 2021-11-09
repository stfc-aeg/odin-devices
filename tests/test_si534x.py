import sys
import pytest

if sys.version_info[0] == 3:    # pragma: no cover
    from unittest.mock import Mock, mock_open, patch
    BUILTINS_NAME = 'builtins'
else:                           # pramga: no cover
    from mock import Mock, mock_open, patch
    BUILTINS_NAME = '__builtin__'

sys.modules['smbus'] = Mock()
sys.modules['logging'] = Mock() # Track calls to logger.warning
from odin_devices.si534x import _SI534x, SI5344, SI5345, SI5342, SI534xCommsException
from odin_devices.i2c_device import I2CException

class si534xTestFixture(object):

    def __init__(self):
        self.si5345_i2c = SI5345(i2c_address = 0xAA)
        self.virtual_registers = {}
        self.virtual_page_select = 0x00
        self.si5345_i2c.i2c_bus = Mock()

    def virtual_registers_en(self, en):
        if en:
            print("I2C interface now driving virtual register map")
            self.si5345_i2c.i2c_bus.write8.side_effect = self.write_virtual_regmap
            self.si5345_i2c.i2c_bus.readU8.side_effect = self.read_virtual_regmap
        else:
            print("I2C interface now has no effect")

    def read_virtual_regmap(self, register):
        try:
            if register == 0x01:
                # This is the page select register
                print("REGISTER MOCK: Page select requested: ", self.virtual_page_select)
                return self.virtual_page_select
            else:
                print("REGISTER MOCK: Register {} page {} value requested: {}".format(
                    register, self.virtual_page_select,
                    self.virtual_registers[self.virtual_page_select][register]))
                return self.virtual_registers[self.virtual_page_select][register]
        except Exception as e:
            print("Failure to read register {} from page {}".format(register, self.virtual_page_select))
            print("Error: {}".format(e))
            raise

    def write_virtual_regmap(self, register, value):
        try:
            if register == 0x01:
                # This is the page select register
                print("REGISTER MOCK: Page select changed: ", value)
                self.virtual_page_select = value
            else:
                print("REGISTER MOCK: Register {} page {} changed: {}".format(
                    register, self.virtual_page_select, value))
                self.virtual_registers[self.virtual_page_select][register] = value
        except Exception as e:
            print("Failure to read register {} from page {}".format(register, self.virtual_page_select))
            print("Error: {}".format(e))
            raise

@pytest.fixture(scope="class")
def test_si534x_driver():
    test_driver_fixture = si534xTestFixture()
    yield test_driver_fixture

class TestSI534x():

    def test_i2c_init(self, test_si534x_driver):
        pass

    def test_spi_init(self, test_si534x_driver):
        pass

    def test_standard_field_rw(self, test_si534x_driver):
        pass

    def test_channelmap_register_addressing(self, test_si534x_driver):
        pass

    def test_multisynthmap_register_addressing(self, test_si534x_driver):
        pass

    def test_regmap_file_rw(self, test_si534x_driver):
        test_si534x_driver.virtual_registers_en(True)

        # For a reproducible pattern, set registers to equal the bitwise OR of page and reg num.
        test_si534x_driver.virtual_registers = {}
        regmap_generator = _SI534x._regmap_generator()
        for page, register in regmap_generator:       # Make sure this is up to date
            if not page in test_si534x_driver.virtual_registers.keys():
                test_si534x_driver.virtual_registers[page] = {}
            test_si534x_driver.virtual_registers[page][register] = page | register
            #print("setting page ", page, " register ", register, " to ", page|register)

        # Mock export to imaginary file
        mock_file_open = mock_open()
        with patch(BUILTINS_NAME + '.open', mock_file_open):
            # Write temporary memory-based file
            print("Iterator resister list:", list(_SI534x._regmap_generator()))
            test_si534x_driver.si5345_i2c.export_register_map('nofile.txt')
            mock_file_open.assert_called()

        # Assemble 'file' to feed back in with the written lines captured
        tmp_file_str = ""
        for writeline in mock_file_open.mock_calls:
            if not "call().write" in str(writeline):
                continue
            tmp_file_str += str(writeline)[14:-4] + "\n"
            #print(writeline)

        #print("Temporary file contents:", tmp_file_str)

        # Change all virtual register values to 0xFF
        for page_no in test_si534x_driver.virtual_registers.keys():
            page_dict = test_si534x_driver.virtual_registers[page_no]
            for register in page_dict.keys():
                if register == 0x01:
                    # Do not overwrite the page select
                    continue
                test_si534x_driver.virtual_registers[page_no][register] = 0xFF

        #print("Virtual registers after reset:", test_si534x_driver.virtual_registers)

        # Write registers from 'saved' register map file (import register map)
        mock_file_open = mock_open(read_data=tmp_file_str)
        with patch(BUILTINS_NAME + '.open', mock_file_open):
            test_si534x_driver.si5345_i2c.apply_register_map('nofile.txt')

        # Check that reigsters have their values restored from file
        for page_no in test_si534x_driver.virtual_registers.keys():
            page_dict = test_si534x_driver.virtual_registers[page_no]
            #print("Checking assertions for page no {:02X}: {}".format(page_no, page_dict))
            for register in page_dict.keys():
                if register == 0x01:
                    # The page select register should not be checked
                    continue
                #print("\tChecking assertion for register {:02X}".format(register))
                assert(test_si534x_driver.virtual_registers[page_no][register] == page_no | register)

        # Test that verify will raise exception if there is a failure
        test_si534x_driver.si5345_i2c.i2c_bus.readU8.side_effect = [
                0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]    # Force smbus read to always return 0xFF
        mock_file_open = mock_open(read_data=tmp_file_str)
        with patch(BUILTINS_NAME + '.open', mock_file_open):
            # Check for exception
            with pytest.raises(SI534xCommsException, match=".*Write of byte to register.*"):
                test_si534x_driver.si5345_i2c.apply_register_map('nofile.txt', verify=True)

        test_si534x_driver.virtual_registers_en(False)  # smbus read reset


#TODO add tests for device function functions...
