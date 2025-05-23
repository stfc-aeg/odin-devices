"""
Samtec Firefly - device access class for the I2C control interface fir Samtec FireFly flyover
systems. This control interface allows channels to be enabled and disabled, as well as recovering
some diagnostic information such as internal case temperature.

The FireFly is controlled using either QSFP+ or CXP specifications, depending on the part used.
Currently, this driver has been written to target 4-channel QSFP+ devices and 12-channel CXP
devices. The interface used is detected automatically, but if there is an issue with this, it can
also be specified manually.

The register maps for QSFP+ and CXP (as well as Samtec's implementation) vary. Refer to FireFly 
Optical ECUO 14G x4 Data Sheet, FireFly Optical 14G x12 Data Sheet and as a general reference
InfiniBand Architecture Specification Volume 2 Release 1.3.

Note that the FireFly expects a select line to be used if more than one is present on the same bus.

Joseph Nobes, Grad Embedded Sys Eng, STFC Detector Systems Software Group
"""

from odin_devices.i2c_device import I2CDevice, I2CException
import smbus
import math
import logging
import time

logger = logging.getLogger('odin_devices.FireFly')

_GPIO_AVAIL = True
try:
    import gpiod
except Exception:
    _GPIO_AVAIL = False
    logger.warning("No support for GPIO, cannot use CS line")

# TODO I'm not sure if there is a better way of doing this that works in python 2 and 3
def _int_to_array(int_in, num_bytes):
    """
    Converts an integer value representing a multibyte field into an array of bytes.
    """
    new_value_array = []
    for byte_index in range(0, num_bytes):
        byte_offset = 8*((num_bytes-1) - byte_index)
        byte_masked = (0xFF << byte_offset) & int_in
        new_value_array.append(byte_masked >> byte_offset)
    return new_value_array

def _array_to_int(array_in):
    """
    Converts an array of bytes to an integer value representing a multibyte field.
    """
    out_value = 0
    for byte_index in range(0, len(array_in)):
        byte_offset = 8*((len(array_in)-1) - byte_index)
        out_value += array_in[byte_index] << byte_offset
    return out_value


