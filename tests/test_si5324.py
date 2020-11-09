"""
Test Cases for the SI5324 class from odin_devices
Joseph Nobes, STFC Detector Systems Software Group
"""

import sys
import pytest
#import builtins
#import tempfile.NamedTemporaryFile as TmpFile

if sys.version_info[0] == 3:    # pragma: no cover
    from unittest.mock import Mock, mock_open, patch
else:                           # pramga: no cover
    from mock import Mock, mock_open, patch

sys.modules['smbus'] = Mock()
sys.modules['logging'] = Mock() # Track calls to logger.warning
from odin_devices.si5324 import SI5324, logger
from odin_devices.i2c_device import I2CDevice, I2CException

class si5324TestFixture(object):

    def __init__(self):
        self.si5324 = SI5324()  # Create with default address

        # Create virtual registers, init to 0x00
        self.registers = dict.fromkeys([0,1,2,3,4,5,6,7,8,9,
            10,11,19,
            20,21,22,23,24,25,
            31,32,33,34,35,36,
            40,41,42,43,44,45,46,47,48,
            55,
            128,129,
            130,131,132,134,135,136,137,138,139,
            142,143],
                0x00)

    def virtual_registers_en(self, en):
        if en:
            self.si5324.bus.read_byte_data.side_effect = self.read_virtual_regmap
            self.si5324.bus.write_byte_data.side_effect = self.write_virtual_regmap
        else:
            self.si5324.bus.read_byte_data.side_effect = None
            self.si5324.bus.write_byte_data.side_effect = None

    def read_virtual_regmap(self, address, register):
        return self.registers[register]

    def write_virtual_regmap(self, address, register, value):
        print ("Writing virtual register {} with 0x{:02X}".format(register, value))
        self.registers[register] = value

@pytest.fixture(scope="class")
def test_si5324_driver():
    test_driver_fixture = si5324TestFixture()
    yield test_driver_fixture


