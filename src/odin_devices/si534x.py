

from odin_devices.i2c_device import I2CDevice, I2CException
import logging
import csv

class SI534xCommsException(Exception):
    """
    An Exception triggered when there is an issue with either the SPI or I2C interfaces.
    """
    pass

class _SI534x(object):

    class _BitField(object):
        def __init__(self, page, start_register, start_bit_pos, bit_width, parent_device):
            self.page = page
            self.start_register = start_register
            self.start_bit_pos = start_bit_pos
            self.bit_width = bit_width
            self.parent_device = parent_device

        def write(self, data):
            # Check data is of correct type (single value)
            if type(data) != int:
                #TODO throw type error
                pass
            # Check data fits in desired bit width
            if data >= (0b1 << self.bit_width):
                #TODO Throw data size error
                pass

            # Send data
            self.parent_device._write_paged_register_field(data, self.page, self.start_register,
                                                           self.start_bit_pos, self.bit_width)

        def read(self):
            return self.parent_device._read_paged_register_field(self.page, self.start_register,
                                                        self.start_bit_pos, self.bit_width)

    class _Channel_BitField(_BitField):
        def __init__(self, page, first_channel_register, start_bit_pos, bit_width, parent_device,
                     channel_positions, channel_width):
            # bit_width is the width of this field, and channel_width is the width of the set of
            # channel-mapped fields.

            # Init shared fields using superclass
            super(_SI534x._Channel_BitField, self).__init__(page, first_channel_register,
                                                            start_bit_pos, bit_width, parent_device)

            # Init additional channel-specific fields
            self.channel_positions = channel_positions
            self.channel_num = len(channel_positions)
            self.channel_width = channel_width
            self.first_channel_start_register = first_channel_register  # Static start of the field
            # start_register now becomes a dynamic value, set per channel on read / writes.

        def write(self, data, channel_num):
            # Check channel number is valid
            if channel_num >= self.num_channels:
                #TODO throw channel number error
                pass

            # Temporarily offset the _BitField start register
            self.start_register = self.first_channel_start_register
            channel_offset = self.channel_width * self.channel_positions[channel_num]
            self.start_register += self.channel_width * channel_offset

            # Call normal _BitField write function
            super(_SI534x._Channel_BitField, self).write(data)

        def read(self, channel_num):
            # Check channel number is valid
            if channel_num >= self.num_channels:
                #TODO throw channel number error
                pass

            # Temporarily offset the _BitField start register
            self.start_register = self.first_channel_start_register
            channel_offset = self.channel_width * self.channel_positions[channel_num]
            self.start_register += self.channel_width * channel_offset

            # Call normal _BitField read function
            return super(_SI534x._Channel_BitField, self).read()

    class _MultiSynth_BitField(_BitField):
        def __init__(self, page, synth0_register, start_bit_pos, bit_width, parent_device,
                     num_multisynths, synth_width):
            # bit_width is the width of this field, and synth_width is the width between adjacent
            # multi-synth mapped fields.

            # Init shared fields using superclass
            super(_SI534x._MultiSynth_BitField, self).__init__(page, synth0_register, start_bit_pos,
                                                               bit_width, parent_device)

            # Init additional multisynth-specific fields
            self.num_multisyths = num_multisynths
            self.synth_width = synth_width
            self.synth0_register = synth0_register  # Static first synth register position 0 offset
            # start_register now becomes a dynamic value, set per multisynth on read/writes

        def write(self, data, synth_num): # Check synth number is valid
            if synth_num >= self.num_multisynths:
                #TODO throw error
                pass

            # Temporarily offset the _BitField start register
            self.start_register = self.synth0_register
            self.start_register += self.synth_width * synth_num

            # Call normal _BitField write function
            super(_SI534x._MultiSynth_BitField, self).write(data)

        def read(self, synth_num):
            # Check channel number is valid
            if synth_num >= self.num_multisynths:
                #TODO throw error
                pass

            # Temporarily offset the _BitField start register
            self.start_register = self.synth0_register
            self.start_register += self.synth_width * synth_num

            # Call normal _BitField read functions
            return super(_SI534x._MultiSynth_BitField, self).read()

    class _regmap_generator(object):
        # Pages in the register map that will be read
        _regmap_pages = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x08, 0x09, 0x0A, 0x0B]
        #TODO update this comment
        # Mapping of registers expected to be present when exporting a register map that could be later
    # programmed back into the device. It is easier to specify ranges and invalid registers instead
    # of listing 'allowed' registers. Each page can have multiple ranges. This is based on an
    # example exported register map CSV from ClockBuilder Pro.
    #                               {page : [range0,
    #                                        range1...]
    # Where ranges are defined as tuples of start, end and invalid values as a list:
    #                                        (start, end, [invalid value list])

