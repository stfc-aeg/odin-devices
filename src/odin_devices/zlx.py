"""Driver for Microchip ZLx series of clock generators.

Primary focus on the relatively common process for loading register maps for configuration.

Register maps are generated using software available from Microchip, though different versions
are used for different sub-families of device. For example, the 'ZL30267' version of the software
is used to create configurations for  ZL30260, ZL30261, ZL30262, ZL30263, ZL30264, ZL30265, ZL30266,
ZL30267, ZL40250, ZL40251, ZL40252, and ZL40253.

Since each variant has its own class, specifics to devices/families such as frequency stepping etc
could be added if desired.

Current functionality:

| Device | Support |
| ------ | ------- |
|        |         |


Device control is via either I2C or SPI for register access, which is also the mechanism for programming
in register maps (DUT files). An alternative is generating an EEPROM image, which can then be embedded
in an external or internal EEPROM, with selectable configurations chosen by digital pins.

Joseph Nobes, Grad Embedded Sys Eng, STFC Detector Systems Software Group
"""

from odin_devices.i2c_device import I2CDevice
from odin_devices.spi_device import SPIDevice
import logging
import time
from smbus2 import i2c_msg


class ZLFlaggedChannelException(Exception):
    """Exception thrown if the user has attmpted to use a channel marked as flagged.

    The user is able to mark flagged channels on init, which will rais this exception if someone attempts
    to load a config that would modify the channel. This is a safety feature to prevent the accidental setting
    of channels that might damage other devices if set to the incorrect voltage. It is optional.
    """

    pass