class TestSI5324():

    def test_addr_pins(self, test_si5324_driver):
        # Test initial address used in class matches address with all pins at GND
        assert test_si5324_driver.si5324.address == SI5324.pins_to_address(0,0,0)

        # Test pin address calculation works in correct positions
        assert SI5324.pins_to_address(1,1,1) == (0x68 + 0b111)
        assert SI5324.pins_to_address(1,0,0) == (0x68 + 0b100)
        assert SI5324.pins_to_address(0,1,0) == (0x68 + 0b010)
        assert SI5324.pins_to_address(0,0,1) == (0x68 + 0b001)

    def test_calibration_routine(self, test_si5324_driver):
        test_si5324_driver.virtual_registers_en(True)   # smbus read virtual registers

        # Check calibration performs correct register write, success is recognised
        test_si5324_driver.registers[130] = 0b0     # Preset LOL to indicate iCAL success
        cal_result = test_si5324_driver.si5324._run_ical()
        test_si5324_driver.si5324.bus.write_byte_data.assert_any_call(
                test_si5324_driver.si5324.address, 136, 0b01000000) # Check iCAL triggered
        assert cal_result == 0      # Check output was success

        # Check calibration failure is recognised when LOL stays high
        test_si5324_driver.registers[130] = 0b1     # Preset LOL to indicate iCAL failure
        cal_result = test_si5324_driver.si5324._run_ical(1000)
        arg = logger.warning.call_args()
        assert arg.contains("timed out")   # Check correct warning issued
        assert cal_result == 1      # Check failure reported

        # Check that if LOL is read as low after third try, still considered success
        test_si5324_driver.si5324.bus.read_byte_data.side_effect= [1,1,0]   # Set successive smbus reads
        cal_result = test_si5324_driver.si5324._run_ical()
        assert cal_result == 0      # Check success was reported

        test_si5324_driver.virtual_registers_en(False)  # smbus read reset

    def test_calibration_required(self, test_si5324_driver):
        test_si5324_driver.virtual_registers_en(True)   # smbus read virtual registers

        # Test running a calibration removes the flag
        test_si5324_driver.si5324.iCAL_required = True
        test_si5324_driver.registers[130] = 0b0         # Simulate LOL staying being low so cal exits
        test_si5324_driver.si5324.calibrate()
        assert test_si5324_driver.si5324.iCAL_required == False

        # Test editing a field within an iCAL sensitive register flags iCAL as required
        test_si5324_driver.si5324.iCAL_required = False
        test_si5324_driver.si5324.set_register_field(SI5324._FIELD_Free_Run_Mode,1)
        assert test_si5324_driver.si5324.iCAL_required == True

        test_si5324_driver.virtual_registers_en(False)  # smbus read reset

    def test_field_rw(self, test_si5324_driver):
        test_si5324_driver.virtual_registers_en(True)   # smbus read virtual registers

        # Field Writing:
        # Set two bits within a defined field (register 4, bits 7&6) low
        test_si5324_driver.registers[4] = 0xff      # Init register before modification
        test_si5324_driver.si5324.set_register_field(SI5324._FIELD_Autoselection, 0b00)

        # Check initial value was read from register
        test_si5324_driver.si5324.bus.read_byte_data.assert_any_call(
                test_si5324_driver.si5324.address, 4)

        # Check field bits written correctly into register
        test_si5324_driver.si5324.bus.write_byte_data.assert_any_call(
                test_si5324_driver.si5324.address, 4, 0b00111111)

        # Check verification failure if readback has not changed
        test_si5324_driver.si5324.bus.read_byte_data.side_effect = [0xFF,0xFF] # Force smbus read to always return 0xFF
        with pytest.raises(I2CException, match=".*not successfully written.*"): # Check for exception
            test_si5324_driver.si5324.set_register_field(
                    SI5324._FIELD_Autoselection, 0b00, True)   # Run with verify
        test_si5324_driver.virtual_registers_en(True)   # smbus read virtual registers


        # Field Reading:
        # Read two bits within a defined field (register 1, bits 3@2)
        test_si5324_driver.registers[1] = 0b00001100    # Init field to 0b11
        output_value = test_si5324_driver.si5324.get_register_field(
                SI5324._FIELD_Clock_2_Priority)

        # Check smbus read function is called as expected, return will be 0b00001000
        test_si5324_driver.si5324.bus.read_byte_data.assert_any_call(
                test_si5324_driver.si5324.address, 1)

        # Check correct bits have been extracted from the register
        assert output_value == 0b11

        test_si5324_driver.virtual_registers_en(False)  # smbus read reset

    def test_clock_manual_select(self, test_si5324_driver):
        test_si5324_driver.virtual_registers_en(True)   # smbus read virtual registers

        # Test setting of clock 1
        test_si5324_driver.registers[3] = 0b01000000    # Init to Clock 2 selected
        test_si5324_driver.si5324.set_clock_select(SI5324.CLOCK_1, False)
        assert test_si5324_driver.registers[3] & 0b11000000 == 0    # Check register set
        assert test_si5324_driver.si5324.get_clock_select() == SI5324.CLOCK_1 # Check read

        # Test setting of clock 2 with freerun init to on (external override)
        test_si5324_driver.registers[3] = 0b00000000    # Init to Clock 1 selected
        test_si5324_driver.registers[0] = 0b01000000    # Init freerun to on
        test_si5324_driver.si5324.set_clock_select(SI5324.CLOCK_2, False)
        assert test_si5324_driver.registers[3] & 0b11000000 == 0b01000000  # Check register set
        assert test_si5324_driver.registers[0] & 0b01000000 == 0    # Check freerun disabled
        assert test_si5324_driver.si5324.get_clock_select() == SI5324.CLOCK_2 # Check read

        # Test setting of clock X with freerun init to off
        test_si5324_driver.registers[3] = 0b00000000    # Init to Clock 1 selected
        test_si5324_driver.registers[0] = 0b00000000    # Init freerun to off
        test_si5324_driver.si5324.set_clock_select(SI5324.CLOCK_X, False)
        assert test_si5324_driver.registers[3] & 0b11000000 == 0b01000000  # Check register set
        assert test_si5324_driver.registers[0] & 0b01000000 == 0b01000000  # Check freerun disabled
        assert test_si5324_driver.si5324.get_clock_select() == SI5324.CLOCK_X # Check read

        # Test for autoselect warning
        test_si5324_driver.registers[4] = 0b10000000    # Enable revertive autoselection
        test_si5324_driver.si5324.set_clock_select(SI5324.CLOCK_1, True)
        test_si5324_driver.si5324.bus.read_byte_data.assert_any_call(   # Autosel reg read
                test_si5324_driver.si5324.address, 4)
        arg = logger.warning.call_args()
        assert arg.contains("auto-selection enabled")   # Warning correct

        # Test for invalid input
        with pytest.raises(I2CException, match="Incorrect clock.*"):
            test_si5324_driver.si5324.set_clock_select(0xFF)

        test_si5324_driver.virtual_registers_en(False)  # smbus read reset

    def test_active_clock(self, test_si5324_driver):
        test_si5324_driver.virtual_registers_en(True)   # smbus read virtual registers

        # Check active clock 1 does not depend on freerun
        test_si5324_driver.registers[128] = 0b01    # Set clock 1 active
        for test_si5324_driver.registers[0] in [0b01000000, 0b0]:   # Freerun on and off
            assert test_si5324_driver.si5324.get_active_clock() == SI5324.CLOCK_1

        # Check active clock 2 overridden with freerun
        test_si5324_driver.registers[128] = 0b10    # Set clock 2 active
        test_si5324_driver.registers[0] = 0b01000000    # Set freerun active
        assert test_si5324_driver.si5324.get_active_clock() == SI5324.CLOCK_X
        test_si5324_driver.registers[0] = 0b00000000    # Set freerun inactive
        assert test_si5324_driver.si5324.get_active_clock() == SI5324.CLOCK_2

        # Check no active clock always reports NONE
        test_si5324_driver.registers[128] = 0b00    # Set no clock active
        for test_si5324_driver.registers[0] in [0b01000000, 0b0]:   # Freerun on and off
            assert test_si5324_driver.si5324.get_active_clock() == SI5324.CLOCK_NONE

        test_si5324_driver.virtual_registers_en(False)  # smbus read reset

    def test_register_map(self, test_si5324_driver):
        test_si5324_driver.virtual_registers_en(True)   # smbus read virtual registers

        #Set virtual registers to have a value matching their register number
        for register, value in test_si5324_driver.registers.items():
            test_si5324_driver.registers[register] = register

        # Mock export to imaginary file
        mock_file_open = mock_open()
        with patch('builtins.open', mock_file_open):
            # Write temporary memory-based file
            test_si5324_driver.si5324.export_register_map('nofile.txt')
            mock_file_open.assert_called()

        # Assemble 'file' with written lines form write() calls
        tmp_file_str = ""
        for writeline in mock_file_open.mock_calls:
            if not "call().write" in str(writeline):
                continue
            tmp_file_str += str(writeline)[14:-4] + "\n"

        # Change all virtual register values to 0xFF
        for register in test_si5324_driver.registers.keys():
            test_si5324_driver.registers[register] = 0xFF

        # Write registers from 'saved' register map file
        mock_file_open = mock_open(read_data=tmp_file_str)
        test_si5324_driver.registers[130] = 0b0 # Preset LOL low to end CAL
        with patch('builtins.open', mock_file_open):
            test_si5324_driver.si5324.apply_register_map('nofile.txt')

        # Now all special export registers should have values matching
        # their number, and other registers should all still  be 0xFF.
        for register, value in test_si5324_driver.registers.items():
            print("Checking assertion for register {}: value {}".format(register, value))
            # Outliers
            if register == 136:
                # iCAL trigger, not written (triggered manually)
                continue
            elif register == 130:
                # LOL INT register forced low to end cal
                continue

            # Checks
            if register in SI5324._regmap_registers:
                assert register == value
            else:
                assert value == 0xff

        test_si5324_driver.virtual_registers_en(False)  # smbus read reset

    def test_alarm_states(self, test_si5324_driver):
        test_si5324_driver.virtual_registers_en(True)   # smbus read virtual registers

        # Set all alarms active (overriding smbus read to read virtual registers),
        # and check they are all read out as true.
        test_si5324_driver.registers[129] = 0b00000111      # Set all LOS INTs high
        test_si5324_driver.registers[131] = 0b00000111      # Set all LOS FLGs high
        test_si5324_driver.registers[130] = 0b00000111      # Set FOS, LOL INTs high
        test_si5324_driver.registers[132] = 0b00001110      # Set FOS, LOL FLGs high

        active_alarms = test_si5324_driver.si5324.get_alarm_states()

        assert not False in [active_alarms.Loss_Of_Lock_INT, active_alarms.Loss_Of_Lock_FLG,
                active_alarms.Loss_Of_Signal_1_INT, active_alarms.Loss_Of_Signal_1_FLG,
                active_alarms.Loss_Of_Signal_2_INT, active_alarms.Loss_Of_Signal_2_FLG,
                active_alarms.Loss_Of_Signal_X_INT, active_alarms.Loss_Of_Signal_X_FLG,
                active_alarms.Freq_Offset_1_INT, active_alarms.Freq_Offset_1_FLG,
                active_alarms.Freq_Offset_2_INT, active_alarms.Freq_Offset_1_FLG]

        # Same test with all INTs and FLGs set low
        test_si5324_driver.registers[129] = 0      # Set all LOS INTs high
        test_si5324_driver.registers[131] = 0      # Set all LOS FLGs high
        test_si5324_driver.registers[130] = 0      # Set FOS, LOL INTs high
        test_si5324_driver.registers[132] = 0      # Set FOS, LOL FLGs high

        active_alarms = test_si5324_driver.si5324.get_alarm_states()

        assert not True in [active_alarms.Loss_Of_Lock_INT, active_alarms.Loss_Of_Lock_FLG,
                active_alarms.Loss_Of_Signal_1_INT, active_alarms.Loss_Of_Signal_1_FLG,
                active_alarms.Loss_Of_Signal_2_INT, active_alarms.Loss_Of_Signal_2_FLG,
                active_alarms.Loss_Of_Signal_X_INT, active_alarms.Loss_Of_Signal_X_FLG,
                active_alarms.Freq_Offset_1_INT, active_alarms.Freq_Offset_1_FLG,
                active_alarms.Freq_Offset_2_INT, active_alarms.Freq_Offset_1_FLG]

        test_si5324_driver.virtual_registers_en(False)  # smbus read reset
