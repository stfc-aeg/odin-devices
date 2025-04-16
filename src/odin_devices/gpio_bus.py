"""Wrapper to abstract hardware-specific details and present a simple GPIO bus of gpiod lines

This class enables the definitions of GPIO buses based the libgpiod python bindings. Lines use
simple indexes with an internal offset (Examples for Zynq and ZynqMP included at EOF).

Lines (pins) returned are gpiod pin instances as created by libgpiod. Therefore refer to the
documentation for the python bindings originally hosted at https://github.com/brgl/libgpiod, now
at https://git.kernel.org/pub/scm/libs/libgpiod/libgpiod.git/

General libgpiod pin functions (applicable to objects returned by get_pin()):
    - get_value()           Returns high or low value read from the pin in INPUT mode
    - set_value()           Sets the pin high or low in OUTPUT mode

General libgpiod linebulk functions (applicable to objects returned from get_bulk_pins():
    - get_values()          Returns array of high or low values read from pins in INPUT mode.
    - set_values()          Sets the pins high or low in OUTPUT mode using an array of values

Additional functions simplifying the registering of events and waiting have been added, including
asynchronous versions that will call a supplied callback when the event occurs.

Joseph Nobes, Grad Embedded Sys Eng, STFC Detector Systems Software Group
"""

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
except ModuleNotFoundError:
    raise GPIOException(
            "gpiod module not found. "
            "This module requires libgpiod to be compiled with python bindings enabled. "
            "See https://git.kernel.org/pub/scm/libs/libgpiod/libgpiod.git/about/")

# If concurrence is not available, module should still be able to be used without events.
_ASYNC_AVAIL = True
if sys.version_info[0] == 3:        # pragma: no cover
    try:
        import concurrent.futures as futures
    except ModuleNotFoundError:
        _ASYNC_AVAIL = False
        logger.warning(
                "concurrent.futures module not available, asynchronous events not supported")
