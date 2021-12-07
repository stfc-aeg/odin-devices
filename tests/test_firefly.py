"""
Tests for QSFP+/CXP FireFly Optical Transceiver control driver. The driver is I2CDevice-derived,
with the addition of select lines.

To Test:
    - [ ] Bit field read/write functions work correctly
    - [ ] Test pin selection
    - [ ] Interface Detection and PN field checking
    - [ ] Base address re-assignment
    - [ ] Initial channel state disable (for temperature safety)
    - [ ] Temperature reporting
    - [ ] Device Information Report
    - [ ] Channel Disable/Enable
    - [ ] Channel Disable Readback
    - Interface Specifics
        - [ ] Check some different fields read differently (and correctly) for different interface
                types (make sure some fields classed as Tx and some as Rx)
            - [ ] Make sure that the CXP interface handles separated Tx/Rx devices
            - [ ] Check page switching is handled
        - [ ] Different address assignment maps???

"""

import sys
import pytest
import time

if sys.version_info[0] == 3:                # pragma: no cover
    from unittest.mock import Mock, MagicMock, call, patch
    from importlib import reload as reload
else:                                       # pragma: no cover
    from mock import Mock, MagicMock, call, patch

sys.modules['smbus'] = MagicMock()
#sys.modules['gpiod.Line'] = MagicMock()
sys.modules['gpiod'] = MagicMock()
from odin_devices.firefly import FireFly, _interface_QSFP, _interface_CXP
import smbus
#from smbus import SMBus
from odin_devices.i2c_device import I2CDevice, I2CException
import gpiod


class firefly_test_fixture(object):
    def __init__(self):
        pass

@pytest.fixture(scope="class")
def test_firefly():
    test_driver_fixture = firefly_test_fixture()
    yield test_driver_fixture

# Create basic register structure. Both QSFP have a single lower page and upper pages
# numbered 00-02. There is a page select to move between these pages. Page 02 is
# optional, but has been used by Samtec. QSFP+ has an optional Page 03 for cable assys.
mock_registers_CXP = {'lower': {}, 'upper': {0: {}, 1: {}, 2: {}}}
mock_registers_CXP_PS = 0
mock_registers_QSFP = {'lower': {}, 'upper': {0: {}, 1: {}, 2: {}, 3: {}}}
mock_registers_QSFP_PS = 0
mock_registers_areCXP = True

QSFP_EXAMPLE_PN = [ord(x) for x in list('B0414xxx0x1xxx  ')]    # 4-channel duplex 14Gbps
CXP_EXAMPLE_PN  = [ord(x) for x in list('B1214xxx0x1xxx  ')]    # 12-channel duplex 14Gbps
TXRX_EXAMPLE_PN = [ord(x) for x in list('B0414xxx0114    ')]  # https://suddendocs.samtec.com/catalog_english/ecuo.pdf
TX_EXAMPLE_PN =  [ord(x) for x in list('T0414xxx0114    ')]  # https://suddendocs.samtec.com/catalog_english/ecuo.pdf


def model_I2C_readList(register, length):
    global mock_registers_areCXP, mock_registers_CXP_PS, mock_registers_QSFP_PS
    length = int(length)
    outlist = []
    for reg in range(register, register+length):
        outlist.append(model_I2C_readU8(reg))
    # Details will be printed on test failure
    print('returning {} from register starting {}'.format(outlist, register))
    print('\tmode is CXP? {}'.format('Yes' if mock_registers_areCXP else 'No'))
    print("\tFull register map: {}".format(mock_registers_CXP if mock_registers_areCXP else mock_registers_QSFP))
    return outlist


def model_I2C_readU8(register):
    global mock_registers_areCXP, mock_registers_CXP_PS, mock_registers_QSFP_PS
    try:
        #print("\t\tSearching for register {}".format(register))
        if register <= 127:     # Lower page
            return (mock_registers_CXP if mock_registers_areCXP else mock_registers_QSFP)['lower'][register]
        else:                   # Upper page(s)
            current_PS = mock_registers_CXP_PS if mock_registers_areCXP else mock_registers_QSFP_PS
            return (mock_registers_CXP if mock_registers_areCXP else mock_registers_QSFP)['upper'][current_PS][register]
    except KeyError:
        return 0