# Update these registers to reflex the exported SI5345, not the SI5344 it is based on
        _regmap_pages_register_ranges = {0x00 : [(0x01, 0x1E, [0x10, 0x15, 0x1B]),
                                                 (0x2B, 0x69, [0x3E])],
                                         0x01 : [(0x02, 0x02, []),
                                                 (0x12, 0x1A, [0x16]),
                                                 (0x26, 0x42, [0x2A])],
                                         0x02 : [(0x06, 0x3E, [0x07, 0x30]),
                                                 (0X50, 0x55, []),
                                                 (0x5C, 0x61, []),
                                                 (0x6B, 0x72, []),
                                                 (0x8A, 0x99, [0x92, 0x93, 0x95, 0x98]),
                                                 (0x9D, 0x9F, []),
                                                 (0xA9, 0xAB, []),
                                                 (0xB7, 0xB7, [])],
                                         0x03 : [(0x02, 0x2D, []),
                                                 (0x38, 0x52, [0x3A]),
                                                 (0x59, 0x60, [])],
                                         0x04 : [(0x87, 0x87, [])],
                                         0x05 : [(0x08, 0x21, [0x14, 0x20]),
                                                 (0x2A, 0x3E, [0x30, 0x3A, 0x3B, 0x3C]),
                                                 (0x89, 0x8A, []),
                                                 (0x9B, 0xA6, [0x9C, 0xA3, 0xA4, 0xA5])],
                                         0x08 : [(0x02, 0x61, [])],
                                         0x09 : [(0x0E, 0x0E, []),
                                                 (0x43, 0x43, []),
                                                 (0x49, 0x4A, []),
                                                 (0x4E, 0x4F, []),
                                                 (0x5E, 0x5E, [])],
                                         0x0A : [(0x02, 0x05, []),
                                                 (0x14, 0x14, []),
                                                 (0x1A, 0x1A, []),
                                                 (0x20, 0x20, []),
                                                 (0x26, 0x26, [])],
                                         0x0B : [(0x44, 0x4A, [0x45, 0x49]),
                                                 (0x57, 0x58, [])]
                                         }

        def __init__(self):
            self.current_page_index = 0
            self.current_page = self._regmap_pages[self.current_page_index]
            self.current_range_index = 0
            minreg, maxrex, excl = self._regmap_pages_register_ranges[self.current_page][self.current_range_index]
            self.current_register = minreg
            pass

        def __iter__(self):
            return self

        def __next__(self):
            return self.next()

        def next(self):
            current_range = self._regmap_pages_register_ranges[self.current_page][self.current_range_index]
            current_min, current_max, current_excluded = current_range

            if self.current_register == current_max:    # Move to next range in page, and next page if last range
                self.current_range_index += 1
                if self.current_range_index >= len(self._regmap_pages_register_ranges[self.current_page]):
                    # Move to next page at range 0
                    self.current_page_index += 1
                    if self.current_page_index >= len(self._regmap_pages):      # Last page finished
                        raise StopIteration()
                    self.current_page = self._regmap_pages[self.current_page_index]
                    self.current_range_index = 0

                minreg, maxrex, excl = self._regmap_pages_register_ranges[self.current_page][self.current_range_index]
                self.current_register = minreg          # Get first register in range
                return self.current_page, self.current_register

            elif self.current_register in current_excluded:     # Read onwards until a non-excluded register reached
                self.current_register += 1
                return self.next()

            else:                                       # Read next value normally
                self.current_register += 1
                return self.current_page, self.current_register

    class _FaultReport(object):
        def __init__(self, lol_status, lol_flag, los_status, los_flag, los_xtal_status,
                      los_xtal_flag, oof_status_field, oof_flag_field):
            # Assign booleans
            self.lol_status = lol_status > 0
            self.lol_flag = lol_flag > 0
            self.los_xtal_status = los_xtal_status > 0
            self.los_xtal_flag = los_xtal_flag > 0

            # Assign input-bitfields
            self.los_input_status = [False, False, False, False]
            self.los_input_flag = [False, False, False, False]
            self.oof_input_status = [False, False, False, False]
            self.oof_input_flag = [False, False, False, False]
            for input_no in range(0, 4):
                self.los_input_status[input_no] = (los_status & (0b1 << input_no)) > 0
                self.los_input_flag[input_no] = (los_flag & (0b1 << input_no)) > 0
                self.oof_input_status[input_no] = (los_status & (0b1 << input_no)) > 0
                self.oof_input_flag[input_no] = (los_flag & (0b1 << input_no)) > 0

        def has_fault(self):
            if (self.lol_status or self.los_xtal_status
                or (True in self.los_input_status) or (True in self.oof_input_status)):
                return True
            else:
                return False

        def had_fault(self):
            if (self.lol_flag or self.los_flag
                or (True in self.los_input_flag) or (True in self.oof_input_flag)):
                return True
            else:
                return False

        def __repr__(self):
            outputstr = ""
            if self.has_fault():
                outputstr += "Faults Active!\nDetails:\n"
                outputstr += "\tLOL: {}\n".format(self.lol_status)
                outputstr += "\tLOS xtal: {}\n".format(self.los_xtal_status)
                outputstr += "\tLOS inputs: {}\n".format(self.los_input_status)
                outputstr += "\tOOF inputs: {}\n".format(self.oof_input_status)
            else:
                outputstr += "No currently active faults.\n"

            if self.had_fault():
                outputstr += "Faults Flagged!\nDetails:\n"
                outputstr += "\tLOL: {}\n".format(self.lol_flag)
                outputstr += "\tLOS xtal: {}\n".format(self.los_xtal_flag)
                outputstr += "\tLOS inputs: {}\n".format(self.los_input_flag)
                outputstr += "\tOOF inputs: {}\n".format(self.oof_input_flag)
            else:
                outputstr += "No currently flagged faults.\n"

            return outputstr




    # An iterable of tuples in the form (page, register) where the pages and registers are those
    # that should be read from the device when creating a settings map with export_register_map()
    # for later re-write with the import_register_map() function.
    _regmap_pages_registers_iter = _regmap_generator()

    # The register maps to be written to the device require a preamble and postamble that write
    # registers that place the device into an acceptable start state.
    #                            [(page, register, value),...]
    _regmap_preamble_sequence =  [(0x0B, 0x24, 0xC0),
                                  (0x0B, 0x25, 0x00),
                                  (0x05, 0x40, 0x01)]
    _regmap_postamble_sequence = [(0x05, 0x14, 0x01),
                                  (0x00, 0x1C, 0x01),
                                  (0x05, 0x40, 0x00),
                                  (0x0B, 0x24, 0xC3),
                                  (0x0B, 0x25, 0x02)]

    def __init__(self, channel_positions, num_multisynths, i2c_address=None, spi_device=None,
                 LOL_Line=None, INT_Line=None):

        # Allocate device properties
        self._num_multisynths = num_multisynths
        self._num_channels = len(channel_positions)
        self._LOL_Pin = LOL_Line
        self._INT_Pin = INT_Line

        #TODO Initiate chosen interface (set chosen read/write functions)
        if i2c_address is not None:
            # Init the instance's logger
            self.logger = logging.getLogger('odin_devices.si534' +
                                            str(num_multisynths) +
                                            '.i2c_' +
                                            hex(i2c_address))

            # Init I2C
            self.i2c_bus = I2CDevice(i2c_address)

            # Set the used register read/write calls to I2C variants
            self._write_register = self._write_register_i2c
            self._read_register = self._read_register_i2c
        elif spi_device is not None:
            # Init the instance's logger
            self.logger = logging.getLogger('odin_devices.si534' +
                                            str(num_multisynths) +
                                            '.spi_dev' +
                                            str(spi_device))

            #TODO init SPI

            # Set the used register read/write calls to SPI variants
            self._write_register = self._write_register_spi
            self._read_register = self._read_register_spi
        else:
            #TODO throw error
            pass

        self._reg_map_page_select = 0xFF    # Will be immediately reset on first r/w

        # Some channel fields use an ordered channel-mapping without the strange order that other
        # fields use. See the channel OE registers.
        channel_positions_condensed = [x for x in range(0, len(channel_positions))]

        #TODO define static fields
        self._output_driver_OUTALL_DISABLE_LOW = _SI534x._BitField(page=0x01,
                                                                   start_register = 0x02,
                                                                   start_bit_pos = 0, bit_width = 1,
                                                                   parent_device = self)
        self._hard_reset_bit = _SI534x._BitField(page=0x00, start_register = 0x01E,
                                                 start_bit_pos = 1, bit_width = 1,
                                                 parent_device = self)
        self._soft_reset_bit = _SI534x._BitField(page=0x00, start_register = 0x01C,
                                                 start_bit_pos = 2, bit_width = 1,
                                                 parent_device = self)
        self._output_driver_cfg_OE_ALL = _SI534x._BitField(page=0x01,
                                                           start_register = 0x02,
                                                           start_bit_pos = 0,
                                                           bit_width = 1,
                                                           parent_device = self)
        self._multisynth_frequency_step_mask = _SI534x._BitField(page=0x03,
                                                                 start_register = 0x39,
                                                                 start_bit_pos = num_multisynths-1,
                                                                 bit_width = num_multisynths,
                                                                 parent_device = self)
        self._fault_lol_status = _SI534x._BitField(page=0x00,
                                                   start_register = 0x0E,
                                                   start_bit_pos = 1, bit_width = 1,
                                                   parent_device = self)
        self._fault_lol_flag = _SI534x._BitField(page=0x00,
                                                 start_register = 0x13,
                                                 start_bit_pos = 1, bit_width = 1,
                                                 parent_device = self)
        self._fault_los_status = _SI534x._BitField(page=0x00,
                                                   start_register = 0x0D,
                                                   start_bit_pos = 3, bit_width = 4,
                                                   parent_device = self)
        self._fault_los_flag = _SI534x._BitField(page=0x00,
                                                 start_register = 0x12,
                                                 start_bit_pos = 3, bit_width = 4,
                                                 parent_device = self)
        self._fault_los_xtal_status = _SI534x._BitField(page=0x00,
                                                   start_register = 0x0C,
                                                   start_bit_pos = 1, bit_width = 1,
                                                   parent_device = self)
        self._fault_los_xtal_flag = _SI534x._BitField(page=0x00,
                                                 start_register = 0x11,
                                                 start_bit_pos = 3, bit_width = 1,
                                                 parent_device = self)
        self._fault_oof_status = _SI534x._BitField(page=0x00,
                                                   start_register = 0x0D,
                                                   start_bit_pos = 7, bit_width = 4,
                                                   parent_device = self)
        self._fault_oof_flag = _SI534x._BitField(page=0x00,
                                                 start_register = 0x12,
                                                 start_bit_pos = 7, bit_width = 4,
                                                 parent_device = self)

        #TODO define channel-mapped fields
        self._output_driver_cfg_PDN = _SI534x._Channel_BitField(page=0x01,
                                                                first_channel_register = 0x08,
                                                                start_bit_pos = 0,
                                                                bit_width = 1,
                                                                parent_device = self,
                                                                channel_positions = channel_positions,
                                                                channel_width = 0x05)
        self._output_driver_cfg_OE = _SI534x._Channel_BitField(page=0x01,
                                                               first_channel_register = 0x08,
                                                               start_bit_pos = 1,
                                                               bit_width = 1,
                                                               parent_device = self,
                                                               channel_positions = channel_positions,
                                                               channel_width = 0x05)
        self._channel_multisynth_selection = _SI534x._Channel_BitField(page=0x01,
                                                                       first_channel_register = 0x0B,
                                                                       start_bit_pos = 2, bit_width = 3,
                                                                       parent_device = self,
                                                                       channel_positions = channel_positions,
                                                                       channel_width = 0x05)
        #TODO define multisynth-mapped fields


        #TODO perform device init

    def _set_correct_register_page(self, target_page):
        # Set the correct page
        if self._reg_map_page_select != target_page:
            # Write to page register on whatever page we are currently on (irrelevant)
            print("Changing register map page to ", target_page)
            self._write_register(0x01, target_page)
            self._reg_map_page_select = target_page

    def _write_paged_register_field(self, value_out, page, start_register, start_bit, width_bits):
        # The input to this function is a value rather than an array, so that it is easier to shift.
        # Also, most fields will be identifying a single value no matter their range, and so byte
        # boundaries hold no significance.

        # Set the correct page
        self._set_correct_register_page(page)

        # Align the output with register boundaries
        additional_lower_bits = (start_bit - width_bits) + 1
        value_out = value_out << additional_lower_bits

        # Read original contents of registers as a value
        num_full_bytes = int((width_bits-1)/8) + 1
        old_full_bytes_value = self._read_paged_register_field(page, start_register, 7,
                                                               num_full_bytes*8)

        # Mask original contents value and combine with new value
        bitmask = ((0b1<<width_bits)-1)             # Create mask of correct field width
        bitmask = bitmask << additional_lower_bits  # Shift mask to correct offset
        bitmask = (~bitmask) & ((0b1<<(num_full_bytes*8))-1)    # Reverse mask, crop to byte range
        old_full_bytes_masked = old_full_bytes_value & bitmask
        value_out = value_out | old_full_bytes_masked

        # Write back with correct start bit offset (additional lower bits already present)
        for byte_index in range (0, num_full_bytes):
            byte_bit_offset = ((num_full_bytes-1) - byte_index) * 8
            byte_value = (value_out >> byte_bit_offset) & 0xFF
            self._write_register(start_register + byte_index, byte_value)

    def _read_paged_register_field(self, page, start_register, start_bit, width_bits):

        # Set the correct page
        self._set_correct_register_page(page)

        # Read whole range of bytes into single value to cover range
        full_bytes_value = 0
        num_full_bytes = int((width_bits-1) / 8) + 1

        for byte_address in range(start_register, start_register + num_full_bytes):
            full_bytes_value = full_bytes_value << 8
            next_byte_value = self._read_register(byte_address)
            #print("next byte: ", next_byte_value)

            # Remove unused start bits from first byte
            if byte_address == start_register:
                next_byte_value = next_byte_value & ((0b1<<(start_bit+1))-1)
                #print("start bits removed: ", next_byte_value)

            full_bytes_value += next_byte_value & 0xFF
            #print("full bytes now: ", full_bytes_value)

        # Remove offset from resulting value
        additional_lower_bits = (start_bit - width_bits) + 1
        full_bytes_value = full_bytes_value >> additional_lower_bits
        #print("Now removing {} additional lower bits: {}".format(additional_lower_bits, full_bytes_value))

        return full_bytes_value

    def _write_register_i2c(self, register, value):
        # Wrapper for writing a full 8-bit register over I2C, without page logic.
        # print("Writing to register ", register, " with value ", value, " using I2C")
        self.i2c_bus.write8(register, value)

    def _read_register_i2c(self, register):
        # Wrapper for reading a full 8-bit register over I2C, without page logic.
        # print("Reading from register ", register, " using I2C")
        return self.i2c_bus.readU8(register)

    def _bytes_write_spi(self, register, value):
        pass

    def _bytes_read_spi(self, register):
        pass

    #TODO add functions for desirable option changes

    def reset(self, soft=False):
        if soft:    # Reset state machines
            self._soft_reset_bit.write(1)
            self._soft_reset_bit.write(0)
        else:       # POR device. Registers set to default.
            self._hard_reset_bit.write(1)
            self._hard_reset_but.write(0)

    """
    Channel Output Enable Control:
    """
    def set_channel_output_enabled(self, channel_number, output_enable):
        if output_enable:
            # Ensure that the all-channel disable is not active
            self._output_driver_cfg_OE_ALL.write(1)

            self._output_driver_cfg_OE.write(1, channel_number)
        else:
            self._output_driver_cfg_OE.write(0, channel_number)

    def get_channel_output_enabled(self, channel_number):
        return self._output_driver_cfg_OE.read(channel_number)

    """
    Channel (MultiSynth) Frequency Stepping:
    """
    def increment_multisynth_frequency(self, multisynth_number):
        all_multisynth_mask = (0b1 << self._num_multisynths) - 1
        step_mask = all_multisynth_mask & ~(0b1 << multisynth_number)
        self._multisynth_frequency_step_mask.write(step_mask)

        self._multisynth_frequency_increment.write(1, multisynth_number)
        self._multisynth_frequency_increment.write(0, multisynth_number)

    def decrement_multisynth_frequency(self, multisynth_number):
        all_multisynth_mask = (0b1 << self._num_multisynths) - 1
        step_mask = all_multisynth_mask & ~(0b1 << multisynth_number)
        self._multisynth_frequency_step_mask.write(step_mask)

        self._multisynth_frequency_decrement.write(1, multisynth_number)
        self._multisynth_frequency_decrement.write(0, multisynth_number)

    def decrement_channel_frequency(self, channel_number, ignore_affected_channels=False):
        # Get the multisynth currently associated with the channel specified
        multisynth_number = self.get_multisynth_from_channel(channel_number)

        if not ignore_affected_channels:
            # Check if other channels will be affected by this change
            channels_on_multisynth = self.get_channels_from_multisynth(multisynth_number)

            for affected_channel in channels_on_multisynth:
                if self.get_channel_output_enabled:     # Only warn for channels that are enabled
                    self.logger.warning(
                            "This channel shares a multisynth with ch {}.".format(affected_channel)
                            + " Both channels will be stepped. To ignore this warning, supply the "
                            + "argument ignore_affected_channels=True")

        self.decrement_multisynth_frequency(multisynth_number)


    def increment_channel_frequency(self, channel_number, ignore_affected_channels=False):
        # Get the multisynth currently associated with the channel specified
        multisynth_number = self.get_multisynth_from_channel(channel_number)

        if not ignore_affected_channels:
            # Check if other channels will be affected by this change
            channels_on_multisynth = self.get_channels_from_multisynth(multisynth_number)

            for affected_channel in channels_on_multisynth:
                if self.get_channel_output_enabled:     # Only warn for channels that are enabled
                    self.logger.warning(
                            "This channel shares a multisynth with ch {}.".format(affected_channel)
                            + " Both channels will be stepped. To ignore this warning, supply the "
                            + "argument ignore_affected_channels=True")

        self.increment_multisynth_frequency(multisynth_number)

    """
    Utility Functions:
    """
    def get_multisynth_from_channel(self, channel_number):
        return self._channel_multisynth_selection.read(channel_number)

    def get_channels_from_multisynth(self, multisynth_number):
        channel_list = []
        for channel in range(0, self._num_channels):
            if self.get_multisynth_from_channel(channel) == multisynth_number:
                channel_list.append(channel)
        return channel_list

    """
    Fault monitoring:
    These functions are aimed at monitoring state only. Set-up should be completed using CPB.
    """

    def get_enabled_fault_monitoring(self):
        # Return the currently enabled features for fault monitoring.
        pass

    def get_fault_report(self, attempt_use_pins=False):
        # Reads fault registers, returns False if no fault, or a report if there is one
        # If pins are supplied, it will skip the register access if neither are high.
        # Because of the immediate return, this could be used to create a custom async handler.
        # attempt_use_pins will try to use pins if available. If False will not even try
        # note that when pins are used, a there will be no result returned when there are fault flags

        # If monitoring via pins was asked for, warn if no pins are supplied
        if attempt_use_pins and self._LOL_Pin == None and self._INT_Pin == None:
            self.logger.warning("Requested a fault report with pin monitoring, but no pins configured.")

        # If pins are being used, return no report unless either of the pins is 1
        pinfault_found = False
        pins_checked = False
        if self._LOL_Pin != None and attempt_use_pins:
            pins_checked = True
            if self._LOL_Pin.read_value() == 0:   # If the pin is active (low)
                pinfault_found = True
        if self._INT_Pin != None and attempt_use_pins:
            pins_checked = True
            if self._INT_Pin.read_value() == 0:   # If the pin is active (high)
                pinfault_found = True

        # Only return false if the pins were actually used and neither found a fault
        if pins_checked and not pinfault_found:
            # Return a blank report, including no flags (despite these not being checked)
            return self._FaultReport(0,0,0,0,0,0,0,0)
        else:   # Either pins were not checked, or they were and a fault was found
            lol_status = self._fault_lol_status.read()
            lol_flag = self._fault_lol_flag.read()
            los_status = self._fault_los_status.read()
            los_flag = self._fault_los_flag.read()
            los_xtal_status = self._fault_los_xtal_status.read()
            los_xtal_flag = self._fault_los_xtal_flag.read()
            oof_status = self._fault_oof_status.read()
            oof_flag = self._fault_oof_flag.read()

            fault_report = self._FaultReport(lol_status, lol_flag, los_status, los_flag,
                                             los_xtal_status, los_xtal_flag,
                                             oof_status, oof_flag)

            return fault_report

    def clear_fault_flag(self, ALL=False, LOL=False, OOF=False, LOSXTAL=False,
                         LOS0=False, LOS1=False, LOS2=False, LOS3=False):
        if LOL or ALL:
            self._fault_lol_flag.write(0)
        if OOF or ALL:
            self._fault_oof_flag.write(0)
        if LOSXTAL or ALL:
            self._fault_los_xtal_flag.write(0)
        if LOS3 or ALL:
            self._fault_los_flag.write(0b0111)
        if LOS2 or ALL:
            self._fault_los_flag.write(0b1011)
        if LOS1 or ALL:
            self._fault_los_flag.write(0b1101)
        if LOS0 or ALL:
            self._fault_los_flag.write(0b1110)

    """
    Register Map File Functions
    """
    def apply_register_map(self, mapfile_csv_location, verify=False):
        #TODO update this text
        """
        Write configuration from a register map generated with DSPLLsim.
        Since the map is register rather than value-based, there is no need to make use
        of the _Field access functions.

        :param mapfile_location: location of register map file to be read
        :param verify: Boolean. If true, read registers back to verify they are written correctly.
        """
        with open(mapfile_csv_location) as csvfile:
            csv_reader = csv.reader(csvfile, delimiter=',')
            for row in csv_reader:
                # The register map starts after general information is printed preceded by '#'
                print("Line read from CSV: ", row) #TODO remove or make a logging line
                if row[0][0] == '0':    # Register values are preceeded by 0x
                    # Extract register-value pairing from register map
                    page_register = int(row[0], 0)  # 0x prefix detected automatically
                    #value = int(row[1][:-2], 0)     # \\r removed
                    value = int(row[1], 0)
                    register = page_register & 0xFF         # Lower byte
                    page = (page_register & 0xFF00) >> 8    # Upper byte
                    print("Storing value ", value, " in register ", register, " of page ", page)#TODO remove
                    # Write register value (whole byte at a time)
                    self.logger.info(
                            "Writing page 0x{:02X} register 0x{:02X} with value {:02X}".format(page,
                                                                                               register,
                                                                                               value))
                    self._write_paged_register_field(value, page, register, 7, 8)

                    if verify:
                        verify_value = self._read_paged_register_field(page, register, 7, 0)
                        self.logger.debug("Verifying value written ({:b}) against re-read: {:b}".format(
                            value,verify_value))
                        if verify_value != value:
                            raise SI534xCommsException(
                                    "Write of byte to register {} failed.".format(register))

        # ICAL-sensitive registers will have been modified during this process
        #TODO if ICAL (or another finishing command) is actually still relevant

    def export_register_map(self, mapfile_csv_location):
        #TODO update this text
        """
        Generate a register map file using the current settings in device control
        registers. This file can then be loaded using apply_register_map(filename).

        :param mapfile_location: location of register map file that will be written to.
        """
        with open(mapfile_csv_location, 'w') as csv_file:
            #TODO Potentially update header line wiht more information
            csv_file.write("# This register map has been generated for the odin-devices SI5324 driver.\n")
            csv_writer = csv.writer(csv_file, delimiter=',')

            # The registers that will be read are the ones found in output register
            # maps from DSPLLsim.
            for page, register in _SI534x._regmap_pages_registers_iter:

                #TODO potentially include any registers that read as 0 for triggers, that should not be
                # included in a write map, or need their values changing (like SI5342 ICAL)

                value = self._read_paged_register_field(page, register, 7, 8)
                print("Read register 0x{:02X}{:02X}: {:02X}".format(page, register, value))#TODO remove
                self.logger.info("Read register 0x{:02X}{:02X}: {:02X}".format(page, register, value))

                # File target format combines page and register into one 4-nibble hex value
                page_reg_combined = "0x{:02X}{:02X}".format(page, register)
                value_hex = "0x{:02X}".format(value)
                csv_writer.writerow([page_reg_combined, value_hex])

            self.logger.info("Register map extraction complete, to file: {}".format(mapfile_csv_location))

