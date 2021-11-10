"""
Tests for QSFP+/CXP FireFly Optical Transceiver control driver. The driver is I2CDevice-derived,
with the addition of select lines.

To Test:
    - [ ] Bit field read/write functions work correctly
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
from odin_devices.firefly import FireFly
import smbus
from odin_devices.i2c_device import I2CDevice
import gpiod


class firefly_test_fixture(object):
    def __init__(self):
        pass

@pytest.fixture(scope="class")
def test_firefly():
    test_driver_fixture = firefly_test_fixture()
    yield test_driver_fixture


class TestFireFly():
    def test_interface_detect(self, test_firefly):
        pass