def model_I2C_write8(register, value):
    global mock_registers_areCXP, mock_registers_CXP_PS, mock_registers_QSFP_PS
    if register <= 127:     # Lower page
        (mock_registers_CXP if mock_registers_areCXP else mock_registers_QSFP)['lower'][register] = value
    else:                   # Upper page(s)
        current_PS = mock_registers_CXP_PS if mock_registers_areCXP else mock_registers_QSFP_PS
        (mock_registers_CXP if mock_registers_areCXP else mock_registers_QSFP)['upper'][current_PS][register] = value

    if register == 127:     # Page select
        if mock_registers_areCXP:
            mock_registers_CXP_PS = value
        else:
            mock_registers_QSFP_PS = value


def model_I2C_writeList(register, values):
    global mock_registers_areCXP, mock_registers_CXP_PS, mock_registers_QSFP_PS
    for i in range(0, len(values)):
        reg = register + i
        model_I2C_write8(reg, values[i])


def mock_I2C_SwitchDeviceQSFP():
    global mock_registers_areCXP, mock_registers_CXP_PS, mock_registers_QSFP_PS
    mock_registers_areCXP = False


def mock_I2C_SwitchDeviceCXP():
    global mock_registers_areCXP, mock_registers_CXP_PS, mock_registers_QSFP_PS
    mock_registers_areCXP = True

def mock_registers_reset():
    global mock_registers_areCXP, mock_registers_CXP_PS, mock_registers_QSFP_PS
    print("!!! Register Map Reset !!!")
    mock_registers_CXP['lower'] = {}
    mock_registers_QSFP['lower'] = {}
    mock_registers_CXP['upper'][0] = {
            168: 0x04, 169: 0xC8, 170: 0x80,    # Set OUI for interface recognition
            171: CXP_EXAMPLE_PN[0], 172: CXP_EXAMPLE_PN[1], 173: CXP_EXAMPLE_PN[2],
            174: CXP_EXAMPLE_PN[3], 175: CXP_EXAMPLE_PN[4], 176: CXP_EXAMPLE_PN[5],
            177: CXP_EXAMPLE_PN[6], 178: CXP_EXAMPLE_PN[7], 179: CXP_EXAMPLE_PN[8],
            180: CXP_EXAMPLE_PN[9], 181: CXP_EXAMPLE_PN[10], 182: CXP_EXAMPLE_PN[11],
            183: CXP_EXAMPLE_PN[12], 184: CXP_EXAMPLE_PN[13], 185: CXP_EXAMPLE_PN[14],
            186: CXP_EXAMPLE_PN[15],
    }
    mock_registers_QSFP['upper'][0] = {
            165: 0x04, 166: 0xC8, 167: 0x80,    # Set OUI for interface recognition
            168: QSFP_EXAMPLE_PN[0], 169: QSFP_EXAMPLE_PN[1], 170: QSFP_EXAMPLE_PN[2],
            171: QSFP_EXAMPLE_PN[3], 172: QSFP_EXAMPLE_PN[4], 173: QSFP_EXAMPLE_PN[5],
            174: QSFP_EXAMPLE_PN[6], 175: QSFP_EXAMPLE_PN[7], 176: QSFP_EXAMPLE_PN[8],
            177: QSFP_EXAMPLE_PN[9], 178: QSFP_EXAMPLE_PN[10], 179: QSFP_EXAMPLE_PN[11],
            180: QSFP_EXAMPLE_PN[12], 181: QSFP_EXAMPLE_PN[13], 182: QSFP_EXAMPLE_PN[14],
            183: QSFP_EXAMPLE_PN[15],
    }
    mock_registers_CXP['upper'][1] = {}
    mock_registers_QSFP['upper'][1] = {}
    mock_registers_CXP['upper'][2] = {}
    mock_registers_QSFP['upper'][2] = {}
    mock_registers_QSFP['upper'][3] = {}

    # Reset Page selects to 0
    mock_registers_CXP_PS = 0
    mock_registers_QSFP_PS = 0

    print("\tFull register maps: \n\t\tCXP: {},\n\t\tQSFP: {}".format(mock_registers_CXP, mock_registers_QSFP))


