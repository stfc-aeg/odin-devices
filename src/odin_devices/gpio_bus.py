import logging
import sys
logger = logging.getLogger('odin_devices.gpio_bus')

class GPIOException(Exception):
    pass

"""
Check dependencies and environment:
"""

try:
    import gpiod
except ModuleNotFoundException:
    raise GPIOException(
            "gpiod module not found. "
            "This module requires libgpiod to be compiled with python bindings enabled. "
            "See https://git.kernel.org/pub/scm/libs/libgpiod/libgpiod.git/about/")

# If concurrence is not available, module should still be able to be used without events.
_ASYNC_AVAIL = True
if sys.version_info[0] == 3:
    try:
        import concurrent.futures as futures
    except ModuleNotFoundError:
        _ASYNC_AVAIL = False
        logger.warning(
                "concurrent.futures module not available, asynchronous events not supported")
else:
    try:
        import futures
    except ImportError:
        _ASYNC_AVAIL = False
        logger.warning(
                "concurrent.futures module not available, asynchronous events not supported")

# This module requires a new enough version of libgpiod that the line.update() function exists
try:
    gpiod.Line.update
except AttributeError:
    raise GPIOException(
            "This module requries a version of libgpiod that includes gpiod.Line.update()")

"""
GPIO Bus Class:
"""

