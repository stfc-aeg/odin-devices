"""
DS110F410 - device access class for the DS110F410 Quad Channel Retimer

TODO

Joseph Nobes, STFC Detector Systems Software Group
"""

from odin_devices.i2c_device import I2CDevice, I2CException
import logging

logger = logging.getLogger('odin_devices.ds110f410')


class _Field:
    """
    Field Class:
    Used to address specific bit fields within 8-bit register addresses for the device. This means
    the function of the fields are kept abstract from the physical register location.

    The DS110 has register IDs that overlap for 'control/shared' and 'channel' registers. Given
    that this is a field property, it is appears in the class as register_group.
    """
    def __init__(self, register, register_group, startbit, length):
        self.register = register
        self.register_group = register_group
        self.startbit = startbit
        self.length = length

    def get_endbit(self):
        return (self.startbit - (self.length - 1))


class DS110F410(I2CDevice):

    # Channel/shared register group selection
    _REG_GROUP_Shared = 1
    _REG_GROUP_Channel = 0
    CHANNEL_0 = 0
    CHANNEL_1 = 1
    CHANNEL_2 = 2
    CHANNEL_3 = 3
    CHANNEL_All = 4     # Applies to write only
    _REG_GROUP_SELECTED = _REG_GROUP_Channel        # By default shared register write is off
    _REG_CHANNEL_SELECTED = CHANNEL_0               # By default channel 0 is selected

    # System reset signals
    RST_CORE    = 0b1000
    RST_REGS    = 0b0100
    RST_REFCLK  = 0b0010
    RST_VCO     = 0b0001
    RST_ALL     = 0b1111

    # Register Fields
    _FIELD_Channel_Reset = _Field(0x00, _REG_GROUP_Channel, 3, 4)   # Combined channel reset bits

    def __init__(self, address=0x18, **kwargs):
        """
        Initialise the DS110F410 device.

        :param address: The address of the DS110F410 is determined by pins ADDR_[3:0] as follows:
                        0x18 + 0b[A3][A2][A1][A0].
        """
        I2CDevice.__init__(self, address, **kwargs)
        logger.info("Created new ds110f410 instance with address 0x{:02X}.".format(address))

        self.reset(CHANNEL_All, RST_ALL)        # Get all channels in known reset state

    """
    Utility Functions:
    """
    @staticmethod
    def pins_to_address(A3,A2,A1,A0):
        """
        Return value of address that self.will be used by the device based on the
        address pin states ADDR_[3:0]. Arguments should be supplied as 1/0.
        """
        if not all(pin in [0,1] for pin in [A3,A2,A1,A0]):     # Check pins are 1 or 0
            raise I2CException("Pins should be specified as 1 or 0")
        return (0x18 + ((A3 << 3) | (A2 << 2) | (A1 << 1) | A0))

    """
    Register and Field Access Functions:
    """
    def _reg_ch_sel(register_group, register_channel):
        """
        Sets the 0xFF channel select register to reflect a single channel if it is being used, as
        well as setting the WRITE_ALL_CH bit if all channels are being written. The EN_CH_SMB bit
        is always set to ensure that channel access is enabled.

        :param register_group: Register group to use. _REG_GROUP_Shared to set a shared control
                                register, or _REG_GROUP_Channel to target only a channel (or all
                                channels), specified below.
        :param register_channel:    Channel written to if _REG_GROUP_Channel is selected.
        """
        if register_group == _REG_GROUP_Shared:
            self.write8(0xFF, 0b0000)       # WRITE_ALL_CH = 0, EN_CH_SMB = 0, CH_SEL = 0
        elif register_group == _REG_GROUP_Channel:
            if register_channel in [CHANNEL_0, CHANNEL_1, CHANNEL_2, CHANNEL_3]:
                self.write8(0xFF,
                            0b0100 |                # WRITE_ALL_CH = 0, EN_CH_SMB = 1
                            (register_channel))
            elif register_channel == CHANNEL_All:
                self.write8(0xFF,
                            0b1100 |                # WRITE_ALL_CH = 1, EN_CH_SMB = 1
                            (register_channel))
            else:
                raise I2CException("Invalid register channel."
                                   " Select CHANNEL_0-CHANNEL3 or CHANNEL_All.")
        else:
            raise I2CExcecption("Invalid register group."
                                " Select _REG_GROUP_Channel or _REG_GROUP_Shared.")

    def _write_register(register_group, register_channel=CHANNEL_All, register, value):
        """
        Wrapper for the I2CDevice write8 function.
        Ensures that the correct register group is specified for writes, and avoids unnecessary
        transmissions setting the group each time if it is already correct.

        If the register_group is set as _REG_GROUP_Shared, the channel is irrelevant.

        :param register_group: Register group to use. _REG_GROUP_Shared to set a shared control
                                register, or _REG_GROUP_Channel to target only a channel (or all
                                channels), specified below.
        :param register_channel:    Channel written to if _REG_GROUP_Channel is selected.
        :param register: Register ID to be written
        :param value: Value to be written
        """
        if ((register_group != self._REG_GROUP_SELECTED) or
            (register_channel != self._REG_CHANNEL_SELECTED)):
            _reg_ch_sel(register_group, register_channel)
        self.write8(register, value)

    def _read_register(register_group, register):
        """
        Wrapper for the I2CDevice readU8 function.
        Ensures that the correct register group is specified for reads, and avoids unnecessary
        transmissions setting the group each time if it is already correct.

        :param register_group: Register group to use. _REG_GROUP_Shared to set a shared control
                                register, or _REG_GROUP_Channel to target only a channel (or all
                                channels), specified below.
        :param register_channel:    Channel written to if _REG_GROUP_Channel is selected.
        :param register: Register ID to be read
        :return: Value read from the register
        """
        if ((register_group != self._REG_GROUP_SELECTED) or
            (register_channel != self._REG_CHANNEL_SELECTED)):
            _reg_ch_sel(register_group, register_channel)
        return self.readU8(register)

    def _write_field(field, channel=CHANNEL_All, value, verify=False):
        """
        Write a field of <=8 bits into an 8-bit register.
        Field bits are masked to preserve other settings held within the same register.

        Some registers for this device are 'ICAL sensitive', meaning that a calibration
        procedure must be run if they are changed. This is handled automatically unless
        otherwise specified.

        :param field: _Field instance holding relevant register and location of field bits
        :param channel: If the field specified requires a channel selection, supply here.
        :param value: Unsigned byte holding unshifted value to be written to the field
        :param verify: Boolean. If true, read values back to verify correct writing.
        """
        logger.debug("Writing value {} to field {}-{} in register {}".format(
            value,field.startbit,field.get_endbit(),field.register)) #TODO update logging

        # warn about channel selection
        if field.register_group == _REG_GROUP_Shared:
            if channel != CHANNEL_All:
                logger.warning(
                        "Field is shared, but channel specified. Channel will be ignored.")
        elif field.register_group == _REG_GROUP_Channel:
            if channel == CHANNEL_ALL:
                logger.warning(
                        "Channel set to -or defaulting to- ALL channels.")

        # check input fits in specified field
        if (1 << (field.length)) <= value:
            raise I2CException(
                    "Value {} does not fit in specified field of length {}.".format(
                        value, field.length))

        old_value = self._read_register(field.register_group, channel, field.register)
        new_msk = (0xff >> (8-field.length)) << field.get_endbit()
        logger.debug("Register {}: field start: {}, field end: {} -> mask {:b}".format(
            field.register,field.startbit,field.get_endbit(), new_msk))
        new_value = (old_value & ~new_msk) | (value << field.get_endbit())
        logger.debug("Register {}: {:b} -> {:b}".format(field.register, old_value, new_value))
        if new_value != old_value:
            self._write_register(field.register_group, channel, field.register, new_value)

        if verify:
            verify_value = self._read_field(field, channel)
            logger.debug("Verifying value written ({:b}) against re-read: {:b}".format(
                value,verify_value))
            if verify_value != value:
                raise I2CException(
                        "Value {} was not successfully written to Field {}".format(
                            value, field))

    def _read_field(field, channel=CHANNEL_All):
        """
        Read only the field-specific bits from the relevant register

        :param register_group: Register group to use. REG_GROUP_Shared to set all registers, or
                                REG_GROUP_Chx to access a particlar channel.
        :param field: _Field instance holding relevant register and location of field bits
        """
        logger.debug("Getting field starting at bit {}, length {} from register {}".format(
            field.startbit,field.length,field.register)) #TODO update to include channels

        # Generate warnings / exception for incorrect reg group/channel combination
        if ((field.register_group == _REG_GROUP_Shared) and
            (channel in [CHANNEL_0, CHANNEL_1, CHANNEL_2, CHANNEL_3])):
            logger.warning(
                    "Field is a shared / control register but channel was specified, ignoring...")
        elif ((field.register_group == _REG_GROUP_Channel) and
              (channel == CHANNEL_All)):
            raise I2CException(
                    "Field read requires a specific channel, plesase specify CHANNEL_0-3.")

        raw_register_value = self._read_register(field.register_group, channel, field.register)
        logger.debug("Raw value: {0:b}".format(raw_register_value))

        # remove high bits
        value = raw_register_value & (0xFF >> (7-field.startbit))
        logger.debug("high bits removed: {0:b}".format(value))

        # shift value to position 0
        value = value >> field.get_endbit()
        logger.debug("Low bits removed: {0:b}".format(value))
        return value

    """
    Device Action Functions:
    """
    def reset(channel, selection=[RST_ALL]):
        """
        Resets entire device or only sections of it for a given channel.
        Either specify ALL, or supply a list of other chosen RESET_X devices.
        Reset bits are self-clearing.

        :param channel:     Channel to reset. Specify CHANNEL_0-3 or CHANNEL_All.
        :param selection:   A list containing systems to reset. No argument or a list containing
                            RST_ALL will reset all systems. Others: RST_CORE, RST_REGS, RST_REFCLK,
                            RST_VCO
        """
        if type(selection) != list:
            raise I2CException(
                    "Argument supplied was not a list")
        if RST_ALL in selection:
            # There is no point in checking other values
            _write_field(_FIELD_Channel_Reset, channel, RST_ALL)
        else:
            # OR values to combine into single reset write
            rst_combined = 0
            for rst_bit in selection:
                if rst_bit in [RST_CORE, RST_REGS, RST_REFCLK, RST_VCO]:
                    rst_combined |= rst_bit
                else:
                    raise I2CException(
                            "Incorrect reset sigal supplied. List items may only be:"
                            " RST_CORE, RST_REGS, RST_REFCLK, RST_VCO")
            _write_field(_FIELD_Channel_Reset, channel, rst_combined)