mock_I2C_readList = MagicMock()
mock_I2C_writeList = MagicMock()
mock_I2C_write8 = MagicMock()
mock_I2C_readU8 = MagicMock()


class TestFireFly():
    def test_interface_detect(self, test_firefly):
        """
        Check the interface detection process, which will be performed to determine
        if the device is QSFP+ or CXP. To perform this test, the select line needs to be used.
        """

        # Create relevant mocks
        writemock = MagicMock()
        readmock = MagicMock()
        temp_pin = MagicMock(spec=gpiod.Line)
        temp_pin.set_value = Mock()
        temp_pin.is_requested = Mock(); temp_pin.is_requested.return_value = True
        with \
                patch.object(I2CDevice, 'write8') as writemock, \
                patch.object(I2CDevice, 'readList') as readmock:

            # Check that the correct OUI address is read, using the correct write-read pattern
            writemock.reset_mock()
            readmock.reset_mock()
            FireFly._get_interface(select_line=temp_pin, default_address=0x50)
            writemock.assert_called_with(127, 0)        # Writes page 0 to page select byte
            readmock.assert_any_call(165, 3)            # Reads OUI bytes for QSFP+
            readmock.assert_any_call(168, 3)            # Reads OUI bytes for CXP

            # Check that reading the OUI for a QSFP+ device will result in identification
            readmock.side_effect = lambda reg, ln: {        # Set fake register to return expected count
                        165: [0x04, 0xC8, 0x80],        # QSFP+ OUI is Samtek
                        168: [0, 0, 0]}[reg]            # QSFP first 3 digits of PN)
            assert (FireFly._get_interface(select_line=temp_pin, default_address=0x50) == FireFly.INTERFACE_QSFP)

            # Check that reading the OUI for a CXP device will result in identification
            readmock.side_effect = lambda reg, ln: {        # Set fake register to return expected count
                        165: [0, 0, 0],                 # CXP end of vendor name in ASCII
                        168: [0x04, 0xC8, 0x80]}[reg]   # CXP OUI is Samtek
            assert (FireFly._get_interface(select_line=temp_pin, default_address=0x50) == FireFly.INTERFACE_CXP)

            # Check that an invalid value for both, return QSFP (may be 4-channel QSFP+, which does
            # not officially support the OUI
            readmock.side_effect = lambda reg, ln: [0, 0, 0]    # Return unexpected value
            assert (FireFly._get_interface(select_line=temp_pin, default_address=0x50) == FireFly.INTERFACE_QSFP)

        # Check that the mocking model for different types also works
        print("Testing the mocked registers:")
        with \
                patch.object(I2CDevice, 'write8') as mock_I2C_write8, \
                patch.object(I2CDevice, 'readU8') as mock_I2C_readU8, \
                patch.object(I2CDevice, 'writeList') as mock_I2C_writeList, \
                patch.object(I2CDevice, 'readList') as mock_I2C_readList:
            # Set up the mocks
            mock_I2C_readList.side_effect = model_I2C_readList
            mock_I2C_writeList.side_effect = model_I2C_writeList
            mock_I2C_write8.side_effect = model_I2C_write8
            mock_I2C_readU8.side_effect = model_I2C_readU8

            mock_registers_reset()          # reset the register systems

            mock_I2C_SwitchDeviceCXP()     # Model a CXP device
            assert (FireFly._get_interface(select_line=temp_pin, default_address=0x50) == FireFly.INTERFACE_CXP)

            mock_I2C_SwitchDeviceQSFP()     # Model a QSFP device
            assert (FireFly._get_interface(select_line=temp_pin, default_address=0x50) == FireFly.INTERFACE_QSFP)

    def test_page_switching_qsfp(self, test_firefly):
        # Check that selecting a field accessible on page 1 results in the page being changed
        # Since the mocking already simulates pages, this can be checked by placing data on the
        # virtual upper page 01 only to see if it is received correctly.

        with \
                patch.object(I2CDevice, 'write8') as mock_I2C_write8, \
                patch.object(I2CDevice, 'readU8') as mock_I2C_readU8, \
                patch.object(I2CDevice, 'writeList') as mock_I2C_writeList, \
                patch.object(I2CDevice, 'readList') as mock_I2C_readList:
            # Set up the mocks
            mock_I2C_readList.side_effect = model_I2C_readList
            mock_I2C_writeList.side_effect = model_I2C_writeList
            mock_I2C_write8.side_effect = model_I2C_write8
            mock_I2C_readU8.side_effect = model_I2C_readU8

            mock_registers_reset()          # reset the register systems, PS is 0

            mock_I2C_SwitchDeviceQSFP()     # Model a QSFP device
            test_firefly = FireFly()

            # Write to the I2C Address field, which is on upper page 2 using current interface
            test_firefly._interface.write_field(test_firefly._interface.FLD_I2C_Address, [0xAA])

            assert(mock_registers_QSFP['lower'][127] == 2)  # Check PS is now 2

            mock_registers_reset()          # reset the register systems, PS is 0

            mock_I2C_SwitchDeviceCXP()     # Model a CXP device
            test_firefly = FireFly()

            # Write to the I2C Address field, which is on upper page 2 using current interface
            test_firefly._interface.write_field(test_firefly._interface.FLD_I2C_Address, [0xAA])

            assert(mock_registers_CXP['lower'][127] == 2)  # Check PS is now 2

    def test_base_address_reassignment_qsfp(self, test_firefly):
        with \
                patch.object(I2CDevice, 'write8') as mock_I2C_write8, \
                patch.object(I2CDevice, 'readU8') as mock_I2C_readU8, \
                patch.object(I2CDevice, 'writeList') as mock_I2C_writeList, \
                patch.object(I2CDevice, 'readList') as mock_I2C_readList:
            # Set up the mocks
            mock_I2C_readList.side_effect = model_I2C_readList
            mock_I2C_writeList.side_effect = model_I2C_writeList
            mock_I2C_write8.side_effect = model_I2C_write8
            mock_I2C_readU8.side_effect = model_I2C_readU8

            mock_I2C_SwitchDeviceQSFP()     # Model a QSFP device
            mock_registers_reset()          # reset the register systems, PS is 0

            # Check that with no arguments, the base address is 0x50
            test_firefly = FireFly()
            assert(test_firefly._interface._device.address == 0x50)

            # Check that if a base address in correct range is set, it takes effect
            mock_registers_reset()          # reset the register systems, PS is 0
            test_firefly = FireFly(base_address=0x60)
            assert(test_firefly._interface._device.address == 0x60)

            # Check that if a base address out of range is set, the address stays the same
            mock_registers_reset()          # reset the register systems, PS is 0
            test_firefly = FireFly(base_address=0x90)
            assert(test_firefly._interface._device.address == 0x50)

    def test_base_address_reassignment_cxp(self, test_firefly):
        with \
                patch.object(I2CDevice, 'write8') as mock_I2C_write8, \
                patch.object(I2CDevice, 'readU8') as mock_I2C_readU8, \
                patch.object(I2CDevice, 'writeList') as mock_I2C_writeList, \
                patch.object(I2CDevice, 'readList') as mock_I2C_readList:
            # Set up the mocks
            mock_I2C_readList.side_effect = model_I2C_readList
            mock_I2C_writeList.side_effect = model_I2C_writeList
            mock_I2C_write8.side_effect = model_I2C_write8
            mock_I2C_readU8.side_effect = model_I2C_readU8

            mock_I2C_SwitchDeviceCXP()      # Model a CXP device
            mock_registers_reset()          # reset the register systems, PS is 0

            # CXP separates Tx and Rx activity.

            # Check that with no arguments, the base address is 0x50
            test_firefly = FireFly()
            assert(test_firefly._interface._tx_device.address == 0x50)

            # Check that if a base address in range 0x01-0x3F, either the address set or 0x50 is used
            mock_registers_reset()          # reset the register systems, PS is 0
            test_firefly = FireFly(base_address=0x30)
            assert(test_firefly._interface._tx_device.address == 0x50 or
                   test_firefly._interface._tx_device.address == 0x30)

            # Check that if a base address in range 0x40-0x7E, address set is used
            mock_registers_reset()          # reset the register systems, PS is 0
            test_firefly = FireFly(base_address=0x90)
            assert(test_firefly._interface._tx_device.address == 0x90)

            # Check that the Rx address is 4 above (when 7-bit) the Tx one
            mock_registers_reset()          # reset the register systems, PS is 0
            test_firefly = FireFly()
            assert(test_firefly._interface._rx_device.address ==
                   test_firefly._interface._tx_device.address + 4)

    def test_pin_control(self, test_firefly):
        pass

    def test_initial_channel_disable(self, test_firefly):
        with \
                patch.object(I2CDevice, 'write8') as mock_I2C_write8, \
                patch.object(I2CDevice, 'readU8') as mock_I2C_readU8, \
                patch.object(I2CDevice, 'writeList') as mock_I2C_writeList, \
                patch.object(I2CDevice, 'readList') as mock_I2C_readList:
            # Set up the mocks
            mock_I2C_readList.side_effect = model_I2C_readList
            mock_I2C_writeList.side_effect = model_I2C_writeList
            mock_I2C_write8.side_effect = model_I2C_write8
            mock_I2C_readU8.side_effect = model_I2C_readU8

            mock_registers_reset()          # reset the register systems, PS is 0

            mock_I2C_SwitchDeviceQSFP()     # Model a QSFP device
            test_firefly = FireFly()

            # Check that the Tx channels have been left in a disabled state assuming 4 channels
            assert(test_firefly.num_channels == 4)      # This test is valid for 4-channel devices
            assert(mock_registers_QSFP['lower'][86] & 0b1111 == 0b1111)         # Tx Disable bits

            mock_registers_reset()          # reset the register systems, PS is 0

            mock_I2C_SwitchDeviceCXP()     # Model a CXP device
            test_firefly = FireFly()

            # Check that the Tx channels have been left in a disabled state assuming 4 channels
            assert(test_firefly.num_channels == 12)      # This test is valid for 4-channel devices
            assert(mock_registers_CXP['lower'][52] & 0b1111 == 0b1111)      # Tx 08-11 Disable bits
            assert(mock_registers_CXP['lower'][53] == 0b11111111)           # Tx 00-07 Disable bits

    def test_tx_temp_reporting_qsfp(self, test_firefly):
        with \
                patch.object(I2CDevice, 'write8') as mock_I2C_write8, \
                patch.object(I2CDevice, 'readU8') as mock_I2C_readU8, \
                patch.object(I2CDevice, 'writeList') as mock_I2C_writeList, \
                patch.object(I2CDevice, 'readList') as mock_I2C_readList:
            # Set up the mocks
            mock_I2C_readList.side_effect = model_I2C_readList
            mock_I2C_writeList.side_effect = model_I2C_writeList
            mock_I2C_write8.side_effect = model_I2C_write8
            mock_I2C_readU8.side_effect = model_I2C_readU8

            mock_registers_reset()          # reset the register systems, PS is 0
            mock_I2C_SwitchDeviceQSFP()     # Model a QSFP device

            # Store temperature 40C in CXP device Tx/Rx and read result
            mock_registers_QSFP['lower'][22] = 0b00101000        # 2's compliment 8-bit
            test_firefly = FireFly()
            assert(test_firefly.get_temperature(direction=FireFly.DIRECTION_TX) == 40.0)

            # Check that the 2's comliment works by reading a negative back
            mock_registers_QSFP['lower'][22] = 0b10000000        # 2's compliment 8-bit
            test_firefly = FireFly()
            assert(test_firefly.get_temperature(direction=FireFly.DIRECTION_TX) == -128.0)

    def test_tx_temp_reporting_cxp(self, test_firefly):
        with \
                patch.object(I2CDevice, 'write8') as mock_I2C_write8, \
                patch.object(I2CDevice, 'readU8') as mock_I2C_readU8, \
                patch.object(I2CDevice, 'writeList') as mock_I2C_writeList, \
                patch.object(I2CDevice, 'readList') as mock_I2C_readList:
            # Set up the mocks
            mock_I2C_readList.side_effect = model_I2C_readList
            mock_I2C_writeList.side_effect = model_I2C_writeList
            mock_I2C_write8.side_effect = model_I2C_write8
            mock_I2C_readU8.side_effect = model_I2C_readU8

            mock_registers_reset()          # reset the register systems, PS is 0
            mock_I2C_SwitchDeviceCXP()     # Model a CXP device

            # Store temperature 40C in CXP device Tx and read result
            mock_registers_CXP['lower'][22] = 0b00101000        # 2's compliment 8-bit
            test_firefly = FireFly()
            assert(test_firefly.get_temperature(direction=FireFly.DIRECTION_TX) == 40.0)

            # Store temperature 40C in CXP device Rx (same register, different I2C address)
            mock_registers_CXP['lower'][22] = 0b00101000        # 2's compliment 8-bit
            test_firefly = FireFly()
            assert(test_firefly.get_temperature(direction=FireFly.DIRECTION_TX) == 40.0)

            # Check that the 2's comliment works by reading a negative back
            mock_registers_CXP['lower'][22] = 0b10000000        # 2's compliment 8-bit
            test_firefly = FireFly()
            assert(test_firefly.get_temperature(direction=FireFly.DIRECTION_TX) == -128.0)

            # Check that a duplex device supplied with no direction raises an error
            mock_registers_reset()          # reset the register systems, PS is 0
            test_firefly = FireFly()
            assert(test_firefly.direction == FireFly.DIRECTION_DUPLEX)  # Test valid for duplex
            with pytest.raises(I2CException, match=".*Invalid direction.*could not be derived.*"):
                test_firefly.get_temperature()

            # Check that a simplex device can infer direction
            mock_registers_reset()          # reset the register systems, PS is 0
            mock_registers_CXP['upper'][0][171] = ord('R') # Force PN to reflect Rx only device
            test_firefly = FireFly()
            assert(test_firefly.direction == FireFly.DIRECTION_RX)  # Test valid for Rx only
            mock_read_field = MagicMock()
            with patch.object(_interface_CXP, 'read_field') as mock_read_field:
                mock_read_field.return_value = [30]
                test_firefly.get_temperature()
                print(mock_read_field.mock_calls)

                # Assert that the Rx version was read
                mock_read_field.assert_called_with(_interface_CXP.FLD_Rx_Temperature)

                # Assert that the Tx version was not read
                assert(call(_interface_CXP.FLD_Rx_Temperature) in mock_read_field.mock_calls)
                assert(call(_interface_CXP.FLD_Tx_Temperature) not in mock_read_field.mock_calls)

    def test_device_info_report_pn(self, test_firefly):
        with \
                patch.object(I2CDevice, 'write8') as mock_I2C_write8, \
                patch.object(I2CDevice, 'readU8') as mock_I2C_readU8, \
                patch.object(I2CDevice, 'writeList') as mock_I2C_writeList, \
                patch.object(I2CDevice, 'readList') as mock_I2C_readList:
            # Set up the mocks
            mock_I2C_readList.side_effect = model_I2C_readList
            mock_I2C_writeList.side_effect = model_I2C_writeList
            mock_I2C_write8.side_effect = model_I2C_write8
            mock_I2C_readU8.side_effect = model_I2C_readU8

            mock_registers_reset()          # reset the register systems, PS is 0
            mock_I2C_SwitchDeviceQSFP()     # Model a QSFP device

            valid_part_number = 'B0425xxx0x1xxx  '
            input_vendor_name = 'PRETEND MANUFAC '

            I2CDevice.writeList(168, [ord(x) for x in valid_part_number])     # Insert info
            I2CDevice.writeList(148, [ord(x) for x in input_vendor_name])     # Insert info

            test_firefly = FireFly()

            # Check fields returned
            ret_pn, ret_vn, ret_oui = test_firefly.get_device_info()
            assert(valid_part_number == ret_pn)
            assert(input_vendor_name == ret_vn)
            # (OUI is already set to Samtec's one, or init will fail)

            # Check part number parts
            assert(test_firefly.data_rate_Gbps == 25)
            assert(test_firefly.num_channels == 4)

    def test_channel_enable_qsfp(self, test_firefly):
        pass

    def test_channel_enable_cxp(self, test_firefly):
        pass

    def test_channel_enable_readback_qsfp(self, test_firefly):
        pass

    def test_channel_enable_readback_cxp(self, test_firefly):
        pass

    def test_gpio_not_present(self, test_firefly):
        # Check that lack of GPIO will cause error
        #TODO

        # Check that other line errrors trigger errors
        #TODO
        pass