class FireFly(object):
    """
    Outer class for user instantiation of a FireFly device. If one device is being used, no args
    should be required. If using multiple units, a select line will be needed. See __init__ for
    more information.

    The interface type (QSFP+ or CXP) should be determined automatically.
    """

    DIRECTION_TX = 1        # Definition used in driver only
    DIRECTION_RX = 0        # Definition used in driver only
    DIRECTION_DUPLEX = 2    # Definition used in driver only

    INTERFACE_CXP = 1
    INTERFACE_QSFP = 0

    CHANNEL_00  = 0b000000000001        # This is the first channel for CXP devices
    CHANNEL_01  = 0b000000000010        # This is the first channel for QSFP+ devices
    CHANNEL_02  = 0b000000000100
    CHANNEL_03  = 0b000000001000
    CHANNEL_04  = 0b000000010000
    CHANNEL_05  = 0b000000100000
    CHANNEL_06  = 0b000001000000
    CHANNEL_07  = 0b000010000000
    CHANNEL_08  = 0b000100000000
    CHANNEL_09  = 0b001000000000
    CHANNEL_10  = 0b010000000000
    CHANNEL_11  = 0b100000000000
    CHANNEL_ALL = 0xFFFF    # This MUST be masked before use

    _LOGGER_BASENAME = "odin_devices.FireFly"

    def __init__(self, Interface_Type=None, direction=None, num_channels=None, base_address=0x50, chosen_base_address=None, busnum=None, select_line=None):
        """
        Create an instance of a generic FireFly device. The interface type will be determined
        automatically, as will the number of channels. Devices are assumed to be in POR, and at
        address 0x50 by default on instantiation, but can be supplied an alternative address to
        switch to. Select lines are also supported, but if ignored it is assumed that the device
        is the only one present on the bus and has its select line pulled low.

        :param Interface_Type:  Type of interface to use, FireFly.INTERFACE_CXP/QSFP. In most cases
                                should be able to omit this and have it detected automatically.
        :param base_address:            The address on which the FireFly is expected to be found by default
        :param direction:       Direction, one of FireFly.DIRECTION_TX/RX/DUPLEX. This should not be required
                                        (will be determined from part number automatically) unless using a
                                        customised part, where the part number cannot be decoded.
        :param num_channels:    Override for number of channels, only required for custom parts (see above)
        :param chosen_base_address:     The address that the device will be assigned to. None for unchanged.
        :param busnum:          I2C bus to be used. If not supplied, will use system default.
        :param select_line:     GPIO line to use for active-low chip select, if used. This should be
                                a line provided by odin_devices.gpio_bus or directly via gpiod.
        """

        # Init logger for instance (likely to have multiple fireflies)
        loggername = FireFly._LOGGER_BASENAME + ('@0x%02x'%(chosen_base_address if chosen_base_address else base_address))
        self._log = logging.getLogger(loggername)
        self._log.info("Init FireFly with base address 0x%02x" % base_address)

        # Determine interface type automatically or use manually chosen one if supplied
        if Interface_Type is None:      # Detect interface automatically (default)
            INTERFACE_Detect = FireFly._get_interface(select_line, base_address, busnum, self._log)
            if INTERFACE_Detect is None:    # Automatic detection failed
                raise I2CException("Was unable to determine interface type automatically, " +
                                   "try specifying Interface_Type manually.")
        elif Interface_Type in [FireFly.INTERFACE_CXP, FireFly.INTERFACE_QSFP]:
            INTERFACE_Detect = Interface_Type
        else:
            raise I2CException("Manually specified interface type was invalid")

        # Instantiate the interface based on above manual/automatic select
        if INTERFACE_Detect == FireFly.INTERFACE_QSFP:
            self._interface = _interface_QSFP(loggername+".QSFP+", base_address, chosen_base_address, busnum, select_line)
            self._log.info("Interface detected as QSFP+ based")
        elif INTERFACE_Detect == FireFly.INTERFACE_CXP:
            self._interface = _interface_CXP(loggername+".CXP", base_address, chosen_base_address, busnum, select_line)
            self._log.info("Interface detected as CXP based")

        # From here onwards, interface and address specific functions can be called through
        # self._interface.???(), and address, register and select line usage will be handled.

        # Read some identifying information
        PN_ascii, VN_ascii, OUI = self.get_device_info()
        self._check_pn_fields(PN_ascii, direction, num_channels)
        self._log.info(
                "Found device, Vendor: {} ({}),\tPN: {}".format(VN_ascii, OUI, PN_ascii))

        # Turn off all Tx channels initially to prevent overheat
        self.disable_tx_channels(FireFly.CHANNEL_ALL)

        temp_tx = self.get_temperature(FireFly.DIRECTION_TX)
        self._log.info("Tx Temperature: {}".format(temp_tx))

    @staticmethod
    def _get_interface(select_line, default_address, busnum, log_instance=None):
        """
        Attempt to automatically determine the interface type (QSFP+ or CXP) that is being used by
        the FireFly device at a given I2C address, using a given select line (if used).

        :param select_line:     gpiod Line being used for CS. Provide with gpio_bus or gpiod.
        :param default_address: The address to use when attempting to communicate. Most likely this
                                is the default (0x50) since the device has not been configured.
        :param busnum:          I2C bus to be used.
        :param log_instance:    Because this is a static method, the self._log must be passed in
                                for logging to work.
        :return:                Interface type (FireFly.INTERFACE_*) or None if it could not be
                                determined automatically.
        """
        # Assuming the device is currently on the default address, and OUI is 0x40C880
        tempdevice = I2CDevice(default_address, busnum)

        if select_line is not None:
            # Check GPIO control is available
            if not _GPIO_AVAIL:
                raise I2CException(
                        "GPIO control is not available, cannot use CS line")

            # Check select_line is valid
            try:
                if not select_line.is_requested():
                    raise I2CException (
                            "GPIO Line supplied is not requested by user")
            except AttributeError:
                raise I2CException (
                        "Supplied line was not a valid object. Use gpiod or odin_devices.gpio_bus")

            # GPIO select line low
            select_line.set_value(0)

        # Force the page to 0x00
        tempdevice.write8(127, 0x00)
        # Read bytes 168, 169, 170
        cxp_oui = tempdevice.readList(168, 3)
        # Read bytes 165, 166, 167
        qsfp_oui = tempdevice.readList(165, 3)

        if select_line is not None:
            # GPIO select line high
            select_line.set_value(1)

        if log_instance is not None:
            log_instance.debug(
                    "Reading OUI fields from device at {}: CXP OUI {}, QSFP OUI {}".format(
                        default_address, cxp_oui,qsfp_oui))

        if cxp_oui == [0x04, 0xC8, 0x80]:
            # OUI found correctly, must be CXP device
            return FireFly.INTERFACE_CXP
        elif qsfp_oui == [0x04, 0xC8, 0x80]:
            # OUI found correctly, must be QSFP interface
            return FireFly.INTERFACE_QSFP
        else:
            if log_instance is not None:
                log_instance.critical("OUI not found during automatic detection")
            return None

    def _check_pn_fields(self, pn_str, direction=None, num_channels=None):
        """
        Checks some common fields accross all common devices to make sure the PN has been read
        correctly. Some fields important to the driver's operation are designated as CRITICAL, and
        will trigger an exception if failed. Others designated with WARNING will simply show a
        warning if the value is not recognised.

        This function also populates some fields used by the driver, like number of channels, data
        direction and data rate.

        :param pn_str:      String of unformatted Part number (without ECU0 prefix)
        :param direction:   Allow user to supply a direction instead of decoding it. This should not
                            be required unless the part is custom, since this renders the part number
                            un-decodable.
        :param num_channels:   Allow user to supply a number of channels instead of decoding it. This
                            should not be required unless the part is custom, since this renders the
                            part number un-decodable.
        """

        try:
            # (CRITICAL) Check data direction (width) field
            if pn_str[0] in ['T']:
                self.direction = FireFly.DIRECTION_TX
            elif pn_str[0] in ['R']:
                self.direction = FireFly.DIRECTION_RX
            elif pn_str[0] in ['B', 'Y']:
                self.direction = FireFly.DIRECTION_DUPLEX
            elif pn_str[0] in ['U']:
                # Currently unsure what this mode means
                #TODO
                pass
            elif pn_str[0:3] == "OTP":
                self._log.warning('Customised OTP part discovered, cannot decode part number further')

                # Special case: customised part. Direction cannot be derived from part number
                if direction is None:
                    raise I2CException(
                        'Device direction cannot be derived automatically for custom parts, please supply a direction')
                else:
                    self.direction = direction

                # Special case: customised part. Number of channels cannot be derived from part number
                if num_channels is None:
                    raise I2CException(
                        'Device number of channels cannot be derived automatically for custom parts, please supply num_channels'
                    )
                else:
                    self.num_channels = num_channels


                # Skip the other checks, since they won't pass
                return
            else:
                raise I2CException(
                        "Data direction {} in part number field not recognised".format(pn_str[0]))
            self._log.info("Device data direction: {}".format(pn_str[0]))

            # (CRITICAL) Check number of channels
            if pn_str[1:3] == '12':
                self.num_channels = 12
            elif pn_str[1:3] == '04':
                self.num_channels = 4
            else:
                raise I2CException("Unsupported number of channels: {}".format(pn_str[1:3]))
            self._log.info("Device channels: {}".format(self.num_channels))

            # (WARNING) Check data rate
            if pn_str[3:5] in ['14','16','25','28']:
                self.data_rate_Gbps = int(pn_str[3:5])
                self._log.info("Device data rate: {}Gbps".format(self.data_rate_Gbps))
            else:
                self._log.warning("Device data rate: unsupported ({})".format(pn_str[3:5]))

            # (CRITICAL) Check static padding fields (wrong implies invalid PN)
            if pn_str[8] != '0' or pn_str[10] != '1':
                raise I2CException("Invalid PN static field(s)")

            # (WARNING) Check heat sink type
            if pn_str[9] not in "12345":
                self._log.warning("Unknown head sink type ({})".format(pn_str[9]))

            # (WARNING) Fiber type
            if pn_str[11] not in "12456":
                self._log.warning("Unknown fiber type ({})".format(pn_str[11]))
        except Exception as e:
            raise I2CException('Failure while checking FireFly part number ({}) fields: {}'.format(
                pn_str, e
            ))

    def get_device_info(self):
        """
        Generic function to obtain the part number, vendor name and vendor OUI.

        :return:    Tuple of (part number (str), vendor name (str), vendor OUI (array))
        """
        part_number_array = self._interface.read_field(self._interface.FLD_Device_Part_No)
        vendor_name_array = self._interface.read_field(self._interface.FLD_Vendor_Name)
        vendor_OUI_array = self._interface.read_field(self._interface.FLD_Vendor_OUI)

        part_number_ascii = "".join([chr(value) for value in part_number_array])
        vendor_name_ascii = "".join([chr(value) for value in vendor_name_array])
        return (part_number_ascii, vendor_name_ascii, vendor_OUI_array)

    def get_temperature(self, direction=None):
        """
        Generic function to get the temperature of the firefly transmitter or receiver.

        :param direction:   Selection from DIRECTION_<TX/RX>
        :return:            float temperature of specified device
        """
        # If the supplied direction is None, but only one direction is possible for this device
        if (direction is None and (self.direction == FireFly.DIRECTION_TX or
                                   self.direction == FireFly.DIRECTION_RX)):
            direction = self.direction  # Derive temperature direction from simplex device
        elif (direction is None and FireFly.DIRECTION_DUPLEX):
            # If unspecified with a duplex device, just use the TX temperature
            direction = FireFly.DIRECTION_TX

        if direction == FireFly.DIRECTION_TX:
            temperature_bytes = self._interface.read_field(self._interface.FLD_Tx_Temperature)
        elif direction == FireFly.DIRECTION_RX:
            temperature_bytes = self._interface.read_field(self._interface.FLD_Rx_Temperature)
        else:
            raise I2CException("Invalid direction specified, and could not be derived")

        # Perform 8-bit 2's compliment conversion
        output_temp = (temperature_bytes[0] & 0b01111111) + \
            (-128 if ((temperature_bytes[0] & 0b10000000) != 0) else 0)

        return output_temp

    def get_time_at_temp_info(self, direction=None):
        pass

    def _check_channel_combination_in_range(self, channels_combined):
        """
        Check that the channel bits are valid for the number of channels & offset, but only if
        if channels are being set directly (i.e. not with CHANNEL_ALL). An exception will be
        raised on failure, otherwise no side effect.

        :param channels_combined:       Combined (ORed) field of channels to be tested
        """
        min_allowed_channelfield = 0b1 << self._interface.channel_no_offset
        max_allowed_channelfield = (0b1 <<
                                    (self._interface.channel_no_offset + self.num_channels)
                                    ) - 1
        if ((channels_combined < min_allowed_channelfield) or
                (channels_combined > max_allowed_channelfield)) and \
                channels_combined != FireFly.CHANNEL_ALL:
            raise Exception(
                    "Combined value ({}) must be between: {}-{}".format(channels_combined,
                                                                        min_allowed_channelfield,
                                                                        max_allowed_channelfield))

    def disable_tx_channels(self, channels_combined):
        """
        Generic function to disable a specified selection of transmitter channels, with chosen
        channels ORed together as a bitfield. Alternatively, CHANNEL_ALL can be passed to disable
        all device channels.

            e.g. disable_tx_channels(CHANNEL_00 | CHANNEL_01 | CHANNEL_05)

        :param channels_combined:   ORed channels: CHANNEL_<00-11> or CHANNEL_ALL
        """

        self._check_channel_combination_in_range(channels_combined)

        # Shift the channels in case interface starts numbering at 1...
        channels_combined = channels_combined >> self._interface.channel_no_offset

        # Mask off any channels that are not present
        channels_combined &= ((1 << self.num_channels) - 1)

        # Write to disable field, but preseve states of other channels
        old_values = self._interface.read_field(self._interface.FLD_Tx_Channel_Disable)

        # Combine old and new values
        new_value = _array_to_int(old_values) | channels_combined

        # Write out to field
        self._interface.write_field(self._interface.FLD_Tx_Channel_Disable,
                                    _int_to_array(new_value, len(old_values)))

    def enable_tx_channels(self, channels_combined):
        """
        Generic function to enable a specified selection of transmitter channels, with chosen
        channels ORed together as a bitfield. Alternatively, CHANNEL_ALL can be passed to enable
        all device channels.

            e.g. enable_tx_channels(CHANNEL_00 | CHANNEL_01 | CHANNEL_05)

        :param channels_combined:   ORed channels: CHANNEL_<00-11> or CHANNEL_ALL
        """

        self._check_channel_combination_in_range(channels_combined)

        # Shift the channels in case interface starts numbering at 1...
        channels_combined = channels_combined >> self._interface.channel_no_offset

        # Mask off any channels that are not present
        channels_combined &= ((1 << self.num_channels) - 1)

        # Write to disable field, but preseve states of other channels
        old_values = self._interface.read_field(self._interface.FLD_Tx_Channel_Disable)

        # Combine old and new values
        new_value = _array_to_int(old_values) & ~(channels_combined)

        # Write out to field
        self._interface.write_field(self._interface.FLD_Tx_Channel_Disable,
                                    _int_to_array(new_value, len(old_values)))

    def get_disabled_tx_channels_field(self):
        """
        Return a combined bitfield representing transmitter channels that have been disabled for
        the device. Note that depending on the encoding of channel names, this might be a shifted
        version of the actualy device register. The field value will correspond with CHANNEL_XX
        values, and can be checked with 'result & CHANNEL_XX'.

        :return:    Combined bitfield of disabled channels
        """
        byte_values = self._interface.read_field(self._interface.FLD_Tx_Channel_Disable)
        output_value = _array_to_int(byte_values)

        # Shift the channels in case the interface starts numbering at 1...
        output_value = output_value << self._interface.channel_no_offset

        return output_value

    def get_disabled_tx_channels(self):
        """
        Provides a more user-suited version of the above function, returning an array of booleans,
        one for each channel (numbering is the user's issue) where True means disabled.

        :return:    Array of booleans, True means disabled channel. Lowest number channel first.
        """
        # Get raw bitfield
        byte_values = self._interface.read_field(self._interface.FLD_Tx_Channel_Disable)
        output_value = _array_to_int(byte_values)

        # Construct array from bit positions, lowest channel number first
        channels_disabled = []
        for bit_offset in range (0, self.num_channels):
            channels_disabled.append(bool(output_value & (0b1 << bit_offset)))

        return channels_disabled