class SI5345 (_SI534x):
    def __init__(self, i2c_address=None, spi_device=None,
                 LOS_Line=None, LOL_Line=None, INT_Line=None):
        super(SI5345, self).__init__([0, 1, 2, 3, 4, 5, 6, 7, 8, 9],    # All channels
                                     5,             # 5 Multisynths, 0.5 per channel
                                     i2c_address, spi_device,
                                     LOL_Line, INT_Line)


class SI5344 (_SI534x):
    def __init__(self, i2c_address=None, spi_device=None,
                 LOS_Line=None, LOL_Line=None, INT_Line=None):
        super(SI5344, self).__init__([2, 3, 6, 7],  # 4 Channels, in SI5345 map positons 2, 3, 6, 7
                                     4,             # 4 Multisynths, 1 per channel
                                     i2c_address, spi_device,
                                     LOL_Line, INT_Line)


class SI5342 (_SI534x):
    def __init__(self, i2c_address=None, spi_device=None,
                 LOS_Line=None, LOL_Line=None, INT_Line=None):
        super(SI5342, self).__init__([2, 3],        # 2 Channels, in SI5345 map positions 2, 3
                                     2,             # 2 Multisynths, 1 per channel
                                     i2c_address, spi_device,
                                     LOL_Line, INT_Line)
