from odin_devices.i2c_device import I2CDevice, I2CException
import smbus
import math
import logging
import time

logger = logging.getLogger('odin_devices.FireFly')

_GPIO_AVAIL = True
try:
    import odin_devices.gpio_bus
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


class FireFly:
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

    def __init__(self, base_address = 0x00, select_line = None):
        """
        Create an instance of a generic FireFly device. The interface type will be determined
        automatically, as will the number of channels. Devices are assumed to be in POR, and at
        address 0x50 by default on instantiation, but can be supplied an alternative address to
        switch to. Select lines are also supported, but if ignored it is assumed that the device
        is the only one present on the bus and has its select line pulled low.

        :param base_address:    Address that will be set for future communication. Omit for default
        :param select_line:     GPIO line to use for active-low chip select, if used. This should be
                                a line provided by odin_devices.gpio_bus or directly via gpiod.
        """

        # Init logger for instance (likely to have multiple fireflies)
        loggername = FireFly._LOGGER_BASENAME + ('@0x%02x'%base_address)
        self._log = logging.getLogger(loggername)
        self._log.info("Init FireFly with base address 0x%02x" % base_address)

        INTERFACE_Detect = FireFly._get_interface(select_line, 0x50, self._log)

        if INTERFACE_Detect == FireFly.INTERFACE_QSFP:
            self._interface = _interface_QSFP(loggername+".QSFP+", base_address, select_line)
            self._log.info("Interface detected as QSFP+ based")
        elif INTERFACE_Detect == FireFly.INTERFACE_CXP:
            self._interface = _interface_CXP(loggername+".CXP", base_address, select_line)
            self._log.info("Interface detected as CXP based")
        else:
            raise I2CException("Unsupported SFF interface class: {}".format(SFF_identifier))

        # From here onwards, interface and address specific functions can be called through
        # self._interface.???(), and address, register and select line usage will be handled.

        # Read some identifying information
        PN_ascii, VN_ascii, OUI = self.get_device_info()
        self._check_pn_fields(PN_ascii)
        self._log.info(
                "Found device, Vendor: {} ({}),\tPN: {}".format(VN_ascii, OUI, PN_ascii))

        # Turn off all Tx channels initially to prevent overheat
        self.disable_tx_channels(FireFly.CHANNEL_ALL)

        temp_tx = self.get_temperature(FireFly.DIRECTION_TX)
        self._log.info("Tx Temperature: {}".format(temp_tx))

    @staticmethod
    def _get_interface(select_line, default_address, log_instance=None):
        # Assuming the device is currently on the default address, and OUI is 0x40C880
        tempdevice = I2CDevice(default_address)

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
        print(cxp_oui, qsfp_oui)

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
            # Given that Samtec does not 'officially' support the OUI field for 4 channel devices,
            # it is possible it would not be present. In that case, we assume QSFP is being used.
            if log_instance is not None:
                log_instance.warning("OUI not found, but assuming QSFP device is present")
            return FireFly.INTERFACE_QSFP

    def _check_pn_fields(self, pn_str):
        """
        Checks some common fields accross all common devices to make sure the PN has been read
        correctly. Some fields important to the driver's operation are designated as CRITICAL, and
        will trigger an exception if failed. Others designated with WARNING will simply show a
        warning if the value is not recognised.

        This function also populates some fields used by the driver, like number of channels, data
        direction and data rate.

        :param pn_str:  String of unformatted Part number (without ECU0 prefix)
        """

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

        if direction == FireFly.DIRECTION_TX:
            temperature_bytes = self._interface.read_field(self._interface.FLD_Tx_Temperature)
        elif direction == FireFly.DIRECTION_RX:
            temperature_bytes = self._interface.read_field(self._interface.FLD_Tx_Temperature)
        else:
            raise I2CException("Invalid direction specified, and could not be derived")

        if len(temperature_bytes) != 2:
            raise I2CException("Failed to read temperature")

        output_temp = temperature_bytes[0] + temperature_bytes[1] * (float(1) / float(256))
        return output_temp

    def disable_tx_channels(self, channels_combined):
        """
        Generic function to disable a specified selection of transmitter channels, with chosen
        channels ORed together as a bitfield. Alternatively, CHANNEL_ALL can be passed to disable
        all device channels.

            e.g. disable_tx_channels(CHANNEL_00 | CHANNEL_01 | CHANNEL_05)

        :param channels_combined:   ORed channels: CHANNEL_<00-11> or CHANNEL_ALL
        """

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

    def _get_disabled_tx_channels_field(self):
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
        output_value << self._interface.channel_no_offset

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