class _Field(object):
    """
    Class capable of storing data to encode fields that span multiple bytes or only segments of a
    few bits within a byte. Note that 'length' is in bits.
    """
    def __init__(self, register, startbit, length, write_only=False):
        """
        :param register:        The register within which the field starts (lowest address)
        :param startbit:        The bit position to start at within the full range of bytes that
                                will be read. For example, if reading the last 12 bits from a two
                                byte field, startbit=11.
        :param length:          Length of the field from startbit in bits.
        :param write_only:      Specifies that the field will not respond with valid values if read.
        """
        self.register = register
        self.startbit = startbit
        self.length = length
        self.write_only = write_only

    def get_endbit(self):
        """
        Calculates the postition of the last bit in a field using the length and startbit position.
        """
        return (self.startbit - (self.length - 1))


class _FireFly_Interface(object):
    """
    Generic class to be extended by alternative interfaces (and memory maps) for the FireFly.
    Currently this supports automatic detection and interaction with devices that report compliance
    with CXP and QSFP+.

    Interfaces should contain the same public access methods and public attributes (mainly the FLD
    register field definitions) so that externally they behave the same as treated by the main
    FireFly instance, which will have ownership of one type of interface (detected automatically).
    """

    def __init__(self, channel_no_offset, loggername, base_address=0x50, chosen_base_address=None, busnum=None, select_line=None):
        """
        :param channel_no_offset:       The channel numbering offset from 0 that the interface
                                        uses. For example, QSFP+ starts at channel 1, and so has an
                                        offset of 1.
        :param loggername:              Name to use when creating the logger.
        :param base_address:            The address on which the FireFly is expected to be found by default
        :param chosen_base_address:     The address that the device will be assigned to. None for unchanged.
        :param busnum:                  I2C bus number, None for default.
        :param select_line:             Optional gpiod pin for device select, will be used if provided.
        """

        self.channel_no_offset = channel_no_offset
        self._log = logging.getLogger(loggername)

        # Set up select line use for the given address
        self._select_line = select_line

        # Establish contact with the device on the initial interface
        self._setup_interface(base_address=base_address, busnum=busnum, select_line=select_line)

        # If one has been supplied, change the address, setting up the new interface automatically
        if chosen_base_address is not None:
            self._change_address(chosen_base_address, busnum=busnum, select_line=select_line)

    def _setup_interface(self, base_address, busnum, select_line):
        # Will be overridden by QSFP or CXP
        pass

    def _change_address(self, chosen_base_address, busnum, select_line):
        # Will be overridden by QSFP or CXP
        pass

    def read_field(self, field, i2c_device):
        """
        Generic function to read from a register field (see above).

        :field:         Field instance containing information about field location and size
        :i2c_device:    I2CDevice instance that will be read from
        :return:        Array of byte values from field, with no offset. If less than the size of
                        one byte, an array of size 1 is returned.
        """
        self._log.debug("Getting field starting at bit {}, length {} from register {}".format(
            field.startbit,field.length,field.register))

        # Read byte values from starting register onwards
        num_full_bytes = int(math.ceil((field.length + field.get_endbit()) / float(8)))
        raw_register_values = i2c_device.readList(field.register, num_full_bytes)

        # Check resulting I2C read format and length
        if (type(raw_register_values) != list):
                raise I2CException("Failed to read byte list from I2C Device")
        if (len(raw_register_values) != num_full_bytes):
                raise I2CException("Number of bytes read incorrect. "
                    "Expected {}, got {}: {}".format(num_full_bytes,
                                                     len(raw_register_values),
                                                     raw_register_values))

        # Convert to a single value
        out_value = _array_to_int(raw_register_values)
        self._log.debug("\tRegister value: {:x}".format(out_value))

        # Create mask for value location
        new_mask = int(math.pow(2, field.length)) - 1   # Create to match field size
        new_mask = new_mask << field.get_endbit()       # Shift to correct position
        self._log.debug("\tCreated mask: {:x}".format(new_mask))

        # Mask off unwanted bits
        out_value &= new_mask
        self._log.debug("\tMasked output: {:x}".format(out_value))

        # Shift value down to endbit position 0
        out_value = out_value >> field.get_endbit()
        self._log.debug("\tShifted output:{:x}".format(out_value))

        # Calculate the number of bytes needed for output
        num_output_bytes = int(math.ceil(field.length / 8.0))

        return _int_to_array(out_value, num_output_bytes)

    def write_field(self, field, values, i2c_device, verify=False):
        """
        Generic function to write a field to registers, where the field may both span multiple
        registers and start and stop at any bit (completely variable length).

        :field:         Field instance containing information about field location and size
        :value:         Array of byte values that will be written directly to the field bits only.
                        If the field is smaller than 1 byte, supply an array of size 1.
        :i2c_device:    I2CDevice instance that will be written to
        """
        # Convert array values to a single value for easier masking and shifting
        value = _array_to_int(values)

        self._log.debug("Writing value {} to field {}-{} in register {}".format(
            value,field.startbit,field.get_endbit(),field.register))

        # Check input fits in specified field
        if (1 << (field.length)) <= value:
            raise I2CException(
                    "Value {} does not fit in specified field of length {}.".format(
                        value, field.length))

        # Align new value with register bytes
        value = value << field.get_endbit()

        # Read old value, align with register bytes
        try:
            old_values = super(type(self), self).read_field(field, i2c_device)
        except AttributeError:
            old_values = self.read_field(field, i2c_device)     # Probably called directly
        old_value = _array_to_int(old_values) << field.get_endbit()
        self._log.debug("\tOld register value: {:x}".format(old_value))

        # Create mask for value location
        new_mask = int(math.pow(2, field.length)) - 1   # Create to match field size
        new_mask = new_mask << field.get_endbit()       # Shift to correct position
        self._log.debug("\tCreated mask: {:x}".format(new_mask))

        # Apply mask to old value to clear new value space
        new_value = old_value &  ~new_mask

        # Overwrite high bits from new value
        new_value |= value
        self._log.debug("\tApplied output: {:x}".format(new_value))

        # Convert an array of bytes, and write
        num_full_bytes = int(math.ceil((field.length + field.get_endbit()) / float(8)))
        new_value_array = _int_to_array(new_value, num_full_bytes)
        i2c_device.writeList(field.register, new_value_array)   # Perform write
        self._log.debug("\tWrite list: {}".format(new_value_array))

        # Verify
        if verify:
            try:
                verify_value = super(type(self), self).read_field(field, i2c_device)
            except AttributeError:
                verify_value = self.read_field(field, i2c_device)   # Probably called directly
            verify_value_int = _array_to_int(verify_value)
            self._log.debug("Verifying value written ({:b}) against re-read: {:b}".format(
                value, verify_value_int))
            if verify_value_int != value:
                raise I2CException(
                        "Value {} was not successfully written to Field {}".format(
                            value, field))

        time.sleep(0.040)       # Write operations (especially upper02) should be separated by 40ms

    def _select_device(self):
        if self._select_line is not None:
            # pull select line low
            self._select_line.set_value(0)

    def _deselect_device(self):
        if self._select_line is not None:
            # pull select line high
            self._select_line.set_value(1)


