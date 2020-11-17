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

    Some registers are write_only (e.g. reset triggers), so the normal process of reading current
    register values to replace some and write back will not work. Therefore these fields are marked
    with 'write_only=True' to ensure the field writing function does not read previous reg state.
    """
    def __init__(self, register, register_group, startbit, length, write_only=False):
        self.register = register
        self.register_group = register_group
        self.startbit = startbit
        self.length = length
        self.write_only = write_only

    def get_endbit(self):
        return (self.startbit - (self.length - 1))


class DS110F410(I2CDevice):

    # Channel/shared register group selection
    _REG_GRP_Shared = 1
    _REG_GRP_Channel = 0

    _CHANNEL_0      = 0
    _CHANNEL_1      = 1
    _CHANNEL_2      = 2
    _CHANNEL_3      = 3
    _CHANNEL_All    = 4         # Applies to write only

    # System reset signals
    RST_CORE    = 0b1000
    RST_REGS    = 0b0100
    RST_REFCLK  = 0b0010
    RST_VCO     = 0b0001
    RST_ALL     = 0b1111

    # Register Fields (Channel)
    _FIELD_Chn_Reset = _Field(0x00, _REG_GRP_Channel, 3, 4)         # Combined channel reset bits

    _FIELD_Chn_CDR_LL_INT = _Field(0x01, _REG_GRP_Channel, 4, 1)    # CDR Lock Loss Interrupt
    _FIELD_Chn_SIG_DET_LOSS_INT = _Field(0x01, _REG_GRP_Channel, 0, 1)  # SD Loss Interrupt

    _FIELD_Chn_Status = _Field(0x02, _REG_GRP_Channel, 7, 8)        # Channel status full byte

    _FIELD_Chn_EOM_VR_Lim_Err = _Field(0x30, _REG_GRP_Channel, 5, 1)
    _FIELD_Chn_HEO_VEO_INT = _Field(0x30, _REG_GRP_Channel, 4, 1)       # Cleared on read

    # Register Fields (Shared / Control)
    _FIELD_Shr_Reset = _Field(0x04, _REG_GRP_Shared, 6, 1)

    def __init__(self, address=0x18, **kwargs):
        """
        Initialise the DS110F410 device.

        :param address: The address of the DS110F410 is determined by pins ADDR_[3:0] as follows:
                        0x18 + 0b[A3][A2][A1][A0].
        """
        I2CDevice.__init__(self, address, **kwargs)
        logger.info("Created new ds110f410 instance with address 0x{:02X}.".format(address))

        # Set up channels
        self.channel_0 = _Channel(self, self._CHANNEL_0)
        self.channel_1 = _Channel(self, self._CHANNEL_1)
        self.channel_2 = _Channel(self, self._CHANNEL_2)
        self.channel_3 = _Channel(self, self._CHANNEL_3)
        self.channel_all = _Channel(self, self._CHANNEL_All)
        self.channel_all.reset(RST_ALL)         # Get all channels in known reset state

        # Set up register access current state
        self._REG_GRP_SELECTED = _REG_GRP_Channel       # By default shared register write is off
        self._REG_CHANNEL_SELECTED = _CHANNEL_0         # By default channel 0 is selected

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

        :param register_group: Register group to use. _REG_GRP_Shared to set a shared control
                                register, or _REG_GRP_Channel to target only a channel (or all
                                channels), specified below.
        :param register_channel:    Channel written to if _REG_GRP_Channel is selected.
        """
        if register_group == _REG_GRP_Shared:
            self.write8(0xFF, 0b0000)       # WRITE_ALL_CH = 0, EN_CH_SMB = 0, CH_SEL = 0
        elif register_group == _REG_GRP_Channel:
            if register_channel in [self._CHANNEL_0,
                                    self._CHANNEL_1,
                                    self._CHANNEL_2,
                                    self._CHANNEL_3]:
                self.write8(0xFF,
                            0b0100 |                # WRITE_ALL_CH = 0, EN_CH_SMB = 1
                            (register_channel))
            elif register_channel == self._CHANNEL_All:
                self.write8(0xFF,
                            0b1100 |                # WRITE_ALL_CH = 1, EN_CH_SMB = 1
                            (register_channel))
            else:
                raise I2CException("Invalid register channel."
                                   " Select self._CHANNEL_0-CHANNEL3 or self._CHANNEL_All.")
        else:
            raise I2CExcecption("Invalid register group."
                                " Select _REG_GRP_Channel or _REG_GRP_Shared.")

    def _write_register(register_group, register_channel=self._CHANNEL_All, register, value):
        """
        Wrapper for the I2CDevice write8 function.
        Ensures that the correct register group is specified for writes, and avoids unnecessary
        transmissions setting the group each time if it is already correct.

        If the register_group is set as _REG_GRP_Shared, the channel is irrelevant.

        :param register_group: Register group to use. _REG_GRP_Shared to set a shared control
                                register, or _REG_GRP_Channel to target only a channel (or all
                                channels), specified below.
        :param register_channel:    Channel written to if _REG_GRP_Channel is selected.
        :param register: Register ID to be written
        :param value: Value to be written
        """
        if ((register_group != self._REG_GRP_SELECTED) or
            (register_channel != self._REG_CHANNEL_SELECTED)):
            _reg_ch_sel(register_group, register_channel)
        self.write8(register, value)

    def _read_register(register_group, register):
        """
        Wrapper for the I2CDevice readU8 function.
        Ensures that the correct register group is specified for reads, and avoids unnecessary
        transmissions setting the group each time if it is already correct.

        :param register_group: Register group to use. _REG_GRP_Shared to set a shared control
                                register, or _REG_GRP_Channel to target only a channel (or all
                                channels), specified below.
        :param register_channel:    Channel written to if _REG_GRP_Channel is selected.
        :param register: Register ID to be read
        :return: Value read from the register
        """
        if ((register_group != self._REG_GRP_SELECTED) or
            (register_channel != self._REG_CHANNEL_SELECTED)):
            _reg_ch_sel(register_group, register_channel)
        return self.readU8(register)

    def _write_field(field, channel=self._CHANNEL_All, value, verify=False):
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
        if field.register_group == _REG_GRP_Shared:
            if channel != self._CHANNEL_All:
                logger.warning(
                        "Field is shared, but channel specified. Channel will be ignored.")
        elif field.register_group == _REG_GRP_Channel:
            if channel == CHANNEL_ALL:
                logger.warning(
                        "Channel set to -or defaulting to- ALL channels.")

        # check input fits in specified field
        if (1 << (field.length)) <= value:
            raise I2CException(
                    "Value {} does not fit in specified field of length {}.".format(
                        value, field.length))

        if (field.write_only):
            old_value = 0x00
        else:
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

    def _read_field(field, channel=self._CHANNEL_All):
        """
        Read only the field-specific bits from the relevant register

        :param register_group: Register group to use. REG_GROUP_Shared to set all registers, or
                                REG_GROUP_Chx to access a particlar channel.
        :param field: _Field instance holding relevant register and location of field bits
        """
        logger.debug("Getting field starting at bit {}, length {} from register {}".format(
            field.startbit,field.length,field.register)) #TODO update to include channels

        # Generate warnings / exception for incorrect reg group/channel combination
        if ((field.register_group == _REG_GRP_Shared) and
            (channel in [self._CHANNEL_0, self._CHANNEL_1, self._CHANNEL_2, self._CHANNEL_3])):
            logger.warning(
                    "Field is a shared / control register but channel was specified, ignoring...")
        elif ((field.register_group == _REG_GRP_Channel) and
              (channel == self._CHANNEL_All)):
            raise I2CException(
                    "Field read requires a specific channel, plesase specify self._CHANNEL_0-3.")

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
    def reset(reset_channel_registers=True):
        if (reset_channel_registers):
            self.channel_all.reset(RST_ALL)                 # Full Reset all channels
        _write_field(DS110F410._FIELD_Shr_Reset, 0b1)    # Reset shared / control registers


    class _Channel:

        def __init__(self, ds110_instance, channel_id):
            self.CID = channel_id
            self._ds110 = ds110_instance

        def get_status(self):
            # Taken from Thomas' version and adapted
            print ' Reset Reg: ' + hex(self._read_field(DS110F410._FIELD_Chn_Reset, self.CID))

            tmp = self.ds110._read_field(DS110F410._FIELD_Chn_CDR_LL_INT, self.CID)
            print 'CDR LOCK LOSS INT: ' + str(tmp)
            tmp = self.ds110._read_field(DS110F410._FIELD_Chn_SIG_DET_LOSS_INT, self.CID)
            print 'CDR LOCK LOSS INT: ' + str(tmp)

            tmp = self.ds110._read_field(_FIELD_Chn_EOM_VR_Lim_Err, self.CID)
            print 'EOM VRANGE LIMIT ERROR: ' + str(tmp)
            tmp = self.ds110._read_field(_FIELD_Chn_HEO_VEO_INT, self.CID)
            print 'HEO VEO INT: ' + str(tmp)

            tmp = self.ds110._read_field(_FIELD_Chn_Status, self.CID)
            print hex(tmp)
            if (tmp & 0b10000000): print 'Comp LPF Low'
            if (tmp & 0b01000000): print 'Comp LPF High'
            if (tmp & 0b00100000): print 'Single Bit Limit Reached'
            if (tmp & 0b00010000): print 'CDR Lock'
            if (tmp & 0b00001000): print 'LOCK'
            if (tmp & 0b00000100): print 'Fail Lock Check'
            if (tmp & 0b00000010): print 'Auto Adapt Complete'
            if (tmp & 0b00000011): print 'PPM Count Met'

            heo = self.ds110._read_field(_FIELD_Chn_HEO_Val, self.CID)
            veo = self.ds110._read_field(_FIELD_Chn_VEO_Val, seld.CID)
            print 'HEO ' + str(heo)
            print 'VEO ' + str(veo)

        def reset(self, selection=[RST_ALL]):
            """
            Resets entire device or only sections of it for a given channel.
            Either specify ALL, or supply a list of other chosen RESET_X devices.
            Reset bits are self-clearing.

            :param channel:     Channel to reset. Specify self._CHANNEL_0-3 or self._CHANNEL_All.
            :param selection:   A list containing systems to reset. No argument or a list containing
                                RST_ALL will reset all systems. Others: RST_CORE, RST_REGS, RST_REFCLK,
                                RST_VCO
            """
            if type(selection) != list:
                raise I2CException(
                        "Argument supplied was not a list")
            if RST_ALL in selection:
                # There is no point in checking other values
                self._ds110._write_field(ds110f410._field_channel_reset, self.cid, rst_all)
            else:
                # or values to combine into single reset write
                rst_combined = 0
                for rst_bit in selection:
                    if rst_bit in [rst_core, rst_regs, rst_refclk, rst_vco]:
                        rst_combined |= rst_bit
                    else:
                        raise i2cexception(
                                "incorrect reset sigal supplied. list items may only be:"
                                " rst_core, rst_regs, rst_refclk, rst_vco")
                self._ds110._write_field(ds110f410._field_channel_reset, self.cid, rst_combined)


