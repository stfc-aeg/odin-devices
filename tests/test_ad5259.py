import sys
import pytest

if sys.version_info[0] == 3:    # pragma: no cover
    from unittest.mock import Mock, MagicMock, mock_open, patch
    BUILTINS_NAME = 'builtins'
else:                           # pramga: no cover
    from mock import Mock, MagicMock, mock_open, patch
    BUILTINS_NAME = '__builtin__'

sys.modules['smbus'] = MagicMock()

from odin_devices.ad5259 import AD5259
from odin_devices.i2c_device import I2CException

class ad5259TestFixture(object):
    def __init__(self, address=0, busnum=0, voltage_A=None, voltage_B=None):
        # Base instance has no optional args so that errors thrown when args are required can be tested.
        self.ad5259 = AD5259(address=address, busnum=busnum, voltage_A=voltage_A, voltage_B=voltage_B)

        # Mock the read and write functions
        self.ad5259.set_wiper_count = Mock()
        self.ad5259.set_wiper_count.side_effect = self.mock_write_count
        self.ad5259.get_wiper_count = Mock()
        self.ad5259.get_wiper_count.side_effect = self.mock_read_count

        # Virtual count value
        self.D = 0

    # Mock register read-write here
    def mock_read_count(self):
        return int(self.D)

    def mock_write_count(self, val):
        self.D = int(val)

@pytest.fixture(scope="class")
def test_driver():
    test_driver_fixture = ad5259TestFixture()
    yield test_driver_fixture