class _interface_CXP(_FireFly_Interface):
    """
    Class describing specifics of CXP-based interfaces for the FireFly.

    This includes a unique memory map and address allocation methods, along with the separation of
    registers for transmission and reception. The memory map is also paged for the upper range.
    """

    class _Field_CXP(_Field):
        """
        Nested bit field class to access fields within the CXP memory map. Includes pages, as well
        as the is_tx flag which determines which of the two I2C addresses should be used (since the
        CXP interface separates the functionality).
        """
        def __init__(self, register, is_tx, page, startbit, length, write_only=False):
            """
            :param register:        See _Field
            :param is_tx:           True if the field is for the transmitter register map.
            :param page:            The page number the register(s) reside in. this is only relevant
                                    for registers in the upper page (>127).
            :param startbit:        See _Field
            :param length:          See _Field
            :param write_only:      See _Field
            """
            _Field.__init__(self, register, startbit, length, write_only)
            # CXP-specific attributes
            self.is_tx = is_tx
            self.page = page            # This is only needed for upper pages

    # Generic fields used by the FireFly class
    FLD_Device_Part_No = _Field_CXP(171, True, 0x00, (16*8)-1, 16*8)    # 16-byte ASCII field
    FLD_Vendor_Name = _Field_CXP(152, True, 0x00, (16*8)-1, 16*8)       # 16-byte ASCII field
    FLD_Vendor_OUI = _Field_CXP(168, True, 0x00, (3*8)-1, 3*8)          # 3-byte IEEE UID (SFF-8024)

    FLD_Tx_Temperature = _Field_CXP(22, True, 0x00, (1*8)-1, 1*8)       # Tx 2-byte temperature
    FLD_Rx_Temperature = _Field_CXP(22, False, 0x00, (1*8)-1, 1*8)      # Rx 2-byte temperature

    FLD_Tx_Channel_Disable = _Field_CXP(52, True, 0x00, 11, 12)         # Tx channel disable

    FLD_I2C_Address = _Field_CXP(255, True, 0x02, 7, 8)                 # I2C Address Select

    FLD_Page_Select = _Field_CXP(127, True, 0x00, 7, 8)                 # Page Select

    # Private interface-specific fields
    _FLG_interface_version_control = _Field_CXP(0x03, True, 0x00, 7, 8)

    def __init__(self, loggername, base_address=0x50, chosen_base_address=None, busnum=None, select_line=None):
        """
        Configure the two I2C device drivers, and set up the FireFly device to a specified address
        if requried. Also initiate use of the GPIO selection line. Note that for CXP devices, there
        are two addresses, one for Rx and one for Tx. The supplied 'base' address is for Tx.
        :param loggername:          Used to name the logger requested from the system
        :param base_address:        The address on which the FireFly Tx is expected to be found by default
        :param chosen_base_address:      The address that the Tx device will be assigned to. None for unchanged.
        :param busnum:              I2C bus number, None for default.
        :param select_line:         Optional gpiod pin for device select, will be used if provided.
        """
        # Call the super init, specifying the channel start for CXP
        super().__init__(
            channel_no_offset=0,        # Channels start at 00 for CXP
            loggername=loggername,
            base_address=base_address,
            chosen_base_address=chosen_base_address,
            busnum=busnum,
            select_line=select_line,
        )

    def _setup_interface(self, base_address, busnum, select_line):
        """
        Given an interface definition consisting of a base address, bus and select line, set up the
        class variables so that the read and write functions operate correctly.
        :param base_address:    The address that will be used for Tx
        :param busnum:          The I2C bus number to be used, None for default.
        :param select_line:     Optional select gpiod pin, active low. None for no pin.
        """
        # Check address validity
        if base_address == 0x7F:
            raise Exception('Invalid base address for CXP devices: {} (will respond to 0x50 when register set to this address)'.format(base_address))

        # CXP uses seperate 'devices' for Tx/Rx operations
        self._tx_device = I2CDevice(base_address, busnum=busnum)
        self._rx_device = I2CDevice(base_address+4, busnum=busnum)

        self._select_line = select_line
        if self._select_line is None:
            # If no selectL line is provided, it must be assumed that it is being pulled low
            # externally, or setup cannot be completed. It must also be the only device pulled low
            # on the bus.
            self._log.warning("Select Line not specified. "
                           "This MUST be the only device with selectL pulled low on the bus")

    def _change_address(self, chosen_base_address, busnum, select_line):
        """
        Change the address by directly setting the register that the FireFly module will respond to.
        For CXP devices:
            - Setting 0x00 will respond to 0x50 (selectL needed)
            - Setting 0x01 - 0x3F will resond to 0x50 or the chosen value (selectL needed)
            - Setting 0x40 - 0x7E will resond to the chosen value (selectL ignored)
        For CXP devices, the Rx address will be 4 addresses higher than the chosen base address.
        """
        # Write the chosen address (the initial interface will have already been set up)
        self.write_field(self.FLD_I2C_Address, [chosen_base_address])

        # If successful, update the interface
        if chosen_base_address in [0x00, 0x7F]:
            # Special case, setting this value will cause device to still respond to 0x50 only
            self._setup_interface(base_address=0x50, busnum=busnum, select_line=select_line)
            self._log.warning('Chosen address {} will have device respond to 0x50'.format(hex(chosen_base_address)))
        else:
            # Setup as normal
            self._setup_interface(base_address=chosen_base_address, busnum=busnum, select_line=select_line)
            self._log.warning('Reprogrammed FireFly to respond to address {}'.format(hex(chosen_base_address)))

    def write_field(self, field, value):
        """
        Calls the superclass write_field() function, but specifies the TX or RX address for I2C,
        and selects a different upper page using the lower page if necessary.
        """
        self._select_device()

        # Determine interface to use (from tx or rx)
        if field.is_tx:
            chosen_interface = self._tx_device
        else:
            chosen_interface = self._rx_device

        # Set the page using lower page, if accessing upper byte
        if (field.register >= 128):
            super(_interface_CXP, self).write_field(self.FLD_Page_Select,
                                                        [field.page], self._tx_device)

        # Call parent write field
        super(_interface_CXP, self).write_field(field, value, chosen_interface)

        self._deselect_device()

    def read_field(self, field):
        """
        Calls the superclass read_field() function, but specifies the TX or RX address for I2C,
        and selects a different upper page using the lower page if necessary.
        """
        self._select_device()

        # Determine interface to use (from tx or rx)
        if field.is_tx:
            chosen_interface = self._tx_device
        else:
            chosen_interface = self._rx_device

        # Set the page using lower page, if accessing upper byte
        if (field.register >= 128):
            super(_interface_CXP, self).write_field(self.FLD_Page_Select,
                                                        [field.page], self._tx_device)

        # Call parent read field
        read_value = super(_interface_CXP, self).read_field(field, chosen_interface)

        self._deselect_device()

        return read_value


