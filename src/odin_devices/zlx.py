"""
Driver for supporting the Microchip ZLx series of clock generators, with a primary focus on the
relatively common process for loading register maps for configuration.

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

class ZLx(object):
    SPI_CMD_WRITE_ENABLE = 0x06
    SPI_CMD_WRITE = 0x02
    SPI_CMD_READ = 0x03
    SPI_CMD_READ_STATUS = 0x05

    _support_internal_eeprom = False
    _num_channels = 0

    # Store as [num: {}] where the following dict must at least contain 'offset' for register info.
    _channel_info = {}

    def __init__(self, use_spi=False, use_i2c=False, bus=0, device=0, nreset_pin=None):
        '''
        :param use_spi:     bool to specify if using spi.
        :param use_i2c:     bool to specify if using i2c.
                        Note: use_i2c and use_spi can both be False if the user only wants
                        to be able to select pre-stored EEPROM configs with pins.
        :param bus:         bus number for SPI/I2C device
        :param device:      device number for SPI device, address for I2C.
        :param nreset_pin:  Optional active low reset pin, assumed to be gpiod pre-requested line.
        '''
        self._logger = logging.getLogger('ZLx')

        self._pin_nreset = nreset_pin

        #TODO Initially cycle the reset, potentially with selected config pins if they
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

        #TODO If no control pins are specified as well as no interface, throw an error

        #TODO make a basic check, read manufacturer info and check against expectation
        self._check_id()

    def num_channels(self):
        return len(self._channel_info.keys())

    def has_internal_eeprom(self):
        return bool(self._support_internal_eeprom)

    def _check_id(self):
        # If the required ID is known, read from the device and check that it's what is expected.
        # If there is a null response (255), assume comms failure and raise an exception
        # Otherwise warn if the device is not as expected.

        ID1 = self.read_register(0x30)
        ID2 = self.read_register(0x31)

        if ID1 == 255 or ID2 == 255:
            raise ('Failure reading device ID, got ID1: {}, ID2: {}'.format(ID1, ID2))

        readback_id = (ID1 << 4) | ((ID2 & 0xF0) >> 4)

        self._logger.info('Read back device ID as {}'.format(hex(readback_id)))

        if self._expected_ID != readback_id:
            self._logger.warning(
                'Read back device ID as {} but expected {}, is this the correct device?'.format(
                    readback_id, self._expected_ID))

        return readback_id

    def write_register(self, address, value, write_EEPROM=False, verify=False):
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

        if type(self.device) is I2CDevice:

            # Writing to EEPROM is a special case that requries extra 'write enable' command
            # without a register address
            if write_EEPROM:
                self.device.bus.write_byte(self.device.bus.address, value)

            # Make use of lower level i2c_rdwr to make non-standard I2C transactions
            # TODO merge in Tim's modifications to make I2CDevice do this automatically.
            transaction = []

            # Write command and 16-bit register address
            transaction.append(ZLx.SPI_CMD_WRITE)	# Write command
            transaction.append((address & 0xFF00)>>8)	# Address upper byte
            transaction.append(address & 0x00FF)	# Address lower byte

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

    def write_register_bit(self, address, bit_pos, value, write_EEPROM, verify):
        # Read the existing value
        reg_val_old = self.read_register(address, read_EEPROM=write_EEPROM)

        if value:
            # If setting the bit, simply ORing with the shifted bit will suffice
            reg_val = (0b1 << bit_pos) | reg_val_old
        else:
            # If clearing the bit, AND with inversion of the shifted bit
            reg_val = ~(0b1 << bit_pos) & 0xFF & reg_val_old

        self.write_register(address, reg_val, write_EEPROM=write_EEPROM, verify=verify)

    def read_register(self, address, read_EEPROM):
	# NOTE THAT THIS FUNCTION EXECUTES A TWO-PART WRITE-READ, WHICH MUST NOT HAVE OTHER TRAFFIC IN BETWEEN

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
            #self.write_register(0x00, 0b10000000 if read_EEPROM else 0b00000000)

        if type(self.device) is I2CDevice:
            # Make use of lower level i2c_rdwr to make non-standard I2C transactions
            # TODO merge in Tim's modifications to make I2CDevice do this automatically.
            transaction = []

            # Read command and 16-bit register address
            transaction.append(ZLx.SPI_CMD_READ)	# Read command
            transaction.append((address & 0xFF00)>>8)	# Address upper byte
            transaction.append(address & 0x00FF)	# Address lower byte

            write_msg = i2c_msg.write(self.device.address, transaction)
            self.device.bus.i2c_rdwr(write_msg)

            # Read the data byte back, return first byte
            read_msg = i2c_msg.read(self.device.address, 1)
            self.device.bus.i2c_rdwr(read_msg)
            return list(read_msg)[0]	# Only return one value

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

    def write_config_mfg(self, filepath, check_dev_id=True):
        # Must have either SPI or I2C interface
        if self.device is None:
            raise Exception('No valid interface for writing registers')

        # Scan the whole file first before attempting to write the config
        with open(filepath, "r") as f:
            try:
                self._check_mfg(f, check_dev_id=check_dev_id)
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

    def _check_mfg(self, filehandle, check_dev_id):
        # Check the Device ID Matches and is the first line
        if check_dev_id:
            headerline = filehandle.readline()
            if headerline.startswith('; Device Id'):
                #TODO check ID matches
                pass
            else:
                raise Exception('Could not find device ID in mfg file')

        # Parse each line checking for errors, but ignoring content
        for line in filehandle.readlines():
            print(filehandle)
            print(line)
            ZLx._mfg_parse_line(line)

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
                        address, value, line
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
        # If there is a reset pin, use it; this is a more thorough reset
        if self._pin_nreset is not None:
            self._pin_nreset.set_value(0)

        # Otherwise use the MCR1.RST bit
        else:
            self._logger.warning('Using the MCR1.RST bit to reset the device due to lack of supplied GPIO pin. This is not a full reset.')
            self.write_register_bit(0x09, 7, 1)

    def exit_reset(self):
        # If there is a reset pin, use it; this is a more thorough reset
        if self._pin_nreset is not None:
            self._pin_nreset.set_value(1)

        # Otherwise use the MCR1.RST bit.
        else:
            self._logger.warning('Using the MCR1.RST bit to bring the device out of reset due to lack of supplied GPIO pin. This will not work if the physical reset pin is still asserted.')
            self.write_register_bit(0x09, 7, 0)
            pass

    def cycle_reset(self, delay_ms=20):
        self.enter_reset()
        time.sleep(delay_ms/1000)
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
class ZL30244_45Channel(ZLx):
    _support_internal_eeprom = False
    _num_channels = 3

class ZL30244Channel(ZL30244_45Channel):
    _support_internal_eeprom = False

class ZL30245Channel(ZL30244_45Channel):
    _support_internal_eeprom = True

"""
Support for the ZL30264-ZL30267
"""
class ZL30264_67(ZLx):
    pass

class ZL30264_65(ZL30264_67):
    _num_channels = 6

class ZL30264(ZL30264_65):
    _support_internal_eeprom = False
    _expected_ID = 0x1D8
class ZL30265(ZL30264_65):
    _support_internal_eeprom = True
    _expected_ID = 0x1F8

class ZL30266_67(ZL30264_67):
    _num_channels = 10

class ZL30266(ZL30266_67):
    _support_internal_eeprom = False
    _expected_ID = 0x1D9
class ZL30267(ZL30266_67):
    _support_internal_eeprom = True
    _expected_ID = 0x1F9