class TestAD5259():

    def test_i2c_init(self, test_driver):
        #TODO
        pass

    def test_pins_to_address(self, test_driver):
        # Check that supplying address pins returns the correct address
        assert(test_driver.ad5259.ad_pins_to_address(AD0=0, AD1=0) == 0b0011000)
        assert(test_driver.ad5259.ad_pins_to_address(AD0=1, AD1=0) == 0b1001100)
        assert(test_driver.ad5259.ad_pins_to_address(AD0=0, AD1=1) == 0b0011010)
        assert(test_driver.ad5259.ad_pins_to_address(AD0=1, AD1=1) == 0b1001110)

    def test_set_R_AB_valid(self, test_driver):
        # Check that setting R_AB with a valid value works
        test_driver.ad5259.set_resistance_AB_kohms(50)

        # Check that sending an invalid value throws an error
        with pytest.raises(Exception, match=".*Invalid.*"):
            test_driver.ad5259.set_resistance_AB_kohms(50000)

    def test_get_resistance_term_wiper(self, test_driver):
        # Check that if the R_AB has not been set, an error is thrown
        with pytest.raises(Exception, match=".*R_AB.*"):
            test_driver.ad5259._R_AB = None
            test_driver.ad5259.get_resistance_AW()

        # Test that if the wiper is set half way on a 50k potentiometer, it reads correctly. This value
        # has been worked out manually using the formula in the datasheet. Both for BW an AW.
        test_driver.D = 127
        test_driver.ad5259.set_resistance_AB_kohms(50)
        assumed_Rw = 75     # Assume that my driver is using the typical listed value
        assert(test_driver.ad5259.get_resistance_AW() == 25195.3125 + (2 * assumed_Rw))
        assert(test_driver.ad5259.get_resistance_BW() == 24804.6875 + (2 * assumed_Rw))

        # Test that if the wiper is set to count 100 on a 5k potentiometer, it reads correctly. This value
        # has been worked out manually using the formula in the datasheet. Both for BW an AW.
        test_driver.D = 100
        test_driver.ad5259.set_resistance_AB_kohms(5)
        assumed_Rw = 75     # Assume that my driver is using the typical listed value
        assert(test_driver.ad5259.get_resistance_AW() == 3046.875 + (2 * assumed_Rw))
        assert(test_driver.ad5259.get_resistance_BW() == 1953.125 + (2 * assumed_Rw))

    def test_set_resistance_term_wiper(self, test_driver):
        # Check that if the R_AB has not been set, an error is thrown
        with pytest.raises(Exception, match=".*R_AB.*"):
            test_driver.ad5259._R_AB = None
            test_driver.ad5259.set_resistance_AW(1)

        # Check that setting an impossible resistance throws an error
        with pytest.raises(Exception, match=".*Invalid R_AW.*"):
            test_driver.ad5259.set_resistance_AB_kohms(50)
            test_driver.ad5259.set_resistance_BW(60000)

        # Check that if an AW resistance of 10k is desired for a 100k potentiometer, it sets the closest D
        # value. Calculated manually using formula in the datasheet. Both BW and AW.
        # Calcaultion assumes that Rw is 75 ohms, gets D as 230.784, meaning the closest should be 231
        test_driver.ad5259.set_resistance_AB_kohms(100)
        test_driver.ad5259.set_resistance_AW(10000)
        assert(test_driver.D == 231)

        # Setting the same for resistance BW should result in raw D of 25.216, so closest 25
        test_driver.ad5259.set_resistance_BW(10000)
        assert(test_driver.D == 25)

    def test_get_wiper_voltage(self, test_driver):
        # Test that if either V_A or V_B is not set, an error is thrown
        with pytest.raises(Exception, match=".*V_A.*"):
            test_driver.ad5259._V_A = None
            test_driver.ad5259.get_wiper_voltage()
        with pytest.raises(Exception, match=".*V_B.*"):
            test_driver.ad5259._V_B = None
            test_driver.ad5259.get_wiper_voltage()

        # Test that if init with init with B as 0, error is not thrown
        tmp_drv = ad5259TestFixture(voltage_A = 1, voltage_B = 0)
        tmp_drv.ad5259.get_wiper_voltage()

        # Test that if R_AB is not set, the less accurate approximation is used
        # If the less accurate formula is used and voltage AB is 3v, the calculated value for count 200
        # will be 2.34375
        test_driver.ad5259.set_voltage_A(3)
        test_driver.ad5259.set_voltage_B(0)
        test_driver.D = 200
        test_driver.ad5259._R_AB = None
        assert(test_driver.ad5259.get_wiper_voltage() == 2.34375)

        # Check that supplying different arguments for V_A or V_B overrides the output
        test_driver.ad5259.set_voltage_A(1000000)     # Set stored value to something stupid
        test_driver.ad5259.set_voltage_B(1000000)     # Set stored value to something stupid
        test_driver.D = 200
        test_driver.ad5259._R_AB = None
        assert(test_driver.ad5259.get_wiper_voltage(voltage_A=3, voltage_B=0) == 2.34375)

        # Test that if R_AB is set, the accurate method is used
        # Using the more accurate formula, the voltage is (for a 50k pot) and Rw=75
        test_driver.ad5259.set_voltage_A(3)
        test_driver.ad5259.set_voltage_B(0)
        test_driver.D = 200
        test_driver.ad5259.set_resistance_AB_kohms(50)
        assert(test_driver.ad5259.get_wiper_voltage() == 2.35275)

        # Test that if B is above 0, the approximate calculation is still correct
        test_driver.ad5259.set_voltage_A(3)
        test_driver.ad5259.set_voltage_B(1)
        test_driver.D = 200
        test_driver.ad5259._R_AB = None
        assert(test_driver.ad5259.get_wiper_voltage() == 2.5625)

        # Test that if B is above 0, the accurate calculation is still correct
        test_driver.ad5259.set_voltage_A(3)
        test_driver.ad5259.set_voltage_B(1)
        test_driver.D = 200
        test_driver.ad5259.set_resistance_AB_kohms(50)
        assert(test_driver.ad5259.get_wiper_voltage() == 2.5745)

    def test_set_wiper_voltage(self, test_driver):
        # Test that if either V_A or V_B is not set, an error is thrown
        with pytest.raises(Exception, match=".*V_A.*"):
            test_driver.ad5259._V_A = None
            test_driver.ad5259.set_wiper_voltage(0)
        with pytest.raises(Exception, match=".*V_B.*"):
            test_driver.ad5259._V_B = None
            test_driver.ad5259.set_wiper_voltage(0)

        # For simplicity, I will use the same values in the above function for getting the wiper
        # values.

        # Test that if R_AB is not set, the less accurate approximation is used
        test_driver.ad5259.set_voltage_A(3)
        test_driver.ad5259.set_voltage_B(0)
        test_driver.ad5259._R_AB = None
        test_driver.ad5259.set_wiper_voltage(2.34375)
        assert(test_driver.D == 200)
        # Check that I'm not getting a false positive
        test_driver.ad5259.set_wiper_voltage(2.35275)
        assert(test_driver.D != 200)

        # Test that if R_AB is set, the accurate method is used
        test_driver.ad5259._R_AB = 50000
        test_driver.ad5259.set_wiper_voltage(2.34375)
        assert(test_driver.D != 200)
        # Check that I'm not getting a false positive
        test_driver.ad5259.set_wiper_voltage(2.35275)
        assert(test_driver.D == 200)

        # Test that if the target is out of range, an error is thrown, both modes
        with pytest.raises(Exception, match=".*V_A.*"):
            test_driver.ad5259._V_A = 1
            test_driver.ad5259._V_B = 1
            test_driver.ad5259._R_AB = None
            test_driver.ad5259.set_wiper_voltage(2)
        with pytest.raises(Exception, match=".*V_A.*"):
            test_driver.ad5259._V_A = 1
            test_driver.ad5259._V_B = 1
            test_driver.ad5259._R_AB = 50000
            test_driver.ad5259.set_wiper_voltage(2)

    def test_set_wiper_proportion(self, test_driver):
        # Test that asking for a proportion of 0.5 with unsupplied voltages results in a correct count
        test_driver.ad5259._V_A = None
        test_driver.ad5259._V_A = None
        test_driver.ad5259._R_AB = None

        test_driver.ad5259.set_wiper_proportion(0.5)
        assert(test_driver.ad5259.get_wiper_count() == 127)
        test_driver.ad5259.set_wiper_proportion(0.25)
        assert(test_driver.ad5259.get_wiper_count() == 63)
        test_driver.ad5259.set_wiper_proportion(0)
        assert(test_driver.ad5259.get_wiper_count() == 0)
        test_driver.ad5259.set_wiper_proportion(1)
        assert(test_driver.ad5259.get_wiper_count() == 255)

        # Test that invalid values trigger errors
        with pytest.raises(Exception, match=".*Invalid.*"):
            test_driver.ad5259.set_wiper_proportion(-0.1)
        with pytest.raises(Exception, match=".*Invalid.*"):
            test_driver.ad5259.set_wiper_proportion(1.2)