class _interface_QSFP(_FireFly_Interface):
    """
    Class describing specifics of QSFP+-based interfaces for the FireFly.

    This includes a unique memory map and address allocation methods. The memory map is also paged
    for the upper range.
    """

    class _Field_QSFP(_Field):
        """
        Nested bit field class to access fields within the QSFP+ memory map. This includes pages.
        """
        def __init__(self, register, page, startbit, length, write_only=False):
            """
            :param register:        See _Field
            :param page:            The page number the register(s) reside in. this is only relevant
                                    for registers in the upper page (>127).
            :param startbit:        See _Field
            :param length:          See _Field
            :param write_only:      See _Field
            """
            _Field.__init__(self, register, startbit, length, write_only)
            # QSFP+ specific attributes
            self.page = page            # This is only needed for upper pages

    # Generic fields used by the FireFly class
    FLD_Device_Part_No = _Field_QSFP(168, 0x00, (16*8)-1, 16*8)         # 16-byte ASCII field
    FLD_Vendor_Name = _Field_QSFP(148, 0x00, (16*8)-1, 16*8)            # 16-byte ASCII field
    FLD_Vendor_OUI = _Field_QSFP(165, 0x00, (3*8)-1, 3*8)               # 3-byte IEEE UID (SFF-8024)

    FLD_Tx_Temperature = _Field_QSFP(22, 0x00, (1*8)-1, 1*8)        # 2-byte shared temperature
    FLD_Rx_Temperature = _Field_QSFP(22, 0x00, (1*8)-1, 1*8)        # 2-byte shared temperature

    FLD_Tx_Channel_Disable = _Field_QSFP(86, 0x00, 3, 4)            # Tx channel disable

    FLD_I2C_Address = _Field_QSFP(255, 0x02, 7, 8)                  # I2C Address Select

    FLD_Page_Select = _Field_QSFP(127, 0x00, 7, 8)                  # Page Select

    # Private interface-specific fields
    _FLG_interface_revision_compliance = _Field_QSFP(0x01, 0x00, 7, 8)

    def __init__(self, loggername, base_address=0x50, chosen_base_address=None, busnum=None, select_line=None):
        """
        Configure the two I2C device drivers, and set up the FireFly device to a specified address
        if requried. Also initiate use of the GPIO selection line.
        :param loggername:          Used to name the logger requested from the system
        :param base_address:        The address on which the FireFly is expected to be found by default
        :param chosen_base_address:      The address that the device will be assigned to. None for unchanged.
        :param busnum:              I2C bus number, None for default.
        :param select_line:         Optional gpiod pin for device select, will be used if provided.
        """
        # Call the super init, specifying the channel start for QSFP
        super().__init__(
            channel_no_offset=1,        # Channels start at 01 for QSFP
            loggername=loggername,
            base_address=base_address,
            chosen_base_address=chosen_base_address,
            busnum=busnum,
            select_line=select_line,
        )

    def _setup_interface(self, base_address, busnum, select_line):
        """
        Given an interface definition consisting of a base address, bus and select line, set up the
        class variables so that the read and write functions operate correctly.
        :param base_address:    The address that will be used for Tx and Rx
        :param busnum:          The I2C bus number to be used, None for default.
        :param select_line:     Optional select gpiod pin, active low. None for no pin.
        """
        # Check address validity
        if base_address in range(0x7f, 0xFF+1):
            raise Exception('Invalid base address for QSFP devices: {} (addresses in this range will respond to 0x50)'.format(base_address))

        # QSFP uses one device for Tx/Rx operations
        self._device = I2CDevice(base_address, busnum=busnum)

        self._select_line = select_line
        if self._select_line is None:
            # If no selectL line is provided, it must be assumed that it is being pulled low
            # externally, or setup cannot be completed. It must also be the only device pulled low
            # on the bus.
            self._log.warning("Select Line not specified. "
                           "This MUST be the only device with selectL pulled low on the bus")

    def _change_address(self, chosen_base_address, busnum, select_line):
        """
        Change the address by directly setting the register that the FireFly module will respond to.
        For QSFP devices:
            - Setting 0x00, 0x7F - 0xFF     will respond to 0x50 and 0x00 (selectL needed)
            - Setting 0x01 - 0x7E           will resond to chosen value and 0x00 (selectL needed)
        """
        # Write the chosen address (the initial interface will have already been set up)
        self.write_field(self.FLD_I2C_Address, [chosen_base_address])

        # If successful, update the interface
        if chosen_base_address == 0x00 or chosen_base_address in range(0x7F,0xFF+1):
            # Setting anything in this range will result in the device only responding to address
            # 0x50 anyway, so set the field but warn the user, and set up the interface to use 0x50
            self._setup_interface(base_address=0x50, busnum=busnum, select_line=select_line)
            self._log.warning('Chosen address {} will have device respond to 0x50'.format(hex(chosen_base_address)))
        else:
            # Set up as normal to respond to the requested address
            self._setup_interface(base_address=chosen_base_address, busnum=busnum, select_line=select_line)
            self._log.warning('Reprogrammed FireFly to respond to address {}'.format(hex(chosen_base_address)))

    def write_field(self, field, value):
        """
        Calls the superclass write_field() function, but selects a different upper page using the
        lower page if necessary.
        """
        self._select_device()

        # Set the page using lower page, if accessing upper byte
        if (field.register >= 128):
            super(_interface_QSFP, self).write_field(self.FLD_Page_Select, [field.page], self._device)

        # Call parent write field
        super(_interface_QSFP, self).write_field(field, value, self._device)

        self._deselect_device()

    def read_field(self, field):
        """
        Calls the superclass read_field() function, but selects a different upper page using the
        lower page if necessary.
        """
        self._select_device()

        # Set the page using lower page, if accessing upper byte
        if (field.register >= 128):
            super(_interface_QSFP, self).write_field(self.FLD_Page_Select, [field.page], self._device)

        # Call parent read field
        read_value = super(_interface_QSFP, self).read_field(field, self._device)

        self._deselect_device()

        return read_value
