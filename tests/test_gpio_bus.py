
import sys
import pytest

if sys.version_info[0] == 3:    # pragma: no cover
    from unittest.mock import Mock, mock_open, MagicMock, patch
    from importlib import reload
else:                           # pragma: no cover
    from mock import Mock, mock_open, MagicMock, patch
    ModuleNotFoundError = ImportError

# Create mocks
sys.modules['gpiod'] = Mock()
sys.modules['logging'] = Mock() # Track calls to logger.warning

#import odin_devices.gpio_bus        # Needs direct import so module can be reloaded live
from odin_devices.gpio_bus import GPIO_Bus, GPIO_ZynqMP, logger, GPIOException, _ASYNC_AVAIL

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
        if sys.version_info[0] == 3:    #pragma: no cover
            import concurrent
            oldconcurrent = sys.modules['concurrent']
            sys.modules['concurrent'] = None
        else:                           #pragma: no cover
            import futures
            oldfutures = sys.modules['futures']
            sys.modules['futures'] = None

        # import with concurrent removed
        import odin_devices.gpio_bus
        reload(odin_devices.gpio_bus)
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
        if sys.version_info[0] == 3:    #pragma: no cover
            sys.modules['concurrent'] = oldconcurrent
        else:                           #pragma: no cover
            sys.modules['futures'] = oldfutures
        import odin_devices.gpio_bus
        reload(odin_devices.gpio_bus)
        from odin_devices.gpio_bus import GPIO_Bus, GPIOException

        # Check async was restored (stops later async test failing)
        from odin_devices.gpio_bus import _ASYNC_AVAIL
        assert(_ASYNC_AVAIL)

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

        # Use patch to patch Chip class' instance
        with patch('gpiod.Chip') as MockChip:
            # Make sure 'valid' chip instance will fail on call of get_lines
            instance = MockChip.return_value
            instance.get_lines.side_effect = OSError

            with pytest.raises(GPIOException, match=".*out of range.*"):
                try:
                    test_g = GPIO_Bus(5, 1, 20)
                except OSError:
                    print("An OSError was triggered. Should have been caught by gpio_bus")
                    pass

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

    def test_check_pin_avail(self, test_gpio_bus):
        from odin_devices.gpio_bus import GPIO_Bus, GPIOException
        # Test that expected errors for pin availability trigger exceptions, and that the flag
        # ignore_concurrent works properly.

        # Init a test bus of width 1 with no offset
        test_gpio_bus.gpio_bus_temp = GPIO_Bus(1, 0, 0)

        # Create a mock line and the master linebulk
        mockline = sys.modules['gpiod'].Line()
        test_gpio_bus.gpio_bus_temp._master_linebulk = sys.modules['gpiod'].LineBulk()
        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list.return_value = [mockline]

        # Check a pin with range beyond or before the master linebulk is rejected
        with pytest.raises(GPIOException, match=".*out of range, bus width: 1.*"):
            test_gpio_bus.gpio_bus_temp._check_pin_avail(6)
        with pytest.raises(GPIOException, match=".*index cannot be negative.*"):
            test_gpio_bus.gpio_bus_temp._check_pin_avail(-1)

        # Check a pin that returns is_used() will be rejected
        mockline.is_used.return_value = True
        mockline.is_requested.return_value = False
        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list.return_value = [mockline]
        with pytest.raises(GPIOException, match=".*in use by another user.*"):
            test_gpio_bus.gpio_bus_temp._check_pin_avail(0)

        # Check a pin that returns is_requested will be rejected, but only if not passed the
        # ignore_current argument.
        mockline.is_used.return_value = False
        mockline.is_requested.return_value = True
        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list.return_value = [mockline]
        with pytest.raises(GPIOException, match=".*already requested ownership.*"):
            test_gpio_bus.gpio_bus_temp._check_pin_avail(0)
        test_gpio_bus.gpio_bus_temp._check_pin_avail(0, ignore_current=True) # Should not throw


    def test_get_pin(self, test_gpio_bus):
        from odin_devices.gpio_bus import GPIO_Bus, GPIOException
        sys.modules['gpiod'].reset_mock()       # Reset call lists for Line() and Linebulk()
        # Test that get_pin calls the expected checks and forwards correct values to to gpiod
        # when making the line request.

        # Create a new GPIO bus and a mocked line
        test_gpio_bus.gpio_bus_temp = GPIO_Bus(1, 0, 0)
        test_gpio_bus.gpio_bus_temp._master_linebulk = sys.modules['gpiod'].LineBulk()
        mockline = sys.modules['gpiod'].Line()

        # Change the consumer name for later checks
        test_gpio_bus.gpio_bus_temp.set_consumer_name("test_get_pin")

        # Check that _check_pin_avail is called and will trigger an exception (see full test above)
        with pytest.raises(GPIOException, match=".*out of range, bus width: 1.*"):
            test_gpio_bus.gpio_bus_temp.get_pin(2, GPIO_Bus.DIR_OUTPUT)

        # Check that calling on an already requested pin with no_request supplies the line without
        # calling the gpiod line request
        mockline.is_requested.return_value = True
        mockline.is_used.return_value = False
        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list.return_value = [mockline]
        pinout = test_gpio_bus.gpio_bus_temp.get_pin(0, GPIO_Bus.DIR_OUTPUT, no_request=True)
        assert(pinout == mockline)                      # Check line is returned correctly
        print(test_gpio_bus.gpio_bus_temp._master_linebulk.to_list()[0].request.mock_calls)
        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list()[0].request.assert_not_called()

        # Check that calling with no_request on a line ID that does not exist still causes an error
        with pytest.raises(GPIOException, match=".*out of range.*"):
            pinout = test_gpio_bus.gpio_bus_temp.get_pin(2, GPIO_Bus.DIR_OUTPUT, no_request=True)

        # Check that a line request with different active_l and direction translate to correct
        # values being propagated to gpiod, and that the consumer name is correct.
        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list()[0].is_requested.return_value = False
        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list()[0].is_used.return_value = False

        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list()[0].reset_mock() # Reset line calls
        test_gpio_bus.gpio_bus_temp.get_pin(0, GPIO_Bus.DIR_OUTPUT, active_l = False)
        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list()[0].request.assert_called_with(
                consumer="test_get_pin",
                type=sys.modules['gpiod'].LINE_REQ_DIR_OUT,
                flags=0,                        # NOTE: assumes no flags other than active low
                default_val=0)

        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list()[0].reset_mock() # Reset line calls
        test_gpio_bus.gpio_bus_temp.get_pin(0, GPIO_Bus.DIR_OUTPUT, active_l = True)
        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list()[0].request.assert_called_with(
                consumer="test_get_pin",
                type=sys.modules['gpiod'].LINE_REQ_DIR_OUT,
                flags=sys.modules['gpiod'].LINE_REQ_FLAG_ACTIVE_LOW,
                default_val=0)

        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list()[0].reset_mock() # Reset line calls
        test_gpio_bus.gpio_bus_temp.get_pin(0, GPIO_Bus.DIR_INPUT, active_l = False)
        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list()[0].request.assert_called_with(
                consumer="test_get_pin",
                type=sys.modules['gpiod'].LINE_REQ_DIR_IN,
                flags=0,                        # NOTE: assumes no flags other than active low
                default_val=0)

    def test_get_bulk_pins(self, test_gpio_bus):
        from odin_devices.gpio_bus import GPIO_Bus, GPIOException
        sys.modules['gpiod'].reset_mock()       # Reset call lists for Line() and Linebulk()
        # This method will be using the same logic as the get_pin(), one so these tests will focus
        # on differences between the two.

        # Create a test mock linebulk with all pre-requested lines
        mockline = sys.modules['gpiod'].Line()
        mockline.is_requested.return_value = True
        mockline.is_used.return_value = False
        mocklines = [mockline, mockline, mockline]
        mocklinebulk = sys.modules['gpiod'].LineBulk()
        mocklinebulk.to_list.return_values = mocklines
        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list.return_value = mocklines
        test_gpio_bus.gpio_bus_temp._master_linebulk.get_lines.return_value = mocklinebulk

        # Create a new GPIO bus with the new mocklines
        test_gpio_bus.gpio_bus_temp = GPIO_Bus(3, 0, 0)
        test_gpio_bus.gpio_bus_temp._master_linebulk = sys.modules['gpiod'].LineBulk()

        # Check that if one of the lines is requested, an exception will be raised
        with pytest.raises(GPIOException, match=""):
            test_gpio_bus.gpio_bus_temp.get_bulk_pins([0,1,2], GPIO_Bus.DIR_OUTPUT)

    def test_synchronous_events(self, test_gpio_bus):
        from odin_devices.gpio_bus import GPIO_Bus, GPIOException
        sys.modules['gpiod'].reset_mock()       # Reset the call lists for Line() and LineBulk()

        # Create a single line bus for testing (unused and unrequested)
        test_gpio_bus.gpio_bus_temp = GPIO_Bus(1, 0, 0)
        test_gpio_bus.gpio_bus_temp.set_consumer_name("test_sync_events")
        mockline = sys.modules['gpiod'].Line()
        mockline.is_requested.return_value = False
        mockline.is_used.return_value = False
        test_gpio_bus.gpio_bus_temp._master_linebulk = sys.modules['gpiod'].LineBulk()
        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list.return_value = [mockline]

        # Check event requests send expected request to gpiod
        test_gpio_bus.gpio_bus_temp.register_pin_event(0, GPIO_Bus.EV_REQ_FALLING)
        sys.modules['gpiod'].Line.request.called_with(
                consumer="test_sync_events",
                type=sys.modules['gpiod'].LINE_REQ_EV_FALLING_EDGE)

        # Check that only valid events are accepted
        with pytest.raises(GPIOException, match=".*Invalid event type.*"):
            test_gpio_bus.gpio_bus_temp.register_pin_event(0, 1010)

        # Check that the wait pin event with a timeout and returns False with no event found
        mockline.is_requested.return_value = True       # Make sure line is not rejected
        mockline.event_wait.return_value = False        # Return timeout respose
        assert(test_gpio_bus.gpio_bus_temp.wait_pin_event(0, 10) == False)  # Timeout is instant

        # Check that the wait pin event exits on manual event trigger and reports correct event
        mockline.is_requested.return_value = True
        mockline.event_wait.return_value = True
        mockline.event_read.return_value = sys.modules['gpiod'].LineEvent.RISING_EDGE
        assert(test_gpio_bus.gpio_bus_temp.wait_pin_event(0, 10) == GPIO_Bus.EVENT_RISING)

        # Check that user is prevented from waiting on a non-requested line
        mockline.is_requested.return_value = False
        with pytest.raises(GPIOException):
            test_gpio_bus.gpio_bus_temp.wait_pin_event(0, 10)


    def test_asynchronous_events(self, test_gpio_bus):
        from odin_devices.gpio_bus import GPIO_Bus, GPIOException, _ASYNC_AVAIL
        sys.modules['gpiod'].reset_mock()       # Reset the call lists for Line() and LineBulk()

        # Create a single line bus for testing (unused and unrequested)
        test_gpio_bus.gpio_bus_temp = GPIO_Bus(2, 0, 0)
        test_gpio_bus.gpio_bus_temp.set_consumer_name("test_sync_events")
        #mockline = sys.modules['gpiod'].Line()
        mockline1 = Mock()
        mockline2 = Mock()
        mockline1.is_requested.return_value = False
        mockline1.is_used.return_value = False
        mockline2.is_requested.return_value = False
        mockline2.is_used.return_value = False
        test_gpio_bus.gpio_bus_temp._master_linebulk = sys.modules['gpiod'].LineBulk()
        test_gpio_bus.gpio_bus_temp._master_linebulk.to_list.return_value = [mockline1, mockline2]

        # Check that only valid events are accepted
        with pytest.raises(GPIOException, match=".*Invalid event type.*"):
            test_gpio_bus.gpio_bus_temp.register_pin_event_callback(0, 1010, int)

        # Check that two separate callbacks can be created and triggered independently
        callback_function_1 = Mock()    # Create mocked callback functions
        callback_function_2 = Mock()
        mockline1.event_read.return_value = GPIO_Bus.EVENT_FALLING      # Set event type
        mockline2.event_read.return_value = GPIO_Bus.EVENT_RISING       # Set event type
        mockline1.event_wait.return_value = False       # Set events to keep waiting for now
        mockline2.event_wait.return_value = False
        test_gpio_bus.gpio_bus_temp.register_pin_event_callback(0,  # Start monitor thread pin0
                GPIO_Bus.EV_REQ_FALLING, callback_function_1)
        test_gpio_bus.gpio_bus_temp.register_pin_event_callback(1,  # Start monitor thread pin1
                GPIO_Bus.EV_REQ_RISING, callback_function_2)
        callback_function_1.assert_not_called()         # Make sure callback not called yet
        callback_function_2.assert_not_called()         # Make sure callback not called yet
        mockline1.event_wait.return_value = True        # TRIGGER pin1 event
        mockline2.event_wait.return_value = True        # TRIGGER pin2 event
        print(callback_function_2)
        test_gpio_bus.gpio_bus_temp.remove_pin_event_callback(0)
        test_gpio_bus.gpio_bus_temp.remove_pin_event_callback(1)

        callback_function_1.assert_called()        # Make sure callback called after event
        callback_function_2.assert_called()        # Make sure callback called after event
        # Note: number of calls not checked, because real gpiod would only return true once

        # Note: checking events do not trigger on the incorrect event_read() return value is not
        #       necessary, as gpiod will not return true to event_wait() if event is wrong type.

        # Check that monitors can be terminated before an event
        mockline1.event_wait.return_value = False                   # Set event to wait for now
        callback_function_1.reset_mock()                            # Reset callback count
        test_gpio_bus.gpio_bus_temp.register_pin_event_callback(0,  # Monitor for falling event
                GPIO_Bus.EV_REQ_FALLING, callback_function_1)
        # (No event triggered)
        test_gpio_bus.gpio_bus_temp.remove_pin_event_callback(0)    # Remove callback
        callback_function_1.assert_not_called()                     # Check event not called
        mockline1.event_wait.return_value = True                    # Trigger falling event
        callback_function_1.assert_not_called()                     # Check event not called

