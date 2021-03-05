

class _SI534x:

    class _BitField():
        def __init__(self, page, start_register, start_bit_pos, bit_width, parent_device):
            self.page = page
            self.start_register = start_retister
            self.start_bit_pos = start_bit_pos
            self.bit_width = bit_width
            self.parent_device = parent_device

        def write(data):
            if type(data) == int:           # Convert value to list of bytes
                # Check data fits in desired bit width
                if data >= (0b1 << bit_width):
                    #TODO Throw data size error
                    pass

                list_data = []
                while (data > 0xFF):
                    list_data.insert(0, 0xFF & data)
                    data = data >> 8

                # Send data
                self.parent_device._write_registers(list_data, len(list_data), self.page, self.start_register, self.start_bit_pos, self.bit_width)

            elif type(data) == list:        # Send list of bytes directly
                # Check list fits within bit width  (Extra MSBs to boundary ignored)
                if len(data) > ((self.bit_width % 8) + 1):
                    #TODO Throw data size error
                    pass

                # Send data
                self.parent_device._write_registers(data, len(data), self.page, self.start_register, self.start_bit_pos, self.bit_width)

        def read():
            return self.parent_device.chosen_bytes_read(self.page, self.start_register, self.start_bit_pos, self.bit_width)

    class _Channel_BitField(_BitField):
        def __init__(self, page, first_channel_register, start_bit_pos, bit_width, parent_device, num_channels, channel_width):
            # bit_width is the width of this field, and channel_width is the width of the set of channel-mapped fields.

            # Init shared fields using superclass
            super(_BitField, self).__init__(page, start_register, start_bit_pos, bit_width, parent_device)

            # Init additional channel-specific fields
            self.num_channels = num_channels
            self.channel_width = channel_width
            self.first_channel_start_register = first_channel_register  # Holds the static start of the field
            # start_register now becomes a dynamic value, set per channel on read / writes.

        def write(data, channel_num):
            # Check channel number is valid
            if channel_num >= self.num_channels:
                #TODO throw channel number error
                pass

            # Temporarily offset the _BitField start register
            self.start_register = self.first_channel_start_register
            self.start_register += self.channel_width * channel_num

            # Call normal _BitField write function
            super(_BitField, self).write(data)

        def read(channel_num):
            # Check channel number is valid
            if channel_num >= self.num_channels:
                #TODO throw channel number error
                pass

            # Temporarily offset the _BitField start register
            self.start_register = self.first_channel_start_register
            self.start_register += self.channel_width * channel_num

            # Call normal _BitField read function
            return super(_BitField, self).read()

    class _MultiSynth_BitField(_BitField):
        def __init__(self, page, synth0_register, start_bit_pos, bit_width, parent_device, num_multisynths, synth_width):
            # bit_width is the width of this field, and synth_width is the width between adjacent
            # multi-synth mapped fields.

            # Init shared fields using superclass
            super(_BitField, self).__init__(page, synth0_register, start_bit_pos, bit_width, parent_device)

            # Init additional multisynth-specific fields
            self.num_multisyths = num_multisynths
            self.synth_width = synth_width
            self.synth0_register = synth0_register  # Static first synth register position without offset
            # start_register now becomes a dynamic value, set per multisynth on read/writes

        def write(data, synth_num):
            # Check synth number is valid
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

    # Mapping of registers expected to be present when exporting a register map that could be later
    # programmed back into the device. It is easier to specify ranges and invalid registers instead
    # of listing 'allowed' registers. Each page can have multiple ranges. This is based on an
    # example exported register map CSV from ClockBuilder Pro.
    #                               {page : [range0,
    #                                        range1...]
    # Where ranges are defined as tuples of start, end and invalid values as a list:
    #                                        (start, end, [invalid value list])
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

    def __init__(self, num_channels, num_multisynths, channel_reg_offset, i2c_address=None, spi_device=None,
                 LOS_line=None, LOL_Line=None, INT_Line=None):
        #TODO Initiate chosen interface (set chosen read/write functions)
        if i2c_address is not None:
            #TODO init I2C

            self._write_registers = self._bytes_write_i2c
            self.chosen_bytes_read = self._bytes_read_i2c
        elif spi_device is not None:
            #TODO init SPI

            # Set the field byte access functions
            self._write_registers = self._bytes_write_spi
            self.chosen_bytes_read = self._bytes_read_spi
        else:
            #TODO throw error
            pass


        #TODO define static fields
        self._output_driver_OUTALL_DISABLE_LOW = _BitField(page=0x01,
                                                           start_register = 0x02,
                                                           start_bit_pos = 0, bit_width = 1,
                                                           parent_device = self)

        #TODO define channel-mapped fields
        self._output_driver_cfg_PDN = _Channel_BitField(page=0x01,
                                                        first_channel_register = 0x08 + channel_reg_offset * 0x05,
                                                        start_bit_pos = 0,
                                                        bit_width = 1,
                                                        parent_device = self,
                                                        num_channels = num_channels,
                                                        channel_width = 0x05)
        self._output_driver_cfg_OE = _Channel_BitField(page=0x01,
                                                       first_channel_register = 0x08 + channel_reg_offset * 0x05,
                                                       start_bit_pos = 1,
                                                       bit_width = 1,
                                                       parent_device = self,
                                                       num_channels = num_channels,
                                                       channel_width = 0x05)


        #TODO perform device init

    def _bytes_write_i2c(self, bytes_out,  bytes_out_length, page, start_register, start_bit, width_bits):
        pass

    def _bytes_read_i2c(self, page, start_register, start_bit, width_bits):
        pass

    def _bytes_write_spi(self, bytes_out,  bytes_out_length, page, start_register, start_bit, width_bits):
        pass

    def _bytes_read_spi(self, page, start_register, start_bit, width_bits):
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
        """
        Generate a register map file using the current settings in device control
        registers. This file can then be loaded using apply_register_map(filename).

        :param mapfile_location: location of register map file that will be written to.
        """
        with open(mapfile_csv_location, 'w') as csv_file:
            csv_file.write("# This register map has been generated for the odin-devices SI5324 driver.\n")
            csv_writer = csv.writer(csv_file, delimiter=',')

            # The registers that will be read are the ones found in output register
            # maps from DSPLLsim.
            for page_register in SI534x._regmap_registers:

                #TODO potentially include any registers that read as 0 for triggers, that should not be
                # included in a write map, or need their values changing (like SI5342 ICAL)

                value = self._read_registers(page, register)
                logger.info("Read register {}: {:02X}".format(register, value))
                f.write("{}, {:02X}h\n".format(register, value))

            logger.info("Register map extraction complete, to file: {}".format(mapfile_location))

class SI5345 (_SI534x):
    def __init__(self, i2c_address=None, spi_device=None):
        super(SI5345, self).__init__(12, 0, i2c_address, spi_device)


class SI5344 (_SI534x):
    def __init__(self, i2c_address=None, spi_device=None):
        super(SI5345, self).__init__(4, 2, i2c_address, spi_device)


class SI5342 (_SI534x):
    def __init__(self, i2c_address=None, spi_device=None):
        super(SI5345, self).__init__(2, 2, i2c_address, spi_device)