class ZLx(object):
    """Control class for the ZLx family of clock generators."""

    SPI_CMD_WRITE_ENABLE = 0x06
    SPI_CMD_WRITE = 0x02
    SPI_CMD_READ = 0x03
    SPI_CMD_READ_STATUS = 0x05

    _support_internal_eeprom = False
    _num_channels = 0
    _output_en_mapping = {}

    # Store as [num: {}] where the following dict must at least contain 'offset' for register info.
    _channel_info = {}

    def __init__(self, use_spi=False, use_i2c=False, bus=0, device=0, nreset_pin=None):
        """Initialise device contact with I2C or SPI, and check communication works.

        :param use_spi:     bool to specify if using spi.
        :param use_i2c:     bool to specify if using i2c.
                        Note: use_i2c and use_spi can both be False if the user only wants
                        to be able to select pre-stored EEPROM configs with pins.
        :param bus:         bus number for SPI/I2C device
        :param device:      device number for SPI device, address for I2C.
        :param nreset_pin:  Optional active low reset pin, assumed to be gpiod pre-requested line.
        """
        self._logger = logging.getLogger('ZLx')

        self._pin_nreset = nreset_pin

        # Store a list of register addresses associated with output enables for later use.
        self._output_en_regs = set()
        for address, bit in self._output_en_mapping.values():
            self._output_en_regs.add(address)
        self._output_en_regs = list(self._output_en_regs)   # Convert to list

        # TODO Initially cycle the reset, potentially with selected config pins if they
        # are present

        # Set either I2C or SPI interface (or neither)
        if use_i2c:
            self.device = I2CDevice(address=device, busnum=bus)
        elif use_spi:
            self.device = SPIDevice(device=device, bus=bus)
        else:
            self._logger.warning('ZL device initialised without a comms bus. This prevents control other than selecting configurations in EEPROM via control pins')

        # EESEL is used to select whether registers or the internal EEPROM is to be accessed.
        # EESEL should be False (bit=0), meaning device registers in use by default.
        self._EESEL = None

        # TODO If no control pins are specified as well as no interface, throw an error

        # TODO make a basic check, read manufacturer info and check against expectation
        self._check_id()

    def num_channels(self):
        """Return the number of output channels this device has."""
        return len(self._channel_info.keys())

    def has_internal_eeprom(self):
        """Return a boolean, True if this device contains an internal EEPROM."""
        return bool(self._support_internal_eeprom)

    def _check_id(self):
        """Check the device's internal ID against the expected one for the given part.

        If the required ID is known, read from the device and check that it's what is expected.
        If there is a null response (255), assume comms failure and raise an exception
        Otherwise warn if the device is not as expected.
        """
        ID1 = self.read_register(0x30)
        ID2 = self.read_register(0x31)

        if ID1 == 255 or ID2 == 255:
            raise ('Failure reading device ID, got ID1: {}, ID2: {}'.format(ID1, ID2))

        readback_id = (ID1 << 4) | ((ID2 & 0xF0) >> 4)

        self._logger.info('Read back device ID as {}'.format(hex(readback_id)))

        if self._expected_ID != readback_id:
            self._logger.critical(
                'Read back device ID as {} but expected {}, is this the correct device?'.format(
                    readback_id, self._expected_ID))
        else:
            self._logger.info('ID matches expected')

        return readback_id

    def write_register(self, address, value, write_EEPROM=False, verify=False):
        """Write to a device register using the configured I2C or SPI interface.

        :param address:         Address of the register to be written
        :param value:           Value to write to the address, single byte
        :param write_EEPROM:    Boolean: If true, will write to the device EEPROM (if present) instead.
        :param verify:          Boolean: If true, will read back the value after writing to confirm success.
        """
        # Must have either SPI or I2C interface
        if self.device is None:
            raise Exception('No valid interface for writing registers')

        # If trying to write the internal EEPROM on a device that does not have it
        if (not self._support_internal_eeprom) and write_EEPROM:
            raise RuntimeError('Cannot write EEPROM of device that does not contain one')

        # If the EEPROM / register select is not correct and we are trying to access a register
        # that is supported by the internal EEPROM (>0x00), correct it.
        if (self._EESEL is not write_EEPROM) and address > 0x00:
            self.write_register(0x00, 0b10000000 if write_EEPROM else 0b00000000)
            self._EESEL = write_EEPROM

        if type(self.device) is I2CDevice:

            # Writing to EEPROM is a special case that requries extra 'write enable' command
            # without a register address
            if write_EEPROM:
                self.device.bus.write_byte(self.device.bus.address, value)

            # Make use of lower level i2c_rdwr to make non-standard I2C transactions
            # TODO merge in Tim's modifications to make I2CDevice do this automatically.
            transaction = []

            # Write command and 16-bit register address
            transaction.append(ZLx.SPI_CMD_WRITE)       # Write command
            transaction.append((address & 0xFF00) >> 8)   # Address upper byte
            transaction.append(address & 0x00FF)        # Address lower byte

            # Rest of the buffer is data to be written, in this case one byte
            transaction.append(value)

            write_msg = i2c_msg.write(self.device.address, transaction)
            self.device.bus.i2c_rdwr(write_msg)

        # Writing to SPI is more complex due to the register address structure
        elif type(self.device) is SPIDevice:

            # Writing to EEPROM is a special case that requries extra 'write enable' command
            # without a register address
            if write_EEPROM:
                transaction = [ZLx.SPI_CMD_WRITE_ENABLE]
                self.device.transfer(transaction)

            # Make use of lower level i2c_rdwr to make non-standard I2C transactions
            # TODO merge in Tim's modifications to make I2CDevice do this automatically.
            transaction = []

            # Write command
            transaction.append(ZLx.SPI_CMD_WRITE)

            # 16-bit register address
            transaction.append(address & 0xFF00)
            transaction.append(address & 0x00FF)

            # Data
            transaction.append(value)

            self.device.transfer(transaction)

    def write_register_bit(self, address, bit_pos, value, write_EEPROM=False, verify=False):
        """Write a single bit of a register with either 1 or 0.

        :param address:         Address of the reigster to access
        :param bit_pos:         Number of the bit position, 0-7 (0 is LSB).
        :param value:           Value to write to the bit, either 1 or 0.
        :param write_EEPROM:    Boolean: If true, will write to the device EEPROM (if present) instead.
        :param verify:          Boolean: If true, will read back the value after writing to confirm success.
        """
        # Read the existing value
        reg_val_old = self.read_register(address, read_EEPROM=write_EEPROM)

        if value:
            # If setting the bit, simply ORing with the shifted bit will suffice
            reg_val = (0b1 << bit_pos) | reg_val_old
        else:
            # If clearing the bit, AND with inversion of the shifted bit
            reg_val = ~(0b1 << bit_pos) & 0xFF & reg_val_old

        self.write_register(address, reg_val, write_EEPROM=write_EEPROM, verify=verify)

    def read_register(self, address, read_EEPROM=False):
        """Read from a device register using the configured I2C or SPI interface.

        NOTE THAT THIS FUNCTION EXECUTES A TWO-PART WRITE-READ, WHICH MUST NOT HAVE OTHER TRAFFIC IN BETWEEN

        :param address:         Address of the register to be written
        :param read_EEPROM:     Boolean: If true, will read from the device EEPROM (if present) instead.
        """
        # Must have either SPI or I2C interface
        if self.device is None:
            raise Exception('No valid interface for writing registers')

        # If trying to read the internal EEPROM on a device that does not have it
        if (not self._support_internal_eeprom) and read_EEPROM:
            raise RuntimeError('Cannot read EEPROM of device that does not contain one')

        # If the EEPROM / register select is not correct and we are trying to access a register
        # that is supported by the internal EEPROM (>0x00), correct it.
        if (self._EESEL is not read_EEPROM) and address > 0x00:
            print('Correcting EESEL')
            self.write_register(0x00, 0b10000000 if read_EEPROM else 0b00000000)
            self._EESEL = read_EEPROM

        if type(self.device) is I2CDevice:
            # Make use of lower level i2c_rdwr to make non-standard I2C transactions
            # TODO merge in Tim's modifications to make I2CDevice do this automatically.
            transaction = []

            # Read command and 16-bit register address
            transaction.append(ZLx.SPI_CMD_READ)            # Read command
            transaction.append((address & 0xFF00) >> 8)     # Address upper byte
            transaction.append(address & 0x00FF)            # Address lower byte

            write_msg = i2c_msg.write(self.device.address, transaction)
            self.device.bus.i2c_rdwr(write_msg)

            # Read the data byte back, return first byte
            read_msg = i2c_msg.read(self.device.address, 1)
            self.device.bus.i2c_rdwr(read_msg)

            # Only return one value
            return list(read_msg)[0]

        # Writing to SPI is more complex due to the register address structure
        elif type(self.device) is SPIDevice:
            transaction = []

            # Write command
            transaction.append(ZLx.SPI_CMD_READ)

            # 16-bit register address
            transaction.append(address & 0xFF00)
            transaction.append(address & 0x00FF)

            # Data
            value = 0x00    # Just a buffer
            transaction.append(value)

            # Return the transaction minus the preamble
            return self.device.transfer(transaction)[3:]

    def write_config_mfg(self, filepath, check_dev_id=True, flag_channels=[]):
        """Write a pre-prepared confuration file to the device, with .mfg extension.

        :param filepath:        Full path and filename of the file to be written.
        :param check_dev_id:    Whether the device ID should be checked to confirm the file was
                                generated for the same device type. Optional, True by default.
        :param flag_channels:   A list of channel numbers that will be considered 'flagged'- if the
                                configuration in the file attampts to alter these channels, an
                                exception will be raised.
        """
        # Must have either SPI or I2C interface
        if self.device is None:
            raise Exception('No valid interface for writing registers')

        # Scan the whole file first before attempting to write the config
        with open(filepath, "r") as f:
            try:
                self._check_mfg(f, check_dev_id=check_dev_id, flag_channels=flag_channels)
            except Exception as e:
                raise Exception('Could not use mfg; config check failed: {}'.format(e))

        # Reset the device (the mfg format assumes initial reset state)
        self.cycle_reset()

        self._logger.info('Starting write sequence for mfg config {}'.format(filepath))

        # Step through the mfg file's steps
        with open(filepath, "r") as f:
            self._follow_mfg(f)

        self._logger.info('Finished writing mfg config {}'.format(filepath))

    def _mfg_parse_line(line):
        if line.startswith(';'):
            linetype = 'comment'
            content = line[2:]

        elif line.startswith('X'):
            linetype = 'regwrite'

            # Discard comment if there is one (;), and separate command by comma
            writeinfo = line.split(';')[0].split(',')

            address = int(writeinfo[1], 16)
            value = int(writeinfo[2], 16)
            content = (address, value)

        elif line.startswith('W'):
            linetype = 'wait'

            waittime = int(line.split(',')[1])
            content = (waittime)

        elif len(line) == 1:
            linetype = 'whitespace'
            content = ''

        else:
            raise Exception('Line type not recognised')

        return (linetype, content)

    def _check_mfg(self, filehandle, check_dev_id, flag_channels=[]):
        # Checks:
        # 1. ID
        #   Check the Device ID Matches and is the first line.
        #   Enabled with check_dev_id=True
        # 2. Flagged Channels
        #   Check if certain channels are being enabled by the config, if requested by the
        #   caller. This can be used as a form of protection of downstream devices.

        if check_dev_id:
            headerline = filehandle.readline()
            if headerline.startswith('; Device Id'):
                # TODO check ID matches
                pass
            else:
                raise Exception('Could not find device ID in mfg file')

        # Parse each line checking for errors, but ignoring content
        for line in filehandle.readlines():
            linetype, content = ZLx._mfg_parse_line(line)

        if linetype == 'regwrite':
            address, value = content

            # If the register address is known to be used for output enable bits
            if address in self._output_en_regs:

                # If any channel to be flagged has its bit set high, raise
                for check_channel in flag_channels:
                    check_addr, check_bit = self._output_en_mapping[check_channel]
                    if check_addr == address and ((0b1 << check_bit) & value > 0):
                        raise ZLFlaggedChannelException('You are attempting to program channel {}, which has been flagged.')

    def _follow_mfg(self, filehandle):
        # Tally the number of register writes since this can be checked at the end
        write_count = 0

        filehandle

        for line in filehandle.readlines():
            linetype, content = ZLx._mfg_parse_line(line)
            #self._logger.debug('Parsed line {}: {}, {}'.format(line, linetype, content))

            if linetype == 'regwrite':
                address, value = content
                self.write_register(address, value)

                self._logger.debug(
                    'Wrote register {} value {} as specified by mfg line: {}'.format(
                        hex(address), hex(value), line[:-1]
                    )
                )
                write_count += 1

            elif linetype == 'wait':
                waittime_us = content
                time.sleep(waittime_us / 1000000.0)

            elif linetype == 'comment':
                # The only comment we are interested in is the write count at the end
                if 'Register Write Count' in content:
                    target_write_count = int(content.split('=')[1])

        try:
            if target_write_count != write_count:
                self._logger.warning('Register write count did not match...')
        except NameError:
            self._logger.warning('No target register write count decoded from mfg')

    def enter_reset(self):
        """Enter reset state using a GPIO pin if provided, or use the register reset otherwise.

        The register reset (MCR1.RST) is a less thorough reset, so if possible the hardware reset pin
        should be used. However, the GPIO line may not have been provided to the driver.
        """
        # If there is a reset pin, use it; this is a more thorough reset
        if self._pin_nreset is not None:
            self._pin_nreset.set_value(0)

        # Otherwise use the MCR1.RST bit
        else:
            self._logger.warning('Using the MCR1.RST bit to reset the device due to lack of supplied GPIO pin. This is not a full reset.')
            self.write_register_bit(0x09, 7, 1)

    def exit_reset(self):
        """Exit reset state using a GPIO pin if provided, or use the register reset otherwise."""
        # If there is a reset pin, use it; this is a more thorough reset
        if self._pin_nreset is not None:
            self._pin_nreset.set_value(1)

        # Otherwise use the MCR1.RST bit.
        else:
            self._logger.warning('Using the MCR1.RST bit to bring the device out of reset due to lack of supplied GPIO pin. This will not work if the physical reset pin is still asserted.')
            self.write_register_bit(0x09, 7, 0)
            pass

    def cycle_reset(self, delay_ms=20):
        """Cycle through a reset cycle to end up in the out-of-reset state.

        :param delay_ms:        Override the time held in reset state in ms, default 20ms.
        """
        self.enter_reset()
        time.sleep(delay_ms / 1000)
        self.exit_reset()


