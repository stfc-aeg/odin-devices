import sys
import pytest

if sys.version_info[0] == 3:    # pragma: no cover
    from unittest.mock import Mock, MagicMock, mock_open, patch
    BUILTINS_NAME = 'builtins'
else:                           # pramga: no cover
    from mock import Mock, MagicMock, mock_open, patch
    BUILTINS_NAME = '__builtin__'

sys.modules['smbus'] = Mock()
#sys.modules['gpiod.Line'] = MagicMock()
sys.modules['gpiod'] = MagicMock()
import gpiod
sys.modules['logging'] = Mock() # Track calls to logger.warning
from odin_devices.si534x import _SI534x, SI5344, SI5345, SI5342, SI534xCommsException
from odin_devices.i2c_device import I2CException

class si534xTestFixture(object):

    def __init__(self):
        self.si5345_i2c = SI5345(i2c_address = 0xAA)
        self.virtual_registers = {0:{}, 1:{}, 2:{}, 3:{}, 4:{}, 5:{}, 6:{}, 7:{}, 8:{}, 9:{}, 0xA:{}, 0xB:{}}
        self.virtual_page_select = 0x00

    def virtual_registers_en(self, en, device=None):
        if device is None:
            device = self.si5345_i2c 
        if en:
            print("I2C interface now driving virtual register map")
            device.i2c_bus = Mock()
            device.i2c_bus.write8.side_effect = self.write_virtual_regmap
            device.i2c_bus.readU8.side_effect = self.read_virtual_regmap
        else:
            print("I2C interface now has no effect")

    def read_virtual_regmap(self, register):
        try:
            if register == 0x01:
                # This is the page select register
                print("REGISTER MOCK: Page select requested: ", self.virtual_page_select)
                return self.virtual_page_select
            else:
                print("REGISTER MOCK: Register 0x{:02X} page {} value requested: {}".format(
                    register, self.virtual_page_select,
                    self.virtual_registers[self.virtual_page_select][register]))
                return self.virtual_registers[self.virtual_page_select][register]
        except Exception as e:
            print("Failure to read register {} from page {}, returning 0".format(register,
                                                                                 self.virtual_page_select))
            print("Error: {}".format(e))
            return 0

    def write_virtual_regmap(self, register, value):
        try:
            if register == 0x01:
                # This is the page select register
                print("REGISTER MOCK: Page select changed: ", value)
                self.virtual_page_select = value
            else:
                print("REGISTER MOCK: Register 0x{:02X} page {} changed: {}".format(
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
        test_si534x_driver.virtual_registers_en(True)

        # Check that SI5345 adjusts channel-mapped registers by offset correctly
        test_si534x_driver.virtual_registers[0x01][0x08] = 0                    # Bit not set for ch0
        test_si534x_driver.si5345_i2c._output_driver_cfg_OE.write(0b1, 0)       # Enable channel 0
        assert(test_si534x_driver.virtual_registers[0x01][0x08] & 0b10 > 0)     # Bit was set for ch0
        test_si534x_driver.virtual_registers[0x01][0x21] = 0                    # Bit not set for ch5
        test_si534x_driver.si5345_i2c._output_driver_cfg_OE.write(0b1, 5)       # Enable channel 5
        assert(test_si534x_driver.virtual_registers[0x01][0x21] & 0b10 > 0)     # Bit was set for ch5

        test_si534x_driver.virtual_registers_en(False)

        # Check that SI5344 register numbering is adjusted and positioned correctly, since SI5344
        # channel 0 is at address 0x0112, equaivalent to SI5345 channel 2
        test_si5344 = SI5344(i2c_address=0xAA)      # Use same virtual register map
        test_si534x_driver.virtual_registers_en(True, test_si5344)

        test_si534x_driver.virtual_registers[0x01][0x12] = 0                    # Bit not set for ch0
        test_si5344._output_driver_cfg_OE.write(0b1, 0)                         # Enable channel 0
        assert(test_si534x_driver.virtual_registers[0x01][0x12] & 0b10 > 0)     # Bit was set for ch0

        test_si534x_driver.virtual_registers_en(False, test_si5344)

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

    def test_instantiate_different_devices(self, test_si534x_driver):
        device_si5345 = SI5345(i2c_address = 0xAA)
        assert(device_si5345._num_multisynths == 5)
        assert(device_si5345._num_channels == 10)

        device_si5344 = SI5344(i2c_address = 0xAA)
        assert(device_si5344._num_multisynths == 4)
        assert(device_si5344._num_channels == 4)

        device_si5342 = SI5342(i2c_address = 0xAA)
        assert(device_si5342._num_multisynths == 2)
        assert(device_si5342._num_channels == 2)

    def test_multisynth_channel_translation(self, test_si534x_driver):
        # This is a conversion that uses dynamic channel-multisynth allocations set by registers
        # within the device, so is more complex than it might seem. Uses output crosspoint switch.

        test_si534x_driver.virtual_registers_en(True)

        # Set registers to represent multisynth 0 <-> out 1 and multisynth 1 <-> out 0
        test_si534x_driver.virtual_registers[0x01][0x0B] = 1    # OUT0_MUX_SEL: out 0 <-> MUX N1
        test_si534x_driver.virtual_registers[0x01][0x10] = 0    # OUT1_MUX_SEL: out 1 <-> MUX N0

        # Check that the readout matches when getting multisynth from channel
        assert(test_si534x_driver.si5345_i2c.get_multisynth_from_channel(0) == 1)
        assert(test_si534x_driver.si5345_i2c.get_multisynth_from_channel(1) == 0)

        # Check that the readout matches when getting channel(s) from multisynth
        assert(1 in test_si534x_driver.si5345_i2c.get_channels_from_multisynth(0))
        assert(0 in test_si534x_driver.si5345_i2c.get_channels_from_multisynth(1))

        test_si534x_driver.virtual_registers_en(False)

    def test_get_fault_report(self, test_si534x_driver):
        test_si534x_driver.virtual_registers_en(True)

        # Without faults, check that the fault report is clear
        test_si534x_driver.virtual_registers[0x00][0x0D] = 0b00000000   # LOS, OOF 0-3 inactive
        test_si534x_driver.virtual_registers[0x00][0x12] = 0b00000000   # LOS, OOF FLG inactive
        test_si534x_driver.virtual_registers[0x00][0x0C] = 0b00000000   # LOS XTAL inactive
        test_si534x_driver.virtual_registers[0x00][0x11] = 0b00000000   # LOS XTAL FLG inactive
        test_si534x_driver.virtual_registers[0x00][0x0E] = 0b00000000   # LOL inactive
        test_si534x_driver.virtual_registers[0x00][0x13] = 0b00000000   # LOL FLG inactive
        fault_report = test_si534x_driver.si5345_i2c.get_fault_report()
        assert(fault_report.lol_status is False)
        assert(fault_report.lol_flag is False)
        assert(fault_report.los_xtal_status is False)
        assert(fault_report.los_xtal_flag is False)
        assert(fault_report.los_input_status == [False, False, False, False])
        assert(fault_report.los_input_flag == [False, False, False, False])
        assert(fault_report.oof_input_status == [False, False, False, False])
        assert(fault_report.oof_input_flag == [False, False, False, False])
        assert(fault_report.has_fault() is False)
        assert(fault_report.had_fault() is False)
        assert('No currently active faults' in fault_report.__repr__())
        assert('No currently flagged faults' in fault_report.__repr__())

        # With a current fault, check that the correct fault is reported
        test_si534x_driver.virtual_registers[0x00][0x0C] = 0b00000010   # LOS XTAL active
        test_si534x_driver.virtual_registers[0x00][0x11] = 0b00000010   # LOS XTAL FLG active
        test_si534x_driver.virtual_registers[0x00][0x0D] = 0b00000100   # LOS 2 active
        test_si534x_driver.virtual_registers[0x00][0x12] = 0b00000100   # LOS 2 FLG active
        fault_report = test_si534x_driver.si5345_i2c.get_fault_report()
        assert(fault_report.los_xtal_status is True)
        assert(fault_report.los_xtal_flag is True)
        assert(fault_report.los_input_status == [False, False, True, False])
        assert(fault_report.los_input_flag == [False, False, True, False])
        assert(fault_report.has_fault() is True)
        assert(fault_report.had_fault() is True)
        assert('Faults Active' in fault_report.__repr__())
        assert('Faults Flagged' in fault_report.__repr__())

        # With a past (flagged) fault, check that the correct fault is reported
        test_si534x_driver.virtual_registers[0x00][0x0C] = 0b00000000   # LOS XTAL active
        test_si534x_driver.virtual_registers[0x00][0x11] = 0b00000010   # LOS XTAL FLG active
        test_si534x_driver.virtual_registers[0x00][0x0D] = 0b00000000   # LOS 2 active
        test_si534x_driver.virtual_registers[0x00][0x12] = 0b00000100   # LOS 2 FLG active
        fault_report = test_si534x_driver.si5345_i2c.get_fault_report()
        assert(fault_report.los_xtal_status is False)
        assert(fault_report.los_xtal_flag is True)
        assert(fault_report.los_input_status == [False, False, False, False])
        assert(fault_report.los_input_flag == [False, False, True, False])
        assert(fault_report.has_fault() is False)
        assert(fault_report.had_fault() is True)
        assert('No currently active faults' in fault_report.__repr__())
        assert('Faults Flagged' in fault_report.__repr__())

        test_si534x_driver.virtual_registers_en(False)


        # Create a new device for testing behaviour with fault pins
        tmp_lolpin = MagicMock(spec=gpiod.Line)
        tmp_lolpin.set_value = Mock()
        tmp_lolpin.get_value = Mock()
        tmp_intpin = MagicMock(spec=gpiod.Line)
        tmp_intpin.set_value = Mock()
        tmp_intpin.get_value = Mock()
        tmp_pin_device = SI5345(i2c_address=0xAA, LOL_Line=tmp_lolpin, INT_Line=tmp_intpin)
        test_si534x_driver.virtual_registers_en(True, tmp_pin_device)

        # Check that if using inactive pins, the fault report is blank and the registers are not read
        test_si534x_driver.si5345_i2c.i2c_bus.readU8.reset_mock()
        tmp_lolpin.get_value.side_effect = lambda: 1        # Low nLOL pin means interrupt
        tmp_intpin.get_value.side_effect = lambda: 1        # Low nINT pin means interrupt
        tmp_pin_device.get_fault_report(attempt_use_pins=True)
        tmp_pin_device.i2c_bus.readU8.assert_not_called()

        # Check that if using pins, and LOL/nINT is active, registers are read
        test_si534x_driver.si5345_i2c.i2c_bus.readU8.reset_mock()
        tmp_lolpin.get_value.side_effect = lambda: 0        # Low nLOL pin means interrupt
        tmp_intpin.get_value.side_effect = lambda: 1        # Low nINT pin means interrupt
        tmp_pin_device.get_fault_report(attempt_use_pins=True)
        tmp_pin_device.i2c_bus.readU8.assert_called()           # Called when LOL indicated

        test_si534x_driver.si5345_i2c.i2c_bus.readU8.reset_mock()
        tmp_lolpin.get_value.side_effect = lambda: 1        # Low nLOL pin means interrupt
        tmp_intpin.get_value.side_effect = lambda: 0        # Low nINT pin means interrupt
        tmp_pin_device.get_fault_report(attempt_use_pins=True)
        tmp_pin_device.i2c_bus.readU8.assert_called()           # Called when INT indicated

        test_si534x_driver.virtual_registers_en(False, tmp_pin_device)

    def test_clear_fault_flag(self, test_si534x_driver):
        test_si534x_driver.virtual_registers_en(True)

        # Adapt register write mock so that only writing 0's takes effect (clears flags)
        tmp_clear_bits_mock = Mock()
        def tmp_clear_bits_mock_write8 (register, value):
            if register == 127: test_si534x_driver.write_virtual_regmap(register, value)    # Page Sel
            oldval = test_si534x_driver.read_virtual_regmap(register)
            test_si534x_driver.write_virtual_regmap(register, oldval & value)        # It works, trust me

        def set_all_flags_high():
            test_si534x_driver.virtual_registers[0x00][0x12] = 0b11111111   # LOS, OOF FLG inactive
            test_si534x_driver.virtual_registers[0x00][0x11] = 0b00000010   # LOS XTAL FLG inactive
            test_si534x_driver.virtual_registers[0x00][0x13] = 0b00000010   # LOL FLG inactive

        with patch.object(test_si534x_driver.si5345_i2c.i2c_bus, 'write8') as tmp_clear_bits_mock:
            tmp_clear_bits_mock.side_effect = tmp_clear_bits_mock_write8

            # Check clear of all flags results in all flag bits being written 0
            set_all_flags_high()

            fault_report = test_si534x_driver.si5345_i2c.get_fault_report()
            assert(fault_report.had_fault())                                # Check setup correct

            test_si534x_driver.si5345_i2c.clear_fault_flag(ALL=True)        # Clear the faults
            fault_report = test_si534x_driver.si5345_i2c.get_fault_report()

            print("Fault register contents (should be clear):\n\t0x12:{}\n\t0x11:{}\n\t0x13:{}".format(
                test_si534x_driver.virtual_registers[0x00][0x12],
                test_si534x_driver.virtual_registers[0x00][0x11],
                test_si534x_driver.virtual_registers[0x00][0x13]))
            assert(not fault_report.had_fault())                            # Check faults were cleared

            # Check LOL Clear
            set_all_flags_high()
            test_si534x_driver.si5345_i2c.clear_fault_flag(LOL=True)
            fault_report = test_si534x_driver.si5345_i2c.get_fault_report()
            print(fault_report)                             # Print will show state on fail
            assert(not fault_report.lol_flag)               # LOL should have been cleared
            assert(False not in fault_report.oof_input_flag)    # All OOF should still be active
            assert(False not in fault_report.los_input_flag)    # All LOS should still be active
            assert(fault_report.los_xtal_flag)                  # XTAL LOS should still be active

            # Check OOF 2 Clear
            set_all_flags_high()
            test_si534x_driver.si5345_i2c.clear_fault_flag(OOF2=True)
            fault_report = test_si534x_driver.si5345_i2c.get_fault_report()
            print(fault_report)                             # Print will show state on fail
            assert(not fault_report.oof_input_flag[2])      # OOF 2 should have been cleared
            assert(fault_report.oof_input_flag[3])          # OOF 3 should still be active
            assert(False not in fault_report.los_input_flag)    # All LOS should still be active
            assert(fault_report.los_xtal_flag)                  # XTAL LOS should still be active
            assert(fault_report.lol_flag)                   # LOL should still be active

            # Check LOS 2 Clear
            set_all_flags_high()
            test_si534x_driver.si5345_i2c.clear_fault_flag(LOS2=True)
            fault_report = test_si534x_driver.si5345_i2c.get_fault_report()
            print(fault_report)                             # Print will show state on fail
            assert(not fault_report.los_input_flag[2])      # LOS 2 should have been cleared
            assert(fault_report.los_input_flag[3])          # LOS 3 should still be active
            assert(False not in fault_report.oof_input_flag)    # All OOF should still be active
            assert(fault_report.los_xtal_flag)                  # XTAL LOS should still be active
            assert(fault_report.lol_flag)                   # LOL should still be active

            # Check XTAL LOS Clear
            set_all_flags_high()
            test_si534x_driver.si5345_i2c.clear_fault_flag(LOSXTAL=True)
            fault_report = test_si534x_driver.si5345_i2c.get_fault_report()
            print(fault_report)                             # Print will show state on fail
            assert(not fault_report.los_xtal_flag)              # XTAL LOS should have been cleared
            assert(False not in fault_report.oof_input_flag)    # All OOF should still be active
            assert(False not in fault_report.los_input_flag)    # All LOS should still be active
            assert(fault_report.lol_flag)                       # LOL should still be active

        test_si534x_driver.virtual_registers_en(False)

    def test_reset(self, test_si534x_driver):
        test_si534x_driver.virtual_registers_en(True)

        # Test hard reset (the detault)
        test_si534x_driver.si5345_i2c.i2c_bus.write8.reset_mock()
        test_si534x_driver.write_virtual_regmap(127, 0)         # Page select 0
        test_si534x_driver.write_virtual_regmap(0x1E, 0)        # Init register to all 0's
        test_si534x_driver.si5345_i2c.reset()
        print(test_si534x_driver.si5345_i2c.i2c_bus.write8.mock_calls)
        test_si534x_driver.si5345_i2c.i2c_bus.write8.assert_any_call(0x1E, 0b10)    # 1 Written
        assert(test_si534x_driver.virtual_registers[0x00][0x1E] & 0b10 == 0)    # left out of reset

        # Test soft reset
        test_si534x_driver.si5345_i2c.i2c_bus.write8.reset_mock()
        test_si534x_driver.write_virtual_regmap(127, 0)         # Page select 0
        test_si534x_driver.write_virtual_regmap(0x1C, 0)        # Init register to all 0's
        test_si534x_driver.si5345_i2c.reset(soft=True)
        print(test_si534x_driver.si5345_i2c.i2c_bus.write8.mock_calls)
        test_si534x_driver.si5345_i2c.i2c_bus.write8.assert_any_call(0x1c, 0b100)    # 1 Written
        assert(test_si534x_driver.virtual_registers[0x00][0x1C] & 0b100 == 0)    # left out of reset

        test_si534x_driver.virtual_registers_en(False)

    def test_set_channel_output_enabled(self, test_si534x_driver):
        # Channel mapped fields have been tested already.

        test_si534x_driver.virtual_registers_en(True)

        # Check that SI5345 adjusts channel-mapped registers by offset correctly
        test_si534x_driver.virtual_registers[0x01][0x21] = 0                    # Bit not set for ch5
        test_si534x_driver.si5345_i2c._output_driver_cfg_OE.write(0b1, 5)       # Enable channel 5
        assert(test_si534x_driver.virtual_registers[0x01][0x21] & 0b10 > 0)     # Bit was set for ch5

        # Check that setting a channel to enabled works
        test_si534x_driver.virtual_registers[0x01][0x08] = 0                    # Bit not set for ch0
        test_si534x_driver.si5345_i2c.set_channel_output_enabled(0, True)       # Enable channel 0
        assert(test_si534x_driver.virtual_registers[0x01][0x08] & 0b10 > 0)     # Bit was set for ch0

        # Check that disabling the channel works
        test_si534x_driver.si5345_i2c.set_channel_output_enabled(0, False)      # Disable channel 0
        assert(test_si534x_driver.virtual_registers[0x01][0x08] & 0b10 == 0)    # Bit not set for ch0

        # Check that if the all-channel-disable is active, enabling a channel disables it
        test_si534x_driver.virtual_registers[0x01][0x21] = 0                    # Bit not set for ch5
        test_si534x_driver.virtual_registers[0x01][0x02] = 0    # OUTALL_DISABLE_LOW disable all drivers
        test_si534x_driver.si5345_i2c.set_channel_output_enabled(0, True)       # Enable channel 0
        assert(test_si534x_driver.virtual_registers[0x01][0x02] & 0b1 == 1)     # Drivers enabled 

        test_si534x_driver.virtual_registers_en(False)

    def test_get_channel_output_enabled(self, test_si534x_driver):
        # This assumes the above test has passed

        test_si534x_driver.virtual_registers_en(True)

        test_si534x_driver.si5345_i2c.set_channel_output_enabled(0, True)       # Enable channel 0
        assert(test_si534x_driver.si5345_i2c.get_channel_output_enabled(0))

        test_si534x_driver.si5345_i2c.set_channel_output_enabled(0, False)       # Disable channel 0
        assert(not test_si534x_driver.si5345_i2c.get_channel_output_enabled(0))

        test_si534x_driver.virtual_registers_en(False)

    def test_increment_decrement_multisynth(self, test_si534x_driver):
        pass

    def test_increment_decrement_channel(self, test_si534x_driver):
        pass
