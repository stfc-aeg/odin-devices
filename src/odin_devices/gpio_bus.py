import gpiod

# TODO can I use with to protect the resources being lost? Pins MUST be released

class GPIO_Bus():
    DIR_INPUT = gpiod.LINE_REQ_DIR_IN
    DIR_OUTPUT = gpiod.LINE_REQ_DIR_OUT

    ACTIVE_L = gpiod.Line.ACTIVE_LOW
    ACTIVE_H = gpiod.Line.ACTIVE_HIGH

    def __init__(self, width, chipno=0, system_offset=0):
        # Select the specified GPIO chip
        self._gpio_chip = gpiod.Chip("/dev/gpiochip" +str(chipno))

        # Place the chosen lines into a bulk for offset removal. Not requested until use.
        self._system_offset = system_offset
        self._width = width
        self._master_linebulk = self._gpio_chip.get_lines(range(system_offset, system_offset+width))

        # Set the consumer name
        self._consumer_name = "odin_gpio_bus"

    def get_consumer_name(self):
        return self._consumer_name

    def set_consumer_name(self, consumer_name):
        self._consumer_name = consumer_name

    def get_width(self):
        return self._width

    def set_width(self, new_width):
        # Create a new linebulk, since this does not imply ownership.

        # Free pins that would become inaccessible
        if new_width < width:
            for i in range(new_width, width):
                self._master_linebulk.to_list()[i].release()

        self._gpio_chip.get_lines(range(self._system_offset, self._system_offset + new_width))

    def get_pin(self, index, direction, active_l=False, no_request=False):
        # TODO Check pin is within range, and unrequested
        # TODO if requested, but by current application, call with no_request and warn

        # Create GPIO_Pin wrapper around master linebulk pin
        line = self._master_linebulk.to_list()[index]
        if no_request == False:
            if active_l:
                flags = LINE_REQ_FLAG_ACTIVE_LOW
            else:
                flags = 0
            line.request(consumer=self._consumer_name,
                         type = direction,
                         flags = flags,
                         default_val = 0)

        return line

    def get_bulk_pins(self, indexes, direction, active_l=False, no_request=False):
        # TODO check pin indexes are all in range, and unrequested
        # TODO if requested, but by current consumer, call with no_request and warn

        # Create GPIO_Bulk_Pins wrapper around master linebulk pin
        lines = self._master_linebulk.get_lines(indexes)
        if no_request == False:
            if active_l:
                flags = LINE_REQ_FLAG_ACTIVE_LOW
            else:
                flags = 0
            lines.request(consumer=self._consumer_name,
                         type = direction,
                         flags = active,
                         default_val = 0)

        return lines

    def release_all_consumed(self):
        self._master_linebulk.release()


# Example buses
GPIO_Zynq = GPIO_Bus(12, 0, 54)         # Width will need to match EMIO GPIO width
GPIO_ZynqMP = GPIO_Bus(12, 0, 78)       # Width will need to match EMIO GPIO width

