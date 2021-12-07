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
from odin_devices.i2c_device import I2CDevice
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
CXP_EXAMPLE_PN  = [ord(x) for x in list('T1214xxx0x1xxx  ')]    # 12-channel Tx 14Gbps
TXRX_EXAMPLE_PN = [ord(x) for x in list('B0414xxx0114    ')]  # https://suddendocs.samtec.com/catalog_english/ecuo.pdf
TX_EXAMPLE_PN =  [ord(x) for x in list('T0414xxx0114    ')]  # https://suddendocs.samtec.com/catalog_english/ecuo.pdf


def model_I2C_readList(register, length):
    global mock_registers_areCXP, mock_registers_CXP_PS, mock_registers_QSFP_PS
    outlist = []
    for reg in range(register, register+length):
        outlist.append(model_I2C_readU8(reg))
    # Details will be printed on test failure
    print('returning {} from register starting {}'.format(outlist, register))
    print('\tmode is CXP? {}'.format('Yes' if mock_registers_areCXP else 'No'))
    print("\tFull register map: {}".format(mock_registers_QSFP if mock_registers_areCXP else mock_registers_QSFP))
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

    # Reset Page selects to 0
    mock_registers_CXP_PS = 0
    mock_registers_QSFP_PS = 0


mock_I2C_readList = MagicMock()
mock_I2C_writeList = MagicMock()
mock_I2C_write8 = MagicMock()
mock_I2C_readU8 = MagicMock()


class TestFireFly():
    def test_interface_detect(self, test_firefly):
        pass