class GPIO_Bus():
    DIR_INPUT = gpiod.LINE_REQ_DIR_IN
    DIR_OUTPUT = gpiod.LINE_REQ_DIR_OUT

    # Event types, used when the events are reported. NOT for requests
    EVENT_RISING = gpiod.LineEvent.RISING_EDGE
    EVENT_FALLING = gpiod.LineEvent.FALLING_EDGE

    # Event request types, used when creating listeners
    EV_REQ_RISING = gpiod.LINE_REQ_EV_RISING_EDGE
    EV_REQ_FALLING = gpiod.LINE_REQ_EV_FALLING_EDGE
    EV_REQ_BOTH_EDGES = gpiod.LINE_REQ_EV_BOTH_EDGES

    def __init__(self, width, chipno=0, system_offset=0):
        # Check width is valid
        if not width > 0:
            raise GPIOException(
                    "Width supplied is invalid. Please specify a bus width above 0")

        # Select the specified GPIO chip
        try:
            self._gpio_chip = gpiod.Chip("/dev/gpiochip" +str(chipno))
        except FileNotFoundError:
            raise GPIOException(
                    "gpiochip not found, check /dev/gpiochip* for chip numbers present")

        # Place the chosen lines into a bulk for offset removal. Not requested until use.
        self._system_offset = system_offset
        self._width = width
        try:
            self._master_linebulk = self._gpio_chip.get_lines(range(system_offset, system_offset+width))
        except OSError:
            raise GPIOException(
                    "Selected lines were not available for this chip. "
                    "Check if numbering is out of range")

        # Set the consumer name
        self._consumer_name = "odin_gpio_bus"

        # Set up for concurrency if available
        self._executor = None       # Will manage futures for events being awaited
        self._monitors = {}          # Will hold references to futures and related lines
        self._monitor_remove_pending = []   # List of pin indexes that should stop monitoring

    """
    Bus and Consumer Management
    """
    def get_consumer_name(self):
        return self._consumer_name

    def set_consumer_name(self, consumer_name):
        self._consumer_name = consumer_name

    def get_width(self):
        return self._width

    def set_width(self, new_width):
        # Create a new linebulk, since this does not imply ownership.

        # Free pins that would become inaccessible
        if new_width < self._width:
            for i in range(new_width, width):
                self._master_linebulk.to_list()[i].release()

        self._master_linebulk = self._gpio_chip.get_lines(range(self._system_offset, self._system_offset + new_width))
        self._width = new_width

    """
    Pin Requests
    """
    def _check_pin_avail(self, index, ignore_current=False):
        # Check if the pin is in range
        if index >= self._width:
            raise GPIOException ("GPIO Pin index out of range, bus width: {}".format(self._width))
        elif index < 0:
            raise GPIOException ("Gpio Pin index cannot be negative")

        self._master_linebulk.to_list()[index].update()     # Sync line info with kernel

        if not ignore_current:
            # Check pin is not already requested for other operations by this user
            if self._master_linebulk.to_list()[index].is_requested():
                raise GPIOException ("User has already requested ownership of this line")

        # Check pin is not already in use by the kernel or another user
        if self._master_linebulk.to_list()[index].is_used():
            raise GPIOException ("This line is already in use by another user or the kernel")

    def get_pin(self, index, direction, active_l=False, no_request=False):

        # check pin is valid and available.
        # If being called with no_request=True, the pin is being returned without request, so
        # whether the current program has requested it or not is irrelevant.
        self._check_pin_avail(index, ignore_current=no_request)

        # Create GPIO_Pin wrapper around master linebulk pin
        line = self._master_linebulk.to_list()[index]
        if no_request == False and line.is_requested() == False:
            if active_l:
                flags = gpiod.LINE_REQ_FLAG_ACTIVE_LOW
            else:
                flags = 0
            line.request(consumer=self._consumer_name,
                         type = direction,
                         flags = flags,
                         default_val = 0)

        return line

    def get_bulk_pins(self, indexes, direction, active_l=False, no_request=False):

        # Check pins are valid and available
        # If being called with no_request=True, the pins are being returned without request, so
        # whether the current program has requested any of the pins or not is irrelevant
        for index in indexes:
            self._check_pin_avail(index, ignore_current=no_request)

        # Create GPIO_Bulk_Pins wrapper around master linebulk pin
        lines = self._master_linebulk.get_lines(indexes)
        any_lines_requested = [x.is_requested() for x in lines.to_list()]
        if no_request == False and any_lines_requested == False:
            if active_l:
                flags = gpiod.LINE_REQ_FLAG_ACTIVE_LOW
            else:
                flags = 0
            lines.request(consumer=self._consumer_name,
                         type = direction,
                         flags = active,
                         default_val = 0)

        return lines

    def release_all_consumed(self):
        self._master_linebulk.release()

    """
    Synchronous Event Handling:
    """
    def register_pin_event(self, index, event_request_type):
        # Check event request is one of those defined at the top
        if event_request_type not in [GPIO_Bus.EV_REQ_RISING,
                GPIO_Bus.EV_REQ_FALLING,
                GPIO_Bus.EV_REQ_BOTH_EDGES]:
            raise GPIOException(
                    "Invalid event type, choose from: "
                    "GPIO_Bus.EV_REQ_RISING, GPIO_Bus.EV_REQ_FALLING, "
                    "GPIO_Bus.EV_REQ_BOTH_EDGES")

        # check pin is valid and available
        self._check_pin_avail(index)

        # Create event request
        line = self._master_linebulk.to_list()[index]
        line.request(consumer=self._consumer_name,
                     type=event_request_type)

        return line

    def remove_pin_event(self, index):
        # Free pin
        line = self.get_pin(index, None, False, True)
        line.release()

    def wait_pin_event(self, index, timeout_s=0):
        # Directly wraps the gpiod call with a check. Blocking if no timeout is supplied.
        # event description if event occured, False if timeout

        # Check this pin has been registered for an event
        line = self.get_pin(index, None, False, True)
        line.update()
        if not line.is_requested():
            raise GPIOException(
                    "This line is not registered to wait for events. "
                    "Try calling register_pin_event() first")

        event_found = line.event_wait(sec=timeout_s)

        if event_found:
            return line.event_read()
        else:
            return False

    """
    Asynchronous Event Callbacks:
    """
    def _event_monitor_task(self, callback_function, index, line):
        # ThreadPool futures can only be terminated individually by finishing work
        while not index in self._monitor_remove_pending:
            # Check non-blocking so that event monitor removal is polled
            if line.event_wait(sec=1):
                event = line.event_read()
                callback_function(event.type, index)    # Call the user's callback

    def register_pin_event_callback(self, index, event_request_type, callback_function):
        # Callback has 2 arguments, event and index. Event is one of those defined at the top
        # Event request is one of those defined at the top

        # Check module has been imported to allow asynchronous code
        if not _ASYNC_AVAIL:
            raise GPIOException ("Asynchronous operations not available, no concurrent.futures module")

        # Create and make event request
        line = self.register_pin_event(index, event_request_type)

        # Register callback
        if self._executor == None:
            self._executor = futures.ThreadPoolExecutor(max_workers=None)
        self._monitors[index] = (self._executor.submit(self._event_monitor_task, callback_function, index, line))

    def remove_pin_event_callback(self, index):
        # Remove callback async function
        self._monitor_remove_pending.append(index)

        while not self._monitors[index].done():
            pass

        self._monitor_remove_pending.remove(index)
        self._monitors.pop(index)

        # Free pin
        self.remove_pin_event(index)

    def report_registered_events(self):
        #TODO list all pins in the monitor list
        pass

"""
Example Buses:
"""
GPIO_Zynq = GPIO_Bus(12, 0, 54)         # Width will need to match EMIO GPIO width
GPIO_ZynqMP = GPIO_Bus(12, 0, 78)       # Width will need to match EMIO GPIO width