"""
Support for the ZL30244/ZL30245.

These are dual-channel devices with completely separate channels (i.e. each has
its own I2C/SPI bus, interface select pins, etc. Therefore each essentially
functions as its own device.

It is possible to have each on a different bus, use one as I2C, one as SPI etc.

The GUI will generate configurations that are appended for these, just split them
before use.

The device classes should then be called with two channels (or None if one is not
in use).

"""


class _ZL30244_45Channel(ZLx):
    _support_internal_eeprom = False
    _num_channels = 3
    _output_en_mapping = {
        # num: (address, bit)
        1: (0x0D, 0),
        2: (0x0D, 1),
        3: (0x0D, 2),
    }


class ZL30244Channel(_ZL30244_45Channel):
    """Driver for a single channel of the ZL30244 clock generator."""

    _support_internal_eeprom = False


class ZL30245Channel(_ZL30244_45Channel):
    """Driver for a single channel of the ZL30245 clock generator."""

    _support_internal_eeprom = True


"""
Support for the ZL30264-ZL30267
"""


class _ZL30264_67(ZLx):
    _output_en_mapping = {
        # num: (address, bit)
        1: (0x05, 0),
        2: (0x05, 1),   # 10-channel devices only
        3: (0x05, 2),
        4: (0x05, 3),
        5: (0x05, 4),   # 10-channel devices only
        6: (0x05, 5),
        7: (0x05, 6),   # 10-channel devices only
        8: (0x05, 7),
        9: (0x06, 0),
        10: (0x06, 1),  # 10-channel devices only
    }


class _ZL30264_65(_ZL30264_67):
    _num_channels = 6


class ZL30264(_ZL30264_65):
    """Driver for the ZL30264 clock generator."""

    _support_internal_eeprom = False
    _expected_ID = 0x1D8


class ZL30265(_ZL30264_65):
    """Driver for the ZL30265 clock generator."""

    _support_internal_eeprom = True
    _expected_ID = 0x1F8


class _ZL30266_67(_ZL30264_67):
    _num_channels = 10


class ZL30266(_ZL30266_67):
    """Driver for the ZL30266 clock generator."""

    _support_internal_eeprom = False
    _expected_ID = 0x1D9


class ZL30267(_ZL30266_67):
    """Driver for the ZL30267 clock generator."""

    _support_internal_eeprom = True
    _expected_ID = 0x1F9
