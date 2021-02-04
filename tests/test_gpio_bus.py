
import sys
import pytest

if sys.version_info[0] == 3:    # pragma: no cover
    from unittest.mock import Mock, mock_open, MagicMock, patch
else:                           # pragma: no cover
    from mock import Mock, mock_open, MagicMock, patch

# Create mocks
sys.modules['gpiod'] = Mock()
sys.modules['logging'] = Mock() # Track calls to logger.warning

##from odin_devices.gpio_bus import GPIO_Bus, GPIO_ZynqMP, logger, GPIOException, _ASYNC_AVAIL

class gpio_bus_test_fixture(object):

    def __init__(self):
        # Instantiate a basic 10-line bus with GPIO chip '1' and offset '20'
        #self.gpio_bus_basic = GPIO_Bus(10, 1, 20);  # Instantiate a basic GPIO BUS
        pass

@pytest.fixture(scope="class")
def test_gpio_bus():
    test_driver_fixture = gpio_bus_test_fixture()
    yield test_driver_fixture

def raise_OSError():
    raise OSError

class TestGPIOBus():

    def test_imports_noconcurrent(self, test_gpio_bus):
        # remove concurrent reference so that on import it will fail
        import concurrent
        oldconcurrent = sys.modules['concurrent']
        sys.modules['concurrent'] = None

        # import with concurrent removed
        from odin_devices.gpio_bus import GPIO_Bus, GPIOException

        # Init a test bus
        test_gpio_bus.gpio_bus_temp = GPIO_Bus(5, 1, 20)    # Test same request as before
        test_gpio_bus.gpio_bus_temp._master_linebulk = MagicMock()  # Make sure these calls do nothing
        test_gpio_bus.gpio_bus_temp._check_pin_avail = MagicMock()  # Make sure tests don't to verify pins

        # Attempt the use of a synchronous event call (gpiod mocked), should not throw error
        test_gpio_bus.gpio_bus_temp.register_pin_event(1, GPIO_Bus.EV_REQ_RISING)

        # Attempt the use of an asynchronous event call, expecting an error thrown
        with pytest.raises(GPIOException, match=".*Asynchronous operations not available.*"):
            try:
                test_gpio_bus.gpio_bus_temp.register_pin_event_callback(2, GPIO_Bus.EV_REQ_RISING, None)
            except ModuleNotFoundError:
                pass    # Stop trigger error causing failure if it is not handled

        # Free any claimed pins
        test_gpio_bus.gpio_bus_temp.release_all_consumed()

        # Restore concurrent
        sys.modules['cocurrent'] = oldconcurrent

    def test_instantiation_chip(self, test_gpio_bus):
        from odin_devices.gpio_bus import GPIO_Bus, GPIOException

        # Create temporary test bus
        test_gpio_bus.gpio_bus_temp = GPIO_Bus(5, 1, 20)

        # Test initial chipname chosen is correct for basic GPIO instance
        #test_gpio_bus.gpio_bus_temp.gpiod.Chip = MagicMock(return=
        sys.modules['gpiod'].Chip.assert_called_with("/dev/gpiochip1")

        # Test the correct line numbers are requested with offset
        assert (list(test_gpio_bus.gpio_bus_temp._gpio_chip.get_lines.call_args[0][0]) == [20,21,22,23,24])

        # Test offset correctly stored
        assert test_gpio_bus.gpio_bus_temp._width == 5

    def test_invalid_gpio_chip(self, test_gpio_bus):
        from odin_devices.gpio_bus import GPIO_Bus, GPIOException
        # Test the driver's reaction to an FileNotFoundError thrown on call to gpiod.Chip()

        # Set the side-effect of calling gpiod.Chip() as FileNotFoundError
        sys.modules['gpiod'].Chip.side_effect = FileNotFoundError

        # Check that the FileNotFoundError triggers a GPIOError which warns about gpiochip
        with pytest.raises(GPIOException, match=".*gpiochip.*"):
            try:
                test.gpio_bus.gpio_bus_temp = GPIO_Bus(5, 1, 20)    # Test same request as before
            except FileNotFoundError:
                pass    # Stop trigger error causing failure if it is not handled

        # Remove the error side-effect
        sys.modules['gpiod'].Chip.side_effect = None

    def test_invalid_line_range(self, test_gpio_bus):
        from odin_devices.gpio_bus import GPIO_Bus, GPIOException
        # Test instantiation with invalid linebulk ranges (pins not available on the gpiochip)
        # In this case, gpiod throws an OSError

        # Set the side-effect of calling get_lines as OSError
        #sys.modules['gpiod'].Chip.get_lines.side_effect = OSError

        # Create a new chip instance to use
        chipmock = sys.modules['gpiod'].Chip(None)
        chipmock.get_lines.side_effect = FileNotFoundError # Calling get_lines on this chip will fail
        sys.modules['gpiod'].Chip.side_effect = chipmock    # Return our mock chip

        # Check that OSError on call to get_lines will cause an error description for range
        with pytest.raises(GPIOException, match=".*out of range.*"):
            try:
                test_gpio_bus.gpio_bus_temp = GPIO_Bus(5, 1, 20)    # Test same request as before
                print(test_gpio_bus.gpio_bus_temp._gpio_chip.get_lines.call_args)
                print(sys.modules['gpiod'].Chip.get_lines.call_args)
                print(chipmock.get_lines.call_args)
                print(chipmock.get_lines.mock_calls)
            except OSError:
                print("An OSError was triggered")
                pass    # Stop trigger error causing failure if it is not handled
            except exception as e:
                print("Other error: ", e)

       # Remove the error side-effect
        sys.modules['gpiod'].Chip.get_lines.side_effect = None

    def test_consumer_naming(self, test_gpio_bus):
        from odin_devices.gpio_bus import GPIO_Bus, GPIOException
        # Test that when the consumer name is changed, the correct name is used to claim lines
        # inside the calls to gpiod.

        # Init a test bus of width 5
        test_gpio_bus.gpio_bus_temp = GPIO_Bus(5, 0, 0)

        # Mock the linebulk so that it returns a free Line object mock
        mockline = sys.modules['gpiod'].Line()
        mockline.is_requested.return_value = False
        mockline.is_used.return_value = False
        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list.return_value = [mockline]

        # Set a non-default consumer name
        default_consumer_name = test_gpio_bus.gpio_bus_temp.get_consumer_name()
        test_gpio_bus.gpio_bus_temp.set_consumer_name("nonstandard_consumername")

        # Check sure we have actually set using a new name
        assert test_gpio_bus.gpio_bus_temp.get_consumer_name() != default_consumer_name

        # Check sure the new consumer name is sent to gpiod
        test_gpio_bus.gpio_bus_temp.get_pin(0, GPIO_Bus.DIR_INPUT, False, False)
        mockline.request.assert_called_with(consumer="nonstandard_consumername",
                type=GPIO_Bus.DIR_INPUT,
                default_val=0,flags=0)

    def test_width_setting(self, test_gpio_bus):
        from odin_devices.gpio_bus import GPIO_Bus, GPIOException
        # Test that the width changes correctly, and properly frees any lines that would become
        # unusable in the event of a reduced width. Also checks invalid widths.

        # Init a test bus of width 5 with no offset
        test_gpio_bus.gpio_bus_temp = GPIO_Bus(5, 0, 0)

        # Check the width has been correctly set as 5
        assert test_gpio_bus.gpio_bus_temp._width == 5

        # Set gpiod get_lines to return a list of 10 lines (for checking this becomes the linebulk)
        mocklines = [sys.modules['gpiod'].Line()] * 10
        test_gpio_bus.gpio_bus_temp._gpio_chip.get_lines.return_value = mocklines

        # Increase width to 10
        test_gpio_bus.gpio_bus_temp.set_width(10)

        # Check that gpiod get_lines called with correct range, width is 10 and assignment is made
        test_gpio_bus.gpio_bus_temp._gpio_chip.get_lines.assert_called_with(range(0, 10))
        assert test_gpio_bus.gpio_bus_temp._width == 10
        assert test_gpio_bus.gpio_bus_temp._master_linebulk == mocklines

        # Check that creating a bus with a range less than 1 results in error
        with pytest.raises(GPIOException, match=".*Width supplied is invalid.*"):
            GPIO_Bus(0, 0, 0)
        with pytest.raises(GPIOException, match=".*Width supplied is invalid.*"):
            GPIO_Bus(-1, 0, 0)