class _Field:
    """
    Class capable of storing data to encode fields that span multiple bytes or only segments of a
    few bits within a byte. Note that 'length' is in bits.
    """
    def __init__(self, register, startbit, length, write_only=False):
        self.register = register
        self.startbit = startbit
        self.length = length
        self.write_only = write_only

    def get_endbit(self):
        return (self.startbit - (self.length - 1))


class _FireFly_Interface:
    """
    Generic class to be extended by alternative interfaces (and memory maps) for the FireFly.
    Currently this supports automatic detection and interaction with devices that report compliance
    with CXP and QSFP+.

    Interfaces should contain the same public access methods and public attributes (mainly the FLD
    register field definitions) so that externally they behave the same as treated by the main
    FireFly instance, which will have ownership of one type of interface (detected automatically).
    """

    def __init__(self, SFF_ID, channel_no_offset, loggername):
        self.SFF_ID = SFF_ID
        self.channel_no_offset = channel_no_offset
        self._log = logging.getLogger(loggername)

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
        num_full_bytes = math.ceil((field.length + field.get_endbit()) / float(8))
        raw_register_values = i2c_device.readList(field.register, num_full_bytes)

        # Check resulting I2C read format and length
        if (type(raw_register_values) != list):
                raise I2CException("Failed to read byte list from I2C Device")
        if (len(raw_register_values) != num_full_bytes):
                raise I2CException("Number of bytes read incorrect. "
                    "Expected {}, got {}".format(len(raw_register_values), num_full_bytes))

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

        return _int_to_array(out_value, num_full_bytes)

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

        # Read old value, align with register bytes, with superclass
        old_values = super(type(self), self).read_field(field, i2c_device)
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
        num_full_bytes = math.ceil((field.length + field.get_endbit()) / float(8))
        new_value_array = _int_to_array(new_value, num_full_bytes)
        i2c_device.writeList(field.register, new_value_array)   # Perform write
        self._log.debug("\tWrite list: {}".format(new_value_array))

        # Verify
        if verify:
            verify_value = self.read_field(field, i2c_device)
            self._log.debug("Verifying value written ({:b}) against re-read: {:b}".format(
                value,verify_value))
            if verify_value != value:
                raise I2CException(
                        "Value {} was not successfully written to Field {}".format(
                            value, field))

        time.sleep(0.040)       # Write operations (especially upper02) should be separated by 40ms


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
            _Field.__init__(self, register, startbit, length, write_only)
            # CXP-specific attributes
            self.is_tx = is_tx
            self.page = page            # This is only needed for upper pages

    # Generic fields used by the FireFly class
    FLD_Device_Part_No = _Field_CXP(171, True, 0x00, (16*8)-1, 16*8)    # 16-byte ASCII field
    FLD_Vendor_Name = _Field_CXP(152, True, 0x00, (16*8)-1, 16*8)       # 16-byte ASCII field
    FLD_Vendor_OUI = _Field_CXP(168, True, 0x00, (3*8)-1, 3*8)          # 3-byte IEEE UID (SFF-8024)

    FLD_Tx_Temperature = _Field_CXP(22, True, 0x00, (2*8)-1, 2*8)       # Tx 2-byte temperature
    FLD_Rx_Temperature = _Field_CXP(22, False, 0x00, (2*8)-1, 2*8)      # Rx 2-byte temperature

    FLD_Tx_Channel_Disable = _Field_CXP(52, True, 0x00, 11, 12)         # Tx channel disable

    FLD_I2C_Address = _Field_CXP(255, True, 0x02, 7, 8)                 # I2C Address Select

    FLD_Page_Select = _Field_CXP(127, True, 0x00, 7, 8)                 # Page Select

    # Private interface-specific fields
    _FLG_interface_version_control = _Field_CXP(0x03, True, 0x00, 7, 8)

    def __init__(self, loggername, base_address = 0x00, select_line = None):
        """
        Configure the two I2C device drivers, and set up the FireFly device to a specified address
        if requried. Also initiate use of the GPIO selection line.
        """
        _FireFly_Interface.__init__(self, None,     # TODO Currently unknown SFF ID (vendor)
                                    0, loggername)      # Channels start at 00

        # Set up select line use for the given address
        self._select_line = select_line
        if base_address == None:
            base_address = 0x00 # Default
        self._base_address = base_address
        self._init_select(base_address)     # May modify _base_address

        # CXP uses seperate 'devices' for Tx/Rx operations
        self._tx_device = I2CDevice(base_address)
        self._rx_device = I2CDevice(base_address + 4)

    def _init_select(self, chosen_address):
        """
        Set up the FireFly to respond on a chosen address, and to use the select line correctly
        when when the _select_device() functions are used.
        """
        # Set up device to respond on chosen address with _select_device() functions
        if self._select_line is None:
            # If no selectL line is provided, it must be assumed that it is being pulled low
            # externally, or setup cannot be completed. It must also be the only device pulled low
            # on the bus.
            self._log.warning("Select Line not specified. "
                           "This MUST be the only device with selectL pulled low on the bus")

        # Apply extra address-specific measures
        if chosen_address in [0x00, 0x7F]:
            # Revert to default behaviour, where address is 0x50 when selectL pulled low
            self._base_address = 0x50
            return

        if 0x40 < chosen_address < 0x7E and chosen_address is not 0x50:
            # Addresses in this range will ignore selectL, so disable it (if not already None)
            # Note that 0x50 is a special case as the default, since it is responded to with
            # address register set to 0x00, and so not in this range...
            self._select_line = None

        # Write address field with initial settings for select line
        self._tx_device = I2CDevice(0x50)   # Temporarily assign the tx_device to default address
        self.write_field(self.FLD_I2C_Address, [chosen_address])
        self._tx_device = None              # Will be properly assigned later

    def _select_device(self):
        if self._select_line is not None:
            # pull select line low
            self._select_line.set_value(0)

    def _deselect_device(self):
        if self._select_line is not None:
            # pull select line high
            self._select_line.set_value(1)

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
            _Field.__init__(self, register, startbit, length, write_only)
            # QSFP+ specific attributes
            self.page = page            # This is only needed for upper pages

    # Generic fields used by the FireFly class
    FLD_Device_Part_No = _Field_QSFP(168, 0x00, (16*8)-1, 16*8)         # 16-byte ASCII field
    FLD_Vendor_Name = _Field_QSFP(148, 0x00, (16*8)-1, 16*8)            # 16-byte ASCII field
    FLD_Vendor_OUI = _Field_QSFP(165, 0x00, (3*8)-1, 3*8)               # 3-byte IEEE UID (SFF-8024)

    FLD_Tx_Temperature = _Field_QSFP(22, 0x00, (2*8)-1, 2*8)        # 2-byte shared temperature
    FLD_Rx_Temperature = _Field_QSFP(22, 0x00, (2*8)-1, 2*8)        # 2-byte shared temperature

    FLD_Tx_Channel_Disable = _Field_QSFP(86, 0x00, 3, 4)            # Tx channel disable

    FLD_I2C_Address = _Field_QSFP(255, 0x02, 7, 8)                  # I2C Address Select

    FLD_Page_Select = _Field_QSFP(127, 0x00, 7, 8)                  # Page Select

    # Private interface-specific fields
    _FLG_interface_revision_compliance = _Field_QSFP(0x01, 0x00, 7, 8)

    def __init__(self, loggername, address = 0x00, select_line = None):
        """
        Configure the two I2C device drivers, and set up the FireFly device to a specified address
        if requried. Also initiate use of the GPIO selection line.
        """
        _FireFly_Interface.__init__(self, 0x81,     # Vendor-specific QSFP+
                                    1, loggername)      # Channels start at 1 for some reason...

        # Set up select line use for the given address
        self._select_line = select_line
        if address == None:
            address = 0x00      # Default
        self._address = address
        self._init_select(address)          # May modify _address

        self._device = I2CDevice(address)
        self._device.enable_exceptions()#TODO remove

    def _init_select(self, chosen_address):
        """
        Set up the FireFly to respond on a chosen address, and to use the select line correctly
        when when the _select_device() functions are used.
        """
        # Set up device to respond on chosen address with _select_device() functions
        if self._select_line is None:
            # If no selectL line is provided, it must be assumed that it is being pulled low
            # externally, or setup cannot be completed. It must also be the only device pulled low
            # on the bus.
            self._log.warning("Select Line not specified. "
                           "This MUST be the only device with selectL pulled low on the bus")

        if chosen_address == 0x00:
            # This is the rest value, and the device is assumed to be reset when this is run.
            return

        # Apply extra address-specific measures
        if chosen_address == 0x00 or 0x7F < chosen_address < 0xFF:
            # Revert to default behaviour, where address is 0x50 when selectL pulled low
            self._log.warning("Device will be responding to 0x50, not {}".format(chosen_address))
            self._base_address = 0x50
            return

        # Write address field with initial settings for select line
        self._device = I2CDevice(0x50)   # Temporarily assign the tx_device to default address
        self.write_field(self.FLD_I2C_Address, [chosen_address])
        self._device = None              # Will be properly assigned later
        # Otherwise chosen address will be used when selectL pulled low

    def _select_device(self):
        if self._select_line is not None:
            # pull select line low
            self._select_line.set_value(0)

    def _deselect_device(self):
        if self._select_line is not None:
            # pull select line high
            self._select_line.set_value(1)

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
