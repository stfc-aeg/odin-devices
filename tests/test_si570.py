"""Test Cases for the SI570 class from odin_devices
Adam Neaves, STFC Detector Systems Software Group
"""

import sys

import pytest

if sys.version_info[0] == 3:  # pragma: no cover
    from unittest.mock import Mock, call, patch
else:                         # pragma: no cover
    from mock import Mock, call, patch

sys.modules['smbus'] = Mock()
from odin_devices.si570 import SI570


class si570TestFixture(object):

    def __init__(self):
        self.address = 0x5d
        self.busnum = 1
        self.model = SI570.SI570_C
        with patch("odin_devices.si570.SI570.readU8") as mocked_readu8, \
             patch("odin_devices.si570.SI570.readList") as mocked_readlist:
            mocked_readu8.return_value = 0
            mocked_readlist.side_effect = self.readList_side_effect
            self.driver = SI570(self.address, self.model, busnum=self.busnum)

    def readList_side_effect(self, reg, length):
        return [i for i in range(length)]


@pytest.fixture(scope="class")
def test_si570_driver():
    test_fixture = si570TestFixture()
    yield test_fixture


class TestSI570():

    # @pytest.mark.skip(reason="Getting an out of index error")
    def test_fake(self, test_si570_driver):
        # dummy test case as placeholder
        assert True
