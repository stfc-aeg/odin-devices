

from odin_devices.i2c_device import I2CDevice, I2CException
import logging

class _SI534x:

    class _BitField():
        def __init__(self, page, start_register, start_bit_pos, bit_width, parent_device):
            self.page = page
            self.start_register = start_retister
            self.start_bit_pos = start_bit_pos
            self.bit_width = bit_width
            self.parent_device = parent_device

        def write(data):
            # Check data is of correct type (single value)
            if type(data) != int:
                #TODO throw type error
                pass
            # Check data fits in desired bit width
            if data >= (0b1 << bit_width):
                #TODO Throw data size error
                pass

            # Send data
            self.parent_device._write_paged_register_field(data, self.page, self.start_register,
                                                           self.start_bit_pos, self.bit_width)

        def read():
            return self.parent_device.chosen_bytes_read(self.page, self.start_register,
                                                        self.start_bit_pos, self.bit_width)

    class _Channel_BitField(_BitField):
        def __init__(self, page, first_channel_register, start_bit_pos, bit_width, parent_device,
                     channel_positions, channel_width):
            # bit_width is the width of this field, and channel_width is the width of the set of
            # channel-mapped fields.

            # Init shared fields using superclass
            super(_BitField, self).__init__(page, start_register, start_bit_pos, bit_width,
                                            parent_device)

            # Init additional channel-specific fields
            self.channel_positions = channel_positions
            self.channel_num = len(channel_positions)
            self.channel_width = channel_width
            self.first_channel_start_register = first_channel_register  # Static start of the field
            # start_register now becomes a dynamic value, set per channel on read / writes.

        def write(data, channel_num):
            # Check channel number is valid
            if channel_num >= self.num_channels:
                #TODO throw channel number error
                pass

            # Temporarily offset the _BitField start register
            self.start_register = self.first_channel_start_register
            channel_offset = self.channel_width * channel_positions[channel_num]
            self.start_register += self.channel_width * channel_offset

            # Call normal _BitField write function
            super(_BitField, self).write(data)

        def read(channel_num):
            # Check channel number is valid
            if channel_num >= self.num_channels:
                #TODO throw channel number error
                pass

            # Temporarily offset the _BitField start register
            self.start_register = self.first_channel_start_register
            channel_offset = self.channel_width * channel_positions[channel_num]
            self.start_register += self.channel_width * channel_offset

            # Call normal _BitField read function
            return super(_BitField, self).read()

    class _MultiSynth_BitField(_BitField):
        def __init__(self, page, synth0_register, start_bit_pos, bit_width, parent_device,
                     num_multisynths, synth_width):
            # bit_width is the width of this field, and synth_width is the width between adjacent
            # multi-synth mapped fields.

            # Init shared fields using superclass
            super(_BitField, self).__init__(page, synth0_register, start_bit_pos, bit_width,
                                            parent_device)

            # Init additional multisynth-specific fields
            self.num_multisyths = num_multisynths
            self.synth_width = synth_width
            self.synth0_register = synth0_register  # Static first synth register position 0 offset
            # start_register now becomes a dynamic value, set per multisynth on read/writes

        def write(data, synth_num): # Check synth number is valid
            if synth_num >= self.num_multisynths:
                #TODO throw error
                pass

            # Temporarily offset the _BitField start register
            self.start_register = self.synth0_register
            self.start_register += self.synth_width * synth_num

            # Call normal _BitField write function
            super(_BitField, self).write(data)

        def read(synth_num):
            # Check channel number is valid
            if synth_num >= self.num_multisynths:
                #TODO throw error
                pass

            # Temporarily offset the _BitField start register
            self.start_register = self.synth0_register
            self.start_register += self.synth_width * synth_num

            # Call normal _BitField read functions
            return super(_BitField, self).read()

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


    # An iterable of tuples in the form (page, register) where the pages and registers are those
    # that should be read from the device when creating a settings map with export_register_map()
    # for later re-write with the import_register_map() function.
    _regmap_pages_registers_iter = regmap_generator()

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
                 LOS_line=None, LOL_Line=None, INT_Line=None):
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


        #TODO define static fields
        self._output_driver_OUTALL_DISABLE_LOW = _BitField(page=0x01,
                                                           start_register = 0x02,
                                                           start_bit_pos = 0, bit_width = 1,
                                                           parent_device = self)

        #TODO define channel-mapped fields
        self._output_driver_cfg_PDN = _Channel_BitField(page=0x01,
                                                        first_channel_register = 0x08,
                                                        start_bit_pos = 0,
                                                        bit_width = 1,
                                                        parent_device = self,
                                                        channel_positions = channel_positions,
                                                        channel_width = 0x05)
        self._output_driver_cfg_OE = _Channel_BitField(page=0x01,
                                                       first_channel_register = 0x08,
                                                       start_bit_pos = 1,
                                                       bit_width = 1,
                                                       parent_device = self,
                                                        channel_positions = channel_positions,
                                                       channel_width = 0x05)

        #TODO define multisynth-mapped fields


        #TODO perform device init

    def _set_correct_register_page(self, target_page):
        # Set the correct page
        if self._reg_map_page_select == target_page:
            # Write to page register on whatever page we are currently on (irrelevant)
            self._write_register(0x01, target_page)
            self._reg_map_page_select = target_page

    def _write_paged_register_field(self, value_out, page, start_register, start_bit, width_bits):
        # The input to this function is a value rather than an array, so that it is easier to shift.
        # Also, most fields will be identifying a single value no matter their range, and so byte
        # boundaries hold no significance.

        # Set the correct page
        self._set_correct_register_page(page)

        # Align the output with register boundaries
        additional_lower_bits = (start_bit+1) - (width_bits%8)
        value_out = value_out << additional_lower_bits

        # Read original contents of registers as a value
        num_full_bytes = ((width_bits-1)/8)
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
            byte_bit_offset = ((num_full_byte-1) - byte_index) * 8
            byte_value = (value_out >> byte_bit_offset) & 0xFF
            self._write_register(start_register + byte_index, byte_value)

    def _read_paged_register_field(self, page, start_register, start_bit, width_bits):

        # Set the correct page
        self._set_correct_register_page(page)

        # Read whole range of bytes into single value to cover range
        full_bytes_value = 0
        num_full_bytes = ((width_bits-1) / 8)

        for byte_address in range(start_register, start_register + num_full_bytes):
            full_bytes_value << 8
            full_bytes_value += self._read_register(byte_address) & 0xFF

            # Remove unused start bits from first byte
            if byte_address == start_register:
                full_bytes_value = full_bytes_value & ((0b1<<(start_bit+1))-1)

        # Remove offset from resulting value
        additional_lower_bits = (start_bit+1) - (width_bits%8)
        full_bytes_value = full_bytes_value >> additional_lower_bits

        return full_bytes_value

    def _write_register_i2c(self, register, value):
        # Wrapper for writing a full 8-bit register over I2C, without page logic.
        self.i2c_bus.writeU8(register, value)

    def _read_register_i2c(self, register):
        # Wrapper for reading a full 8-bit register over I2C, without page logic.
        return self.i2c_bus.readU8(register)

    def _bytes_write_spi(self, register, value):
        pass

    def _bytes_read_spi(self, register):
        pass

    #TODO add functions for desirable option changes


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
                if row[0] != '#':
                    # Extract register-value pairing from register map
                    page_register = int(row[0], 0)  # 0x prefix detected automatically
                    value = int(row[1], 0)          # 0x prefix detected automatically
                    register = page_register & 0xFF         # Lower byte
                    page = (page_register & 0xFF00) >> 16   # Upper byte

                    # Write register value (whole byte at a time)
                    logger.info(
                            "Writing page 0x{:02X} register 0x{:02X} with value {:02X}".format(page,
                                                                                               register,
                                                                                               value))
                    self._write_registers([value], 1, page, register, 7, 8)

                    if verify:
                        verify_value = self._read_registers(page, register, 7, 0)
                        logger.debug("Verifying value written ({:b}) against re-read: {:b}".format(
                            value,verify_value))
                        if verify_value != value:
                            raise self.CommsException(
                                    "Write of byte to register {} failed.".format(register))

        # ICAL-sensitive registers will have been modified during this process
        #TODO if ICAL (or another finishing command) is actually still relevant

    def export_register_map(self, mapfile_location):
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
            for page, register in SI534x._regmap_pages_registers_iter:

                #TODO potentially include any registers that read as 0 for triggers, that should not be
                # included in a write map, or need their values changing (like SI5342 ICAL)

                value = self._read_registers(page, register)
                logger.info("Read register 0x{:02X}{:02X}: {:02X}".format(page, register, value))

                # File target format combines page and register into one 4-nibble hex value
                page_reg_combined = "0x{:02X}{:02X}".format(page, register)
                csv_writer.writerow([page_reg_combined, value])

            logger.info("Register map extraction complete, to file: {}".format(mapfile_location))

class SI5345 (_SI534x):
    def __init__(self, i2c_address=None, spi_device=None):
        super(SI5345, self).__init__([0, 1, 2, 3, 4, 5, 6, 7, 8, 9],    # All channels
                                     5,             # 5 Multisynths, 0.5 per channel
                                     i2c_address, spi_device,
                                     LOS_line, LOL_Line, INT_Line)


class SI5344 (_SI534x):
    def __init__(self, i2c_address=None, spi_device=None):
        super(SI5345, self).__init__([2, 3, 6, 7],  # 4 Channels, in SI5345 map positons 2, 3, 6, 7
                                     4,             # 4 Multisynths, 1 per channel
                                     i2c_address, spi_device,
                                     LOS_line, LOL_Line, INT_Line)


class SI5342 (_SI534x):
    def __init__(self, i2c_address=None, spi_device=None):
        super(SI5345, self).__init__([2, 3],        # 2 Channels, in SI5345 map positions 2, 3
                                     2,             # 2 Multisynths, 1 per channel
                                     i2c_address, spi_device,
                                     LOS_Line, LOL_Line, INT_Line)