else:                               # pragma: no cover
    FileNotFoundError = OSError     # FileNotFoundError is not defined in Python 2
    try:
        import concurrent.futures as futures
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
    """
    A class to represent a set of consecutive GPIO lines by keeping the offset of those lines
    abstract from the user. Instances should be defined for different devices by specifying the
    relevant chip number from /dev/gpiochip and the offset of the bus pins in use.
    """

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
        """
        Create a new bus instance for a set of gpiod pins on a specified bus at a specified offset.

        :param width:           The number of concurrent pins to be referenced by this bus
        :param chipno:          The number of the relevant gpio chip in /dev/gpiochip*
        :param system_offset:   The offset of this bus from GPIO 0. In the case of Xilinx Zynq this
                                is due to numbering reserved for MIO lines rather than EMIO.
        """

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
        """ Return the consumer name that will be used to consume (reserve) gpiod pins. """
        return self._consumer_name

    def set_consumer_name(self, consumer_name):
        """ Set the consumer name that will be used to consume (reserve) gpiod pins. """
        self._consumer_name = consumer_name

    def get_width(self):
        """ Return the width (number of gpiod lines) associated with this bus """
        return self._width

    def set_width(self, new_width):
        """
        Change the width (number of gpiod lines) associated with this bus. If the width is less
        than the previous width, the lines that would become inaccessible are released.

        :param new_width:   New width to be set
        """
        # Free pins that would become inaccessible
        if new_width < self._width:
            for i in range(new_width, self._width):
                self._master_linebulk.to_list()[i].release()

        self._master_linebulk = self._gpio_chip.get_lines(range(self._system_offset, self._system_offset + new_width))
        self._width = new_width

    """
    Pin Requests
    """
    def _check_pin_avail(self, index, ignore_current=False):
        """
        Check if a given pin is available to be requested for use by the user. This includes checks
        for range in the bus, whether the line has already been requested by the current user, and
        check for whether the line is in use by the kernel or a different user.

        If the pin is not available, an exception will be raised. Otherwise, no action.

        :param index:               Bus index of the line to be checked
        :param ignore_current:      Set True to return success if the pin is in use, but by the
                                    current user.
        """

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
        """
        Claims the gpiod pin from the system, if available. Return the relevant gpiod pin.

        :param index:               Bus index of the line to be retrieved
        :param direction:           IO direction of the pin. One of GPIO_Bus.DIR_INPUT/OUTPUT
        :param active_l:            (optional) If True, pin will be active low when set to 1.
                                    False by default.
        :param no_request:          (optional) If True, do not attempt to request use of the pin
                                    from the system. Might be useful to free it if the index is
                                    known. False by default.
        :return:                    Requested gpiod line.
        """

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
        """
        Similar to get_pin but returns a gpiod 'linebulk' instance that refers to several lines at
        once. These lines' values can be set and read with arrays. It is also iterable. The indexes
        included in the linebulk do not have to be concurrent, and can be in any order. Read/write
        arrays will be in this order.

        :param indexs:              Array of bus indexes of the lines to be retrieved
        :param direction:           IO direction of the pins. One of GPIO_Bus.DIR_INPUT/OUTPUT. All
                                    pins in the linebulk have the same direction.
        :param active_l:            (optional) If True, pins will be active low when set to 1.
                                    False by default.
        :param no_request:          (optional) If True, do not attempt to request use of the pins
                                    from the system. Might be useful to free them if the indexes are
                                    known. False by default.
        :return:                    gpiod linebulk instance
        """

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
        """ Release all lines currently consumed by this bus. """
        self._master_linebulk.release()

    """
    Synchronous Event Handling:
    """
    def register_pin_event(self, index, event_request_type):
        """
        Register an event on a given pin, so that it can be polled on or checked in a non-blocking
        manner.

        :param index:               Bus index of the line to register the event with
        :param event_request_type:  Type of event:
                                        - GPIO_Bus.EV_REQ_FALLING       for falling edge
                                        - GPIO_BUS.EV_REQ_RISING        for rising edge
                                        - GPIO_Bus.EV_REQ_BOTH_EDGES    for either edge
        :return:                    The line on which the event was registered.
        """

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
        """ Remove the event request from pin with given bus index """
        # Free pin
        line = self.get_pin(index, None, False, True)
        line.release()

    def wait_pin_event(self, index, timeout_s=0):
        """
        Wait on a pin event to trigger. This can be non-blocking if called without a timeout.

        :param index:               Bus index of the line to wait for an event from
        :param timeout_s:           Time to wait in seconds before returning if there was no event.
                                    If unassigned or 0, will return immediately whether event has
                                    occurred. If set to a negative value, will wait forever (ppoll).
        :return:                    Returns 0 if no event was found or if timeout was reached.
                                    Otherwise returns the type of event
        """

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
        """
        Task that will execute line event polling in the background.

        :param callback_function:       Function that will be called when an event is detected.
                                        Arguments will be event type followed by line index.
        :param index:                   Bus index of the line that is being checked
        :param line:                    The line instance that is to be checked
        """

        # ThreadPool futures can only be terminated individually by finishing work
        while not index in self._monitor_remove_pending:
            # Check non-blocking so that event monitor removal is polled
            if line.event_wait(sec=1):
                event = line.event_read()
                callback_function(event.type, index)    # Call the user's callback

    def register_pin_event_callback(self, index, event_request_type, callback_function):
        """
        Register a callback to be associated with a given event for a given pin. The same function
        can be passed for event callbacks to different lines.

        :param index:               Bus index of the line to wait for an event from
        :param event_request_type:  Type of event:
                                        - GPIO_Bus.EV_REQ_FALLING       for falling edge
                                        - GPIO_BUS.EV_REQ_RISING        for rising edge
                                        - GPIO_Bus.EV_REQ_BOTH_EDGES    for either edge
        :param callback_function:   Function to be called when/if the event occurs. This should take
                                    two arguments: event type, and line index (so that the trigger
                                    line can be identified if using the same callback function for
                                    multiple lines).
        """

        # Check event request is one of those defined at the top
        if event_request_type not in [GPIO_Bus.EV_REQ_RISING,
                GPIO_Bus.EV_REQ_FALLING,
                GPIO_Bus.EV_REQ_BOTH_EDGES]:
            raise GPIOException(
                    "Invalid event type, choose from: "
                    "GPIO_Bus.EV_REQ_RISING, GPIO_Bus.EV_REQ_FALLING, "
                    "GPIO_Bus.EV_REQ_BOTH_EDGES")

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
        """ Remove callback event for a given pin bus index. """
        # Remove callback async function
        self._monitor_remove_pending.append(index)

        while not self._monitors[index].done():
            pass

        self._monitor_remove_pending.remove(index)
        self._monitors.pop(index)

        # Free pin
        self.remove_pin_event(index)

    def report_registered_events(self):
        """ List all pins currently being monitored, along with the events being waited for. """
        #TODO
        pass

"""
Example Buses:
"""
GPIO_Zynq = GPIO_Bus(12, 0, 54)         # Width will need to match EMIO GPIO width
GPIO_ZynqMP = GPIO_Bus(12, 0, 78)       # Width will need to match EMIO GPIO width

