"""
DS110DF410 - device access class for the DS110DF410 Quad Channel Retimer.

Joseph Nobes, STFC Detector Systems Software Group
"""
from odin_devices.i2c_device import I2CDevice, I2CException
import logging
import math
import time
import numpy as np

logger = logging.getLogger('odin_devices.ds110df410')


class _Field:
    """Used to address specific bit fields within 8-bit register addresses for the device.

    This means the function of the fields are kept abstract from the physical register location.

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


_CHANNEL_0 = 0
_CHANNEL_1 = 1
_CHANNEL_2 = 2
_CHANNEL_3 = 3
_CHANNEL_All = 4         # Applies to write only

# Encoding for output driver de-emphasis values
_De_Emphasis_Value_Map = {
    0.0: 0b0000,
    -0.9: 0b0011,
    -1.5: 0b0010,
    -2.0: 0b0101,
    -2.8: 0b0100,
    -3.3: 0b0111,
    -3.5: 0b0110,
    -3.9: 0b1001,
    -4.5: 0b1000,
    -5.0: 0b1011,
    -6.0: 0b1101,
    -7.5: 0b1100,
    -9.0: 0b1111,
    -12.0: 0b1110
}

# System reset signals
RST_CORE = 0b1000
RST_REGS = 0b0100
RST_REFCLK = 0b0010
RST_VCO = 0b0001
RST_ALL = 0b1111

# MUX Output selection (production modes only)
MUX_OUTPUT_default = 0b111     # Will not take effect unless 0x09[5] set or no lock
MUX_OUTPUT_raw = 0b000
MUX_OUTPUT_retimed = 0b001     # 'force' output even with no lock
MUX_OUTPUT_prbs = 0b100

# Adaptation setting
ADAPT_Mode0_None = 0b00
ADAPT_Mode1_CTLE_Only = 0b01
ADAPT_Mode2_Both_CTLE_Optimal = 0b10
ADAPT_Mode3_Both_DFE_Emphasis = 0b11

# PPM Groups, 0 and 1 exist for each channel
PPM_GROUP_0 = 0
PPM_GROUP_1 = 1
PPM_GROUP_Both = 2     # For code convenience use only

# Standard-based rate settings for auto mode register 0x2F
CDR_STANDARD_Ethernet = 0x06
CDR_STANDARD_Fibre_Channel = 0x16
CDR_STANDARD_Infiniband = 0x26
CDR_STANDARD_SDH_SONET = 0x56
CDR_STANDARD_PROP1a = 0x76
CDR_STANDARD_PROP1b = 0x86
CDR_STANDARD_Interlaken_2 = 0xC6
CDR_STANDARD_SFF_8431 = 0xD6

# Subrate (VCO divider) settings for manual mode register 0x2F[7:4]
SUBRATE_DIV_Grp0_8__Grp1_1 = 0b0000
SUBRATE_DIV_Grp0_1_2_4__Grp1_1 = 0b0001
SUBRATE_DIV_Grp0_1_2_4__Grp1_1_2_4 = 0b0010
SUBRATE_DIV_Grp0_2_4__Grp1_2_4 = 0b0100
SUBRATE_DIV_Grp0_1_4__Grp1_1_4 = 0b0101
SUBRATE_DIV_Grp0_1_2_4_8__Grp1_1_2_4_8 = 0b0110
SUBRATE_DIV_Grp0_1__Grp1_1 = 0b0111    # Or 0b1000, 0b1100, 0b1101
SUBRATE_DIV_Grp0_2__Grp1_2 = 0b1010
_SUBRATE_DIV_STATIC = [SUBRATE_DIV_Grp0_8__Grp1_1, SUBRATE_DIV_Grp0_1__Grp1_1,
                       SUBRATE_DIV_Grp0_2__Grp1_2]
_SUBRATE_DIV_VARIABLE = [SUBRATE_DIV_Grp0_1_2_4__Grp1_1, SUBRATE_DIV_Grp0_1_2_4__Grp1_1_2_4,
                         SUBRATE_DIV_Grp0_2_4__Grp1_2_4, SUBRATE_DIV_Grp0_1_4__Grp1_1_4,
                         SUBRATE_DIV_Grp0_1_2_4_8__Grp1_1_2_4_8]

# Reference clock mode (rarely not 0b11)
REF_CLK_Mode_3 = 0b11
REF_CLK_Constr_CAPDAC__RefClk_EN = 0b10
REF_CLK_Refless_Constr_CAPDAC = 0b01
REF_CLK_Refless_All_CAPDAC = 0b00

# CAP DAC range settings (override), stop = <setting>
CAP_DAC_RANGE_Start_Minus_4 = 0b11
CAP_DAC_RANGE_Start_Minus_3 = 0b10
CAP_DAC_RANGE_Start_Minus_2 = 0b01
CAP_DAC_RANGE_Start_Minus_1 = 0b00

# Figure of Merit (FOM) Mode
FOM_MODE_HEO_Only = 0x1
FOM_MODE_VEO_Only = 0x2
FOM_MODE_HEO_VEO = 0x3   # Default

# EOM Voltage Range Selection
EOM_Voltage_pm_100mV = 0x0
EOM_Voltage_pm_200mV = 0x1
EOM_Voltage_pm_300mV = 0x2
EOM_Voltage_pm_400mV = 0x3

# Channel/shared register group selection
_REG_GRP_Shared = 1
_REG_GRP_Channel = 0


class DS110DF410(I2CDevice):
    """Control class for the I2C DS110DF410 retimer IC."""

    _CHANNEL_0 = _CHANNEL_0
    _CHANNEL_1 = _CHANNEL_1
    _CHANNEL_2 = _CHANNEL_2
    _CHANNEL_3 = _CHANNEL_3
    _CHANNEL_All = _CHANNEL_All         # Applies to write only

    # Register Fields (Channel)
    _FIELD_Chn_Reset = _Field(0x00, _REG_GRP_Channel, 3, 4)         # Combined channel reset bits

    _FIELD_Chn_CDR_LL_INT = _Field(0x01, _REG_GRP_Channel, 4, 1)    # CDR Lock Loss Interrupt
    _FIELD_Chn_SIG_DET_LOSS_INT = _Field(0x01, _REG_GRP_Channel, 0, 1)  # SD Loss Interrupt

    _FIELD_Chn_Status = _Field(0x02, _REG_GRP_Channel, 7, 8)        # Channel status full byte

    _FIELD_Chn_Current_CTLE_Setting = _Field(0x03, _REG_GRP_Channel, 7, 8)      # CTLE stage setting
    _FIELD_Chn_LowDataRate_CTLE_Setting = _Field(0x3A, _REG_GRP_Channel, 7, 8)  # LR CTLE stage stng

    _FIELD_EOM_LockM_EN = _Field(0x3E, _REG_GRP_Channel, 7, 1)          # EOM Lock monitoring enable
    _FIELD_EOM_LockM_Thr_VEO = _Field(0x6A, _REG_GRP_Channel, 7, 4)     # EOM Lock mon VEO Threshold
    _FIELD_EOM_LockM_Thr_HEO = _Field(0x6A, _REG_GRP_Channel, 3, 4)     # EOM Lock mon HEO Threshold

    _FIELD_Chn_CAPDAC_StartVal_EN = _Field(0x09, _REG_GRP_Channel, 7, 1)    # EN CAPDAC startval ovr
    _FIELD_Chn_Bypass_PFD_0V = _Field(0x09, _REG_GRP_Channel, 5, 1)    # Override retimed and raw loopthru
    _FIELD_Chn_CAPDAC_Setting_0 = _Field(0x08, _REG_GRP_Channel, 4, 5)      # CAPDAC startval group0
    _FIELD_Chn_CAPDAC_Setting_1 = _Field(0x0B, _REG_GRP_Channel, 4, 5)      # CAPDAC startval group1

    _FIELD_Chn_EOM_VoltageRange = _Field(0x11, _REG_GRP_Channel, 7, 2)  # EOM Voltage Range Select

    _FIELD_Chn_Driver_VOD = _Field(0x2D, _REG_GRP_Channel, 2, 3)    # Output Differential Voltage
    _FIELD_Chn_Driver_DEM = _Field(0x15, _REG_GRP_Channel, 2, 3)    # Output De-emphasis
    _FIELD_Chn_Driver_SLOW = _Field(0x18, _REG_GRP_Channel, 2, 1)   # Output Slow Rise/Fall enable
    _FIELD_Chn_Driver_POL = _Field(0x1F, _REG_GRP_Channel, 7, 1)    # Output Polarity Inversion

    _FIELD_Chn_PFD_MUX = _Field(0x1E, _REG_GRP_Channel, 7, 3)       # PFD Output Select MUX
    _FIELD_Chn_PRBS_EN = _Field(0x1E, _REG_GRP_Channel, 4, 1)       # Enable PRBS Generator

    _FIELD_Chn_DFE_Power_Down = _Field(0x1E, _REG_GRP_Channel, 3, 1)            # DFE Power Down
    _FIELD_Chn_DFE_Override_En = _Field(0x23, _REG_GRP_Channel, 6, 1)           # DFE override enable
    _FIELD_Chn_DFE_Force_En = _Field(0x15, _REG_GRP_Channel, 7, 1)              # DFE Manual Tap enable
    _FIELD_Chn_DFE_Tap1_Weight = _Field(0x12, _REG_GRP_Channel, 4, 5)           # DFE Tap 1 Weight
    _FIELD_Chn_DFE_Tap2_Weight = _Field(0x21, _REG_GRP_Channel, 3, 4)           # DFE Tap 2 Weight
    _FIELD_Chn_DFE_Tap3_Weight = _Field(0x21, _REG_GRP_Channel, 7, 4)           # DFE Tap 3 Weight
    _FIELD_Chn_DFE_Tap4_Weight = _Field(0x20, _REG_GRP_Channel, 3, 4)           # DFE Tap 4 Weight
    _FIELD_Chn_DFE_Tap5_Weight = _Field(0x20, _REG_GRP_Channel, 7, 4)           # DFE Tap 5 Weight
    _FIELD_Chn_DFE_Tap1_Polarity = _Field(0x12, _REG_GRP_Channel, 7, 1)         # DFE Tap 1 Polarity
    _FIELD_Chn_DFE_Tap2_5_Polarities = _Field(0x11, _REG_GRP_Channel, 3, 4)     # DFE Taps 2-5 Polarity

    _FIELD_EOM_LockM_EN = _Field(0x3E, _REG_GRP_Channel, 7, 1)          # EOM Lock monitor enable
    _FIELD_Chn_EOM_Power_Down = _Field(0x11, _REG_GRP_Channel, 5, 1)    # EOM Power Down
    _FIELD_Chn_EOM_Override_EN = _Field(0x22, _REG_GRP_Channel, 7, 1)   # EOM Override enable
    _FIELD_Chn_FastEye_EN = _Field(0x24, _REG_GRP_Channel, 7, 1)        # EOM Fast Eye enable
    _FIELD_Chn_FastEye_Auto = _Field(0x24, _REG_GRP_Channel, 1, 1)      # EOM Fast Eye auto init

    _FIELD_Chn_HEO_Val = _Field(0x28, _REG_GRP_Channel, 7, 8)           # HEO Value
    _FIELD_Chn_VEO_Val = _Field(0x29, _REG_GRP_Channel, 7, 8)           # VEO Value

    _FIELD_Chn_CDR_Standard_Rate = _Field(0x2F, _REG_GRP_Channel, 7, 8)         # CDR Standard-based rates
    _FIELD_Chn_CDR_Subrate_Div = _Field(0x2F, _REG_GRP_Channel, 7, 4)           # CDR Manual Rate Mode
    _FIELD_Chn_Manual_Adapt_Initiate = _Field(0x2F, _REG_GRP_Channel, 0, 1)     # Initiate Adaptation

    _FIELD_Chn_EOM_VR_Lim_Err = _Field(0x30, _REG_GRP_Channel, 5, 1)
    _FIELD_Chn_HEO_VEO_INT = _Field(0x30, _REG_GRP_Channel, 4, 1)       # Cleared on read
    _FIELD_Chn_PRBS_EN_DIG_CLK = _Field(0x30, _REG_GRP_Channel, 3, 1)       # Enable clock to PRBS generator, toggle is primary PRBS reset method.

    _FIELD_Chn_Adapt_Mode = _Field(0x31, _REG_GRP_Channel, 6, 2)    # Adaptation / Lock mode
    _FIELD_Chn_FOM_Mode = _Field(0x31, _REG_GRP_Channel, 4, 2)      # Figure of Merit mode

    _FIELD_Chn_Ref_Clk_Mode = _Field(0x36, _REG_GRP_Channel, 5, 2)  # Reference clock mode
    _FIELD_CAPDAC_Range_Ovr_EN = _Field(0x36, _REG_GRP_Channel, 2, 1)  # CAPDAC range override EN

    _FIELD_Chn_PPM_Count_G0_LSB = _Field(0x60, _REG_GRP_Channel, 7, 8)  # PPM Count Group 0 LSB
    _FIELD_Chn_PPM_Count_G0_MSB = _Field(0x61, _REG_GRP_Channel, 6, 7)  # PPM Count Group 0 MSB
    _FIELD_Chn_PPM_Count_G0_EN = _Field(0x61, _REG_GRP_Channel, 7, 1)   # PPM Count Group 0 Enable
    _FIELD_Chn_PPM_Count_G1_LSB = _Field(0x62, _REG_GRP_Channel, 7, 8)  # PPM Count Group 1 LSB
    _FIELD_Chn_PPM_Count_G1_MSB = _Field(0x63, _REG_GRP_Channel, 6, 7)  # PPM Count Group 1 MSB
    _FIELD_Chn_PPM_Count_G1_EN = _Field(0x63, _REG_GRP_Channel, 7, 1)   # PPM Count Group 1 Enable
    _FIELD_Chn_PPM_Tolerance_G0 = _Field(0x64, _REG_GRP_Channel, 7, 4)  # PPM Tolerance Group 0
    _FIELD_Chn_PPM_Tolerance_G1 = _Field(0x64, _REG_GRP_Channel, 3, 4)  # PPM Tolerance Group 1

    _FIELD_Chn_FOM_Config_A = _Field(0x6B, _REG_GRP_Channel, 7, 8)  # Configurable FOM Param 'a'
    _FIELD_Chn_FOM_Config_B = _Field(0x6C, _REG_GRP_Channel, 7, 8)  # Configurable FOM Param 'b'
    _FIELD_Chn_FOM_Config_C = _Field(0x6D, _REG_GRP_Channel, 7, 8)  # Configurable FOM Param 'c'
    _FIELD_Chn_FOM_CTLE_EN = _Field(0x6E, _REG_GRP_Channel, 7, 1)   # Configurable FOM CTLE Enable
    _FIELD_Chn_FOM_CTLE_EN = _Field(0x6E, _REG_GRP_Channel, 6, 1)   # Configurable FOM DFE Enable

    _FIELD_Chn_VCO_Div_Override = _Field(0x18, _REG_GRP_Channel, 6, 3)  # Manual VCO div override
    _FIELD_Chn_VCO_Div_Override_EN = _Field(0x09, _REG_GRP_Channel, 2, 1)   # Enable above

    # Register Fields (Shared / Control)
    _FIELD_Shr_Reset = _Field(0x04, _REG_GRP_Shared, 6, 1)

    def __init__(self, address=0x18, **kwargs):
        """
        Initialise the DS110DF410 device.

        :param address: The address of the DS110DF410 is determined by pins ADDR_[3:0] as follows:
                        0x18 + 0b[A3][A2][A1][A0].
        """
        I2CDevice.__init__(self, address, **kwargs)
        logger.info("Created new ds110df410 instance with address 0x{:02X}.".format(address))

        # Set up channels
        self.channel_0 = self._Channel(self, DS110DF410._CHANNEL_0)
        self.channel_1 = self._Channel(self, DS110DF410._CHANNEL_1)
        self.channel_2 = self._Channel(self, DS110DF410._CHANNEL_2)
        self.channel_3 = self._Channel(self, DS110DF410._CHANNEL_3)
        self.channel_all = self._Channel(self, DS110DF410._CHANNEL_All)

        # Set up register access current state
        self._REG_GRP_SELECTED = _REG_GRP_Shared       # By default shared register write is on
        self._REG_CHANNEL_SELECTED = _CHANNEL_0         # By default channel 0 is selected

        self.channel_all.reset([RST_ALL])         # Get all channels in known reset state

    """
    Utility Functions:
    """
    @staticmethod
    def pins_to_address(A3, A2, A1, A0):
        """
        Return value of address that will be used by the device based on the address pin states.

        The address pins are ADDR_[3:0]. Arguments should be supplied as 1/0.
        """
        if not all(pin in [0, 1] for pin in [A3, A2, A1, A0]):     # Check pins are 1 or 0
            raise I2CException("Pins should be specified as 1 or 0")
        return (0x18 + ((A3 << 3) | (A2 << 2) | (A1 << 1) | A0))

    """
    Register and Field Access Functions:
    """
    def _reg_ch_sel(self, register_group, register_channel):
        """Select a channel or all channels for register access.

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
                self.write8(
                    0xFF,
                    0b0100 | (register_channel)     # WRITE_ALL_CH = 0, EN_CH_SMB = 1
                )
            elif register_channel == DS110DF410._CHANNEL_All:
                self.write8(
                    0xFF,
                    0b1100 | (register_channel)     # WRITE_ALL_CH = 1, EN_CH_SMB = 1
                )
            else:
                raise I2CException(
                    "Invalid register channel."
                    " Select self._CHANNEL_0-CHANNEL3 or self._CHANNEL_All."
                )
        else:
            raise I2CException(
                "Invalid register group."
                " Select _REG_GRP_Channel or _REG_GRP_Shared."
            )

    def _write_register(self, register_group, register_channel, register, value):
        """Write to an 8-bit register while handilng register group access.

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
        if any([
            (register_group != self._REG_GRP_SELECTED),
            (register_channel != self._REG_CHANNEL_SELECTED)
        ]):
            self._reg_ch_sel(register_group, register_channel)
        self.write8(register, value)

    def _read_register(self, register_group, register_channel, register):
        """Read from an 8-bit register while handling register group access.

        Ensures that the correct register group is specified for reads, and avoids unnecessary
        transmissions setting the group each time if it is already correct.

        :param register_group: Register group to use. _REG_GRP_Shared to set a shared control
                                register, or _REG_GRP_Channel to target only a channel (or all
                                channels), specified below.
        :param register_channel:    Channel written to if _REG_GRP_Channel is selected.
        :param register: Register ID to be read
        :return: Value read from the register
        """
        if any([
            (register_group != self._REG_GRP_SELECTED),
            (register_channel != self._REG_CHANNEL_SELECTED)
        ]):
            self._reg_ch_sel(register_group, register_channel)
        value_out = self.readU8(register)
        if value_out == -1:
            raise I2CException('Failed to read unsigned value from register {}'.format(register))
        logging.debug('Read register {} as {}'.format(register, value_out))
        return value_out

    def _write_field(self, field, channel, value, verify=False):
        """Write a field of <=8 bits into an 8-bit register.

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
            value,
            field.startbit,
            field.get_endbit(),
            field.register)
        )   # TODO update logging

        # warn about channel selection
        if field.register_group == _REG_GRP_Shared:
            if channel != DS110DF410._CHANNEL_All:
                logger.warning(
                    "Field is shared, but channel specified. Channel will be ignored.")
        elif field.register_group == _REG_GRP_Channel:
            if channel == _CHANNEL_All:
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
        new_msk = (0xff >> (8 - field.length)) << field.get_endbit()
        logger.debug("Register {}: field start: {}, field end: {} -> mask {:b}".format(
            field.register, field.startbit, field.get_endbit(), new_msk))
        new_value = (old_value & ~new_msk) | (value << field.get_endbit())
        logger.debug("Register {}: {:b} -> {:b}".format(field.register, old_value, new_value))
        if new_value != old_value:
            self._write_register(field.register_group, channel, field.register, new_value)

        if verify:
            verify_value = self._read_field(field, channel)
            logger.debug("Verifying value written ({:b}) against re-read: {:b}".format(
                value, verify_value))
            if verify_value != value:
                raise I2CException(
                    "Value {} was not successfully written to Field {}".format(
                        value, field))

    def _read_field(self, field, channel=_CHANNEL_All):
        """
        Read only the field-specific bits from the relevant register.

        :param register_group: Register group to use. REG_GROUP_Shared to set all registers, or
                                REG_GROUP_Chx to access a particlar channel.
        :param field: _Field instance holding relevant register and location of field bits
        """
        logger.debug("Getting field starting at bit {}, length {} from register {}".format(
            field.startbit, field.length, field.register))  # TODO update to include channels

        # Generate warnings / exception for incorrect reg group/channel combination
        if all([
            (field.register_group == _REG_GRP_Shared),
            (channel in [self._CHANNEL_0, self._CHANNEL_1, self._CHANNEL_2, self._CHANNEL_3]),
        ]):
            logger.warning(
                "Field is a shared / control register but channel was specified, ignoring...")
        elif ((field.register_group == _REG_GRP_Channel) and (channel == self._CHANNEL_All)):
            raise I2CException(
                "Field read requires a specific channel, plesase specify self._CHANNEL_0-3.")

        raw_register_value = self._read_register(field.register_group, channel, field.register)
        logger.debug("Raw value: {0:b}".format(raw_register_value))

        # remove high bits
        value = raw_register_value & (0xFF >> (7 - field.startbit))
        logger.debug("high bits removed: {0:b}".format(value))

        # shift value to position 0
        value = value >> field.get_endbit()
        logger.debug("Low bits removed: {0:b}".format(value))
        return value

    """
    Device Action Functions:
    """
    def reset(self, reset_channel_registers=True):
        """Reset all channels if requested, and enter the shared reset state.

        :param reset_channel_registers:     Boolean, if True, will individually also fully reset
                                            each channel.
        """
        if (reset_channel_registers):
            self.channel_all.reset([RST_ALL])                 # Full Reset all channels
        self._write_field(DS110DF410._FIELD_Shr_Reset, 0b1)    # Reset shared / control registers

    class _Channel:

        def __init__(self, ds110_instance, channel_id):
            self.CID = channel_id
            self._ds110 = ds110_instance

        def get_status(self):
            # Taken from Thomas' version and adapted
            logger.info(' Reset Reg: ' + hex(self._ds110._read_field(DS110DF410._FIELD_Chn_Reset, self.CID)))

            tmp = self._ds110._read_field(DS110DF410._FIELD_Chn_CDR_LL_INT, self.CID)
            logger.info('CDR LOCK LOSS INT: ' + str(tmp))
            tmp = self._ds110._read_field(DS110DF410._FIELD_Chn_SIG_DET_LOSS_INT, self.CID)
            logger.info('CDR LOCK LOSS INT: ' + str(tmp))

            tmp = self._ds110._read_field(DS110DF410._FIELD_Chn_EOM_VR_Lim_Err, self.CID)
            logger.info('EOM VRANGE LIMIT ERROR: ' + str(tmp))
            tmp = self._ds110._read_field(DS110DF410._FIELD_Chn_HEO_VEO_INT, self.CID)
            logger.info('HEO VEO INT: ' + str(tmp))

            tmp = self._ds110._read_field(DS110DF410._FIELD_Chn_Status, self.CID)
            logger.info(hex(tmp))
            if (tmp & 0b10000000):
                logger.info('Comp LPF Low')
            if (tmp & 0b01000000):
                logger.info('Comp LPF High')
            if (tmp & 0b00100000):
                logger.info('Single Bit Limit Reached')
            if (tmp & 0b00010000):
                logger.info('CDR Lock')
            if (tmp & 0b00001000):
                logger.info('LOCK')
            if (tmp & 0b00000100):
                logger.info('Fail Lock Check')
            if (tmp & 0b00000010):
                logger.info('Auto Adapt Complete')
            if (tmp & 0b00000011):
                logger.info('PPM Count Met')

            # Only valid if CDR is locked
            heo = self._ds110._read_field(DS110DF410._FIELD_Chn_HEO_Val, self.CID)
            veo = self._ds110._read_field(DS110DF410._FIELD_Chn_VEO_Val, self.CID)
            logger.info('HEO ' + str(heo))
            logger.info('VEO ' + str(veo))

        """
        CDR (Clock Data Recovery) Settings:
        """
        def configure_cdr_ppm_tolerance(self, ppm_tolerance, group_select):
            """Apply a PPM tolerance for the channel for a given group 0, 1, or both.

            The field is one byte in total, with one nibble for each group.

            :param ppm_tolerance:   PPM tolerance setting, one nibble wide (masked to 0x0F).
            :param group_select:    Group to apply the setting to. Choose PPM_GROUP_0, PPM_GROUP_1
                                    or PPM_GROUP_Both to set both nibbles.
            """
            if (ppm_tolerance & 0xF) != ppm_tolerance:
                raise I2CException(
                    "Please specify a single group tolerance with mask 0x0F."
                    "To apply this to both groups, choose PPM_GROUP_Both.")
            if not (group_select in [PPM_GROUP_0, PPM_GROUP_1, PPM_GROUP_Both]):
                raise I2CException(
                    "Invalid group selected. Please Choose PPM_GROUP_0/1/Both")

            if group_select in [PPM_GROUP_0, PPM_GROUP_Both]:
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_PPM_Tolerance_G0,
                    self.CID, ppm_tolerance
                )

            if group_select in [PPM_GROUP_1, PPM_GROUP_Both]:
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_PPM_Tolerance_G1,
                    self.CID, ppm_tolerance
                )

        def configure_cdr_standard_rate(self, cdr_standard):
            """
            Use a pre-defined standard for automatically determining channel rates and subrates.

            If a standard rate matches requirements, no further PPM settings will need to be set.

            :param cdr_standard:    Selected standard to determine rates. Choose from:
                                        CDR_STANDARD_Ethernet
                                        CDR_STANDARD_Fibre_Channel
                                        CDR_STANDARD_Infiniband
                                        CDR_STANDARD_SDH_SONET
                                        CDR_STANDARD_PROP1a
                                        CDR_STANDARD_PROP1b
                                        CDR_STANDARD_Interlaken_2
                                        CDR_STANDARD_SFF_8431
            """
            # Set value of 0x2f depending on standard selected
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_CDR_Standard_Rate,
                self.CID, cdr_standard)

            # NO rates should need to be set here, rates and subrates automatic (see 8.3.5)

            # Ensure standard mode is enabled
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_PPM_Count_G0_EN,
                self.CID, 0b1)                          # Group 0 Disable manual rate
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_PPM_Count_G1_EN,
                self.CID, 0b1)                          # Group 0 Disable manual rate

            # TODO Does Fibre need special consideration? See documentation:
            """
            For Fibre-Channel, the standard requiring a 10.51875GHz VCO frequency and the standard
            requiring an 8.5GHz VCO frequency require different settings for the registers shown in
            the table. The retimer cannot automatically switch between these two standards.
            """

        def set_cdr_ppm_count(self, int_Nppm_group0, int_Nppm_group1):
            # Write Nppm values for each group, and enable manual rate selection
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_PPM_Count_G0_LSB,
                self.CID, int_Nppm_group0 & 0xFF)       # Count Group 0 LSB
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_PPM_Count_G0_MSB,
                self.CID, (int_Nppm_group0 & 0x7F00))   # Count Group 0 MSB
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_PPM_Count_G1_LSB,
                self.CID, int_Nppm_group1 & 0xFF)       # Count Group 1 LSB
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_PPM_Count_G1_MSB,
                self.CID, (int_Nppm_group1 & 0x7F00) << 8)  # Count Group 1 MSB
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_PPM_Count_G0_EN,
                self.CID, 0b1)                          # Group 0 Enable manual rate
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_PPM_Count_G1_EN,
                self.CID, 0b1)                          # Group 0 Enable manual rate

        def _get_dividers_from_fld(dividers_setting):
            """
            Return the true divider value(s) associated with a the subrate divider field in 0x2F when used in manual mode.

            Because there can either be static divider settings with only one value for each group
            as well as variable ones (several values for one or both of the groups), function output
            is a tuple of two lists of group values, which in the case of a static setting will only
            contain one element.

            :pararm dividers_setting:   0x2F[7:4] field value, SUBRATE_DIV_Gro0_x__Grp1_x value
            :return:                    Tuple of divider value lists for each group:
                                            (Group 0 div list, Group 1 div list)
            """
            if dividers_setting == SUBRATE_DIV_Grp0_1__Grp1_1:
                divider_group0 = [1]
                divider_group1 = [1]
            elif dividers_setting == SUBRATE_DIV_Grp0_2__Grp1_2:
                divider_group0 = [2]
                divider_group1 = [2]
            elif dividers_setting == SUBRATE_DIV_Grp0_8__Grp1_1:
                divider_group0 = [8]
                divider_group1 = [1]
            elif dividers_setting == SUBRATE_DIV_Grp0_1_2_4__Grp1_1:
                divider_group0 = [1, 2, 4]
                divider_group1 = [1]
            elif dividers_setting == SUBRATE_DIV_Grp0_1_2_4__Grp1_1_2_4:
                divider_group0 = [1, 2, 4]
                divider_group1 = [1, 2, 4]
            elif dividers_setting == SUBRATE_DIV_Grp0_2_4__Grp1_2_4:
                divider_group0 = [2, 4]
                divider_group1 = [2, 4]
            elif dividers_setting == SUBRATE_DIV_Grp0_1_4__Grp1_1_4:
                divider_group0 = [1, 4]
                divider_group1 = [1, 4]
            elif dividers_setting == SUBRATE_DIV_Grp0_1_2_4_8__Grp1_1_2_4_8:
                divider_group0 = [1, 2, 4, 8]
                divider_group1 = [1, 2, 4, 8]
            else:
                raise I2CException("Divider ratio invalid")

            return (divider_group0, divider_group1)

        def autoconfigure_cdr_manual_rate(self, data_rate_group0, data_rate_group1, divider_ratio=None, desired_VCO_freq=None):
            """Configure the CDR for a specified frequency or known divider ratio.

            If a standard rate cannot be found to match requirements, custom rate/subrate settings
            can be used. PPM count targets and dividers can be set to allocate the correct VCO
            frequency for target required data rates for each channel group0/1.

            This function can be used in two ways:
                1) Call with desired frequency specified to calculate or verify divider ratios that
                    can provide the specified data rates.
                2) Call with only divider ratio specified to calculate a VCO frequency (and PPM
                    values) to use given the specified data rates. If impossible, the user will
                    be warned.

            If neither are specified, will default to 'frequency calculation', with an assumed
            nominal divider ratio of 1 for both groups 0 and 1.

            :param data_rate_group0:    Raw data rate for group 0, in Gbps
            :param data_rate_group1:    Raw data rate for group 1, in Gbps
            :param divider_ratio:       Divider ratio for VCO frequency to use for each group, in a
                                        combined bitfield. Choose from SUBRATE_DIV_Grp0_x__Grp1_x.
                                        (optional)
            :param desired_VCO_freq:    Shared VCO frequency used by both groups for the channel
                                        that will be divided down by the group dividers to generate
                                        the target data rates.
            """
            recalc_warn = 1         # Percentage to warn about recalculation percentage change

            # Check valid VCO frequency ranges
            if all([
                (not (8.5 <= desired_VCO_freq <= 11.3)),
                (desired_VCO_freq is not None),         # If not used, range doesn't matter
            ]):
                raise I2CException("VCO frequency for DS110DF410 must be between 8.5-11.3")

            # Check valid divider ratio has been specified
            if all([
                (divider_ratio is not None),
                (divider_ratio in (_SUBRATE_DIV_STATIC + _SUBRATE_DIV_VARIABLE))
            ]):
                raise I2CException("Unsupported divider ratio specified. "
                                   "See SUBRATE_DIV_Grp0_x__Grp1_x vaiants.")

            # Determine if auto frequency or auto divider is being used, react accordingly
            if desired_VCO_freq is None:        # Automatic frequency mode, requires static dividers
                logger.info("VCO Frequency will be determined automatically.")
                if divider_ratio is None:
                    logger.info("No divider ratios supplied, assuming 1,1.")
                    divider_ratio = SUBRATE_DIV_Grp0_1__Grp1_1
                if divider_ratio not in _SUBRATE_DIV_STATIC:
                    raise I2CException(
                        "Cannot choose a variable divider ratio with automatic frequency. "
                        "Please use a different divider, or specify desired_VCO_freq.")

                logger.info("Subrate divider selection using static dividers")
                dividers = DS110DF410._get_dividers_from_fld(divider_ratio)
                divider_group0 = dividers[0][0]
                divider_group1 = dividers[1][0]

                desired_VCO_freq = divider_group0 * data_rate_group0    # Calculate for group0
                logger.info("VCO frequency for group0 calculated as {}".format(desired_VCO_freq))

                # VCO freq is shared, so data rate group1 is re-calculated from the new VCO frequency
                # using the chosen divider.
                data_rate_group1_supplied = data_rate_group1
                data_rate_group1 = desired_VCO_freq / float(divider_group1)
                logger.info("Data rate for group1 re-calculated: "
                            "{} -> {}".format(data_rate_group1_supplied, data_rate_group1))

                if (abs(
                    (data_rate_group1 - data_rate_group1_supplied) / data_rate_group1_supplied
                ) > recalc_warn):
                    logger.warning("Recalculated data rate over {}% different".format(recalc_warn))

            else:                           # Manual frequency mode, can determine variable dividers
                logger.info(
                    "VCO Frequency set to {}Gbps.".format(desired_VCO_freq))

                if divider_ratio in _SUBRATE_DIV_STATIC:            # Using a static divider ratio
                    logger.info(
                        "Using static divider values, checking against frequency and data rates...")

                    divider_group0, divider_group1 = DS110DF410._get_dividers_from_fld(divider_ratio)
                    if any([
                        ((desired_VCO_freq / float(divider_group0)) != data_rate_group0),
                        ((desired_VCO_freq / float(divider_group1)) != data_rate_group1)
                    ]):
                        raise I2CException(
                            "Supplied divider ratio was not valid for given frequency, data rate. ")
                    else:
                        logger.info("Divider values checked successfully.")

                elif divider_ratio in _SUBRATE_DIV_VARIABLE:        # Using a variable divider ratio
                    logger.info("Using variable divider values, checking for valid combination...")
                    divider_lists = DS110DF410._get_dividers_from_fld(divider_ratio)
                    groups_found = [False, False]
                    for current_group in [0, 1]:
                        for divider_group_tmp in divider_lists[current_group]:
                            if (desired_VCO_freq / float(divider_group_tmp)):
                                logger.info("Found valid divider for group"
                                            "{}: {}".format(current_group, divider_group_tmp))
                                if current_group == 0:
                                    divider_group0 = divider_group_tmp
                                else:
                                    divider_group1 = divider_group_tmp
                                groups_found[current_group] = True
                                break
                    if False in groups_found:
                        raise I2CException("Failed to find valid combination for both groups")
                    else:
                        logger.info("Successfully found combination of dividers: "
                                    "{}, {}".format(divider_group0, divider_group1))

                else:                                               # Unspecified, try all
                    logger.info("Unspecified divider values, trying all combinations...")
                    for current_div in (_SUBRATE_DIV_STATIC, _SUBRATE_DIV_VARIABLE):

                        divider_lists = DS110DF410._get_dividers_from_fld(divider_ratio)
                        groups_found = [False, False]
                        for current_group in [0, 1]:
                            for divider_group_tmp in divider_lists[current_group]:
                                if (desired_VCO_freq / float(divider_group_tmp)):
                                    logger.info("Found valid divider for group"
                                                "{}: {}".format(current_group, divider_group_tmp))
                                    if current_group == 0:
                                        divider_group0 = divider_group_tmp
                                    else:
                                        divider_group1 = divider_group_tmp
                                    groups_found[current_group] = True
                                    break

                        if all(groups_found):
                            logger.info("Found good combination "
                                        "({}, {}) with setting {}".format(divider_group0,
                                                                          divider_group1,
                                                                          current_div))
                            divider_ratio = current_div
                            break

            # Set selected VCO divider setting
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_CDR_Subrate_Div,
                self.CID, divider_ratio)

            # Calcualte PPM count settings for given data rate, taking account of the selected divider subrate.
            data_rate_group0_scaled = data_rate_group0 * divider_group0
            int_Nppm_group0 = int(1280 * data_rate_group0_scaled)
            data_rate_group1_scaled = data_rate_group1 * divider_group1
            int_Nppm_group1 = int(1280 * data_rate_group1_scaled)

            # Ensure calculated values are possible in 15 bits
            if ((int_Nppm_group0 > 0x7FFF) or (int_Nppm_group1 > 0x7FFF)):
                raise I2CException(
                    "Failed to calculate valid Nppm value with current divider ratio (0x2F[7:4]"
                    "=0b{:04b}). Try specifying a different ratio.".format(divider_ratio))
            logger.info("Writing calculated CDR PPM counts: {}, {}".format(int_Nppm_group0, int_Nppm_group1))

            # Write calculated PPM values to registers
            self.set_cdr_ppm_count(int_Nppm_group0, int_Nppm_group1)

            # Set PPM tolerance to 0xFF default (0xF for both channels)
            self.configure_cdr_ppm_tolerance(0xF, PPM_GROUP_Both)

        def set_reference_clock_mode(self, ref_clk_mode):
            """
            Set the CAP DAC reference mode.

            In the default mode (Ref mode 3), VCO divider ratios will be tried automatically using
            ext osc, with no futher CAP DAC settings set.

            :param ref_clk_mode:    Select from: REF_CLK_Mode_3, REF_CLK_Constr_CAPDAC__RefClk_EN,
                                    REF_CLK_Refless_Constr_CAPDAC, REF_CLK_Refless_All_CAPDAC.
            """
            # By default, ref clk mode 3 will use external osc to switch VCO ratios in 0x2F manual mode
            if not (ref_clk_mode in [REF_CLK_Mode_3,
                                     REF_CLK_Constr_CAPDAC__RefClk_EN,
                                     REF_CLK_Refless_Constr_CAPDAC,
                                     REF_CLK_Refless_All_CAPDAC]):
                raise I2CException(
                    "Invalid reference clock mode specified, choose from:"
                    " REF_CLK_[Mode_3, Constr_CAPDAC__RefClk_EN, Refless_Constr_CAPDAC,"
                    " Refless_All_CAPDAC].")
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_Ref_Clk_Mode,
                self.CID, REF_CLK_Mode_3)

        def set_cap_dac_start_override_en(self, enable):
            """
            Set to enable CAP DAC start value override values in registers 0x08 and 0x0B.

            Set using the set_cap_dac_start_values() function below.

            :param enable:  Boolean, True to enable override
            """
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_CAPDAC_StartVal_EN,
                self.CID, bool(enable))

        def set_cap_dac_start_values(self, cap_dac_setting_0, cap_dac_setting_1):
            """
            Set the CAP DAC start value override values in registers 0x08 and 0x0B.

            Must be enabled with above function to take effect.

            :param cap_dac_setting_0:   CAP DAC start value for group 0, 5 bit field
            :param cap_dac_setting_1:   CAP DAC start value for group 1, 5 bit field
            """
            if any([
                (cap_dac_setting_0 & 0b11111 != cap_dac_setting_0),
                (cap_dac_setting_1 & 0b11111 != cap_dac_setting_1)
            ]):
                raise I2CException(
                    "CAP DAC setting in in correct range, should fit in 5 bit field")

            self._ds110._write_field(
                DS110DF410._FIELD_Chn_CAPDAC_Setting_0,
                self.CID, cap_dac_setting_0)
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_CAPDAC_Setting_1,
                self.CID, cap_dac_setting_1)

        def cap_dac_range_override_en(self, enable):
            """
            Set to enable range (stop value) override for CAP DAC in function below.

            :param enable:  Boolean, True to enable override
            """
            self._ds110._write_field(
                DS110DF410._FIELD_CAPDAC_Range_Ovr_En,
                self.CID, bool(enable))

        def cap_dac_range_override(self, cap_dac_range):
            """
            Override for VCO search range (stop) value.

            This is specified relative to the start value using several pre-defined choices.
            Must be enabled with above to take effect.

            :param cap_dac_range:   Range choice, from CAP_DAC_RANGE_Start_Minus<1-4>
            """
            if not (cap_dac_range in [CAP_DAC_RANGE_Start_Minus_1,
                                      CAP_DAC_RANGE_Start_Minus_2,
                                      CAP_DAC_RANGE_Start_Minus_3,
                                      CAP_DAC_RANGE_Start_Minus_4]):
                raise I2CException(
                    "Incorrect CAP DAC Range Specified")
            self._ds110._write_field(
                DS110DF410._FIELD_CAPDAC_Range_Override,
                self.CID, cap_dac_range)

        def override_vco_divider_ratio(self, manual_divider_ratio):
            """
            Manually force a certain VCO divider ratio. This should not commonly be used (8.5.11).

            :param manual_divider_ratio:    Integer selection from: 1, 2, 4, 8, or 16.
                                            Set to 0 to disable manual selection.
            """
            if manual_divider_ratio == 0:   # Disable override
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_VCO_Div_Override_EN,
                    self.CID, 0b0)
                return
            elif not (manual_divider_ratio in [1, 2, 4, 8, 16]):
                raise I2CException(
                    "Invalid divider ratio supplied, please choose 1, 2, 4, 8, or 16")

            # Set override field
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_VCO_Div_Override,
                self.CID, math.log2(manual_divider_ratio))

            # Enable override
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_VCO_Div_Override_EN,
                self.CID, 0b1)

        """
        Eye Opening Monitor (EOM) Settings:
        """
        def set_eom_voltage_range(self, eom_voltage_range):
            """
            Override for the voltage range for the eye-opening measurement comparator.

            This will usually be set during the CTLE lock/adaptation process, so should not
            normally require being overridden.

            :param eom_voltage_range:   Choice from a selection of voltage ranges between +-100 and
                                        +-400mV: EOM_Voltage_pm_<100, 200, 300, 400>mV
            """
            if eom_voltage_range not in [EOM_Voltage_pm_100mV,
                                         EOM_Voltage_pm_200mV,
                                         EOM_Voltage_pm_300mV,
                                         EOM_Voltage_pm_400mV]:
                raise I2CException("Invalid EOM Voltage Range selected")

            self._ds110._write_field(
                DS110DF410._FIELD_Chn_EOM_VoltageRange,
                self.CID, eom_voltage_range)

            logger.debug('Changed EOM Voltage Range to {}'.format(
                {
                    EOM_Voltage_pm_100mV: 'PM 100mV',
                    EOM_Voltage_pm_200mV: 'PM 200mV',
                    EOM_Voltage_pm_300mV: 'PM 300mV',
                    EOM_Voltage_pm_400mV: 'PM 400mV',
                }[eom_voltage_range]
            ))

        def eom_lock_monitor_en(self, enable):
            """
            Enable lock monitoring using the eye-opening monitor.

            Set the thresholds using the set_eom_lock_monitor() function below.
            """
            self._ds110._write_field(
                DS110DF410._FIELD_EOM_LockM_EN,
                self.CID, bool(enable))

        def set_eom_lock_monitor_thresholds(self, threshold_veo, threshold_heo):
            """
            Set the vertical and horisontal thresholds when using the EOM in lock monitoring mode.

            :param threshold_veo:       Vertical threshold
            :param threshold_heo:       Horisontal threshold
            """
            if any([
                (threshold_veo & 0xF) != threshold_veo,
                (threshold_heo & 0xF) != threshold_heo,
            ]):
                raise I2CException("Threshold values must fit in 4-bit field")
            self._ds110._write_field(
                DS110DF410._FIELD_EOM_LockM_Thr_VEO,
                self.CID, threshold_veo)
            self._ds110._write_field(
                DS110DF410._FIELD_EOM_LockM_Thr_HEO,
                self.CID, threshold_heo)

        def fast_eom_readout(self, eom_voltage_range=None):
            """
            Read out Fast Eye Monitor data under external control, into a 64x64 array representing the EOM output.

            :param eom_voltage_range:   Voltage range to be used by the EOM. If not specified, it
                                        will not be changed.
            :return:                    EOM output as 64x64 array of unsigned 16-bit integers
            """
            # Read current lock monitoring setting, temporarily disable it
            old_lockmon_setting = self._ds110._read_field(DS110DF410._FIELD_EOM_LockM_EN, self.CID)
            self.eom_lock_monitor_en(False)

            # If specified, change the EOM Voltage Range
            if eom_voltage_range is not None:
                self.set_eom_voltage_range(eom_voltage_range)

            # Force power to EOM circuitry
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_EOM_Power_Down,
                self.CID, 0b0)

            # Clear EOM override (may not be enabled)
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_EOM_Override_EN,
                self.CID, 0b0)

            # Enable Fast Eye Monitor, automatic Fast Eye
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_FastEye_EN,
                self.CID, 0b1)
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_FastEye_Auto,
                self.CID, 0b1)

            # Read out first 4 bytes, which are discarded
            self._ds110.readList(0x25, 4)

            # Read out remaining 64x64 array in 64 byte segments
            fast_eom_output = [[] for j in range(64)]
            for i in range(64):
                for j in range(64):
                    value = self._ds110.readU8(0x25) << 8 | self._ds110.readU8(0x26)
                    fast_eom_output[i].append(value)

            # Restore normal operating settings
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_FastEye_EN,
                self.CID, 0b0)          # Disable fasteye
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_EOM_Power_Down,
                self.CID, 0b1)          # Enable auto power down

            # Restore original lock monitor setting
            self.eom_lock_monitor_en(old_lockmon_setting)

            return fast_eom_output

        def fast_eom_shade_pixels(self, pxdata, thresholds=None):
            # Auto-determine thresholds if not supplied
            if thresholds is None:
                minpx = min(min(pxdata))
                maxpx = max(max(pxdata))

                # Split into 5 or the top threshold will only be set for one value
                thresholds = np.linspace(minpx, maxpx, 5)

            threshold_chars = {
                0: ' ',
                thresholds[0]: chr(0x2591),
                thresholds[1]: chr(0x2592),
                thresholds[2]: chr(0x2593),
                thresholds[3]: chr(0x2588),
            }

            logger.debug('EOM Shade Key: {}'.format(['{}-{}'.format(threshold_chars[th], th) for th in threshold_chars.keys()]))

            fullimage = []
            for row in pxdata:
                fullstr = ''
                for px in row:
                    current_char = threshold_chars[0]
                    for threshold in threshold_chars.keys():
                        if threshold < px:
                            current_char = threshold_chars[threshold]
                    fullstr += current_char

                fullimage.append(fullstr)

                logger.debug(fullstr)

            return fullimage

        """
        Adaptation Settings:
        """
        def set_adaptation_mode(self, adaptation_mode):
            """
            Set adaptation mode bits (simple wrapper).

            This could be done in isolation from other settings. See DS110DF410 datasheet section
            8.5.19 (Rev D Apr 2015) for guide. This will take effect at next loss of lock, or when
            manually enabled by calling initiate_adaptation().

            :param adaptation_mode: Mode to select from the following:
                                    ADAPT_Mode0_None, ADAPT_Mode1_CTLE_Only,
                                    ADAPT_Mode2_Both_CTLE_Optimal, ADAPT_Mode3_Both_DFE_Emphasis
            """
            if adaptation_mode in [ADAPT_Mode0_None,
                                   ADAPT_Mode1_CTLE_Only,
                                   ADAPT_Mode2_Both_CTLE_Optimal,
                                   ADAPT_Mode3_Both_DFE_Emphasis]:
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_Adapt_Mode,
                    self.CID, adaptation_mode)
            else:
                raise I2CException(
                    "Incorrect Adaptation Mode specified. "
                    "Use ADAPT_Modex_x.")

        def initiate_adaptation(self):
            """
            Manually initiate ataptation.

            Note that setting the adaptation mode is enough to ensure that adaptation will be used
            at the next loss of lock. This function will perform adapatation immediately.
            """
            self._ds110_write_field(
                DS110DF410._FIELD_Chn_Manual_Adapt_Initiate,
                self.CID, 0b1)
            time.sleep(50)
            self._ds110_write_field(
                DS110DF410._FIELD_Chn_Manual_Adapt_Initiate,
                self.CID, 0b0)

        def set_FOM_mode(self, fom_mode):
            """
            Set the figure of merit mode to use HEO, VEO, or both (the default) when not using the configurable mode.

            :param fom_mode:    Select from FOM_MODE_<HEO_Only, VEO_Only, HEO_VEO>
            """
            if fom_mode not in [FOM_MODE_HEO_Only, FOM_MODE_VEO_Only, FOM_MODE_HEO_VEO]:
                raise I2CException(
                    "Invalid FOM Mode, choose from FOM_MODE_<HEO_Only, VEO_Only, HEO_VEO>")
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_FOM_Mode,
                self.CID, fom_mode)

        def set_FOM_configurable(self, a, b, c, CTLE_EN, DFE_EN):
            """Set the arguments for the alternative 'configurable' figure of merit calculation.

            'Configurable' FOM calculation:
                FOM= (HEO– b) x a + (VEO– c) x (1 – a)

            If used, this must be individually enabled for CTLE and DFE if they should use it rather
            than the normal FOM calculation configured with set_FOM_mode in 0x2C[5:4].

            :param a/b/c:       Equation parameters. a is 7-bit, b/c are 8-bit fields
            :param CTLE_EN:     Enable configurable FOM calculation for CTLE
            :param DFE_EN:      Enable configurable FOM calculation for DFE
            """
            # Check Inputs
            if (a > 128):
                raise I2CException("Max configurable FOM argument a is 128")
            if any([
                ((a & 0xFF) != a),
                ((b & 0xFF) != b),
                ((c & 0xFF) != c)
            ]):
                raise I2CException("Invalid FOM argument for unsigned 8-bit field")

            # Set the a, b, c arguments
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_FOM_Config_A,
                self.CID, a)
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_FOM_Config_B,
                self.CID, b)
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_FOM_Config_C,
                self.CID, c)

            # Enable for CTLE and DFE if required
            if CTLE_EN:
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_FOM_CTLE_EN,
                    self.CID, 0b1)
            if DFE_EN:
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_FOM_DFE_EN,
                    self.CID, 0b1)

        def override_CTLE_boost_setting(self, stage0, stage1, stage2, stage3, limit_final_stage=False):
            """
            Override CTLE to a custom set of stages rather than the set created by the adaptation system.

            This will disable adaptation since, the only setting allowing CTLE adaptation is the
            setting where all adaptation is disabled.

            By bits:            override_CTLE_boost_setting(0b11, 0b01, 0b00, 0b10)
            By Boost String:    override_CTLE_boost_setting(3,1,0,2)

            :param stagex:              2-bit Field for each stage (all linear by default)
            :param limit_final_stage:   Set True to Convert final stage to limiting (not linear)
            """
            # Check Inputs
            for stage in [stage0, stage1, stage2, stage3]:
                if (stage & 0b11) != stage:
                    raise I2CException("All stages should fit in a 2-bit field")

            # Force Adaptation mode to 0 (the only one where CTLE is is not overridden)
            self.set_adaptation_mode(ADAPT_Mode0_None)

            # Apply desired setting in low-rate value used in LOL
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_LowDataRate_CTLE_Setting, self.CID,
                (stage0 << 6 + stage1 << 4 + stage2 << 2 + stage3))

            # Apply desired setting in current CTLE setting register
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_Current_CTLE_Setting, self.CID,
                (stage0 << 6 + stage1 << 4 + stage2 << 2 + stage3))

            # Apply desired setting in initial value for CTLE adaptation sequence
            tempField = _Field(0x40, _REG_GRP_Channel, 7, 8)    # The first of 32 registers
            self._ds110._write_field(
                tempField, self.CID,
                (stage0 << 6 + stage1 << 4 + stage2 << 2 + stage3))

            # Set limiting bit
            self.ds11._write_field(DS110DF410._FIELD_Chn_CTLE_Stg3_Limiting, self.CID,
                                   bool(limit_final_stage))

        def override_DFE_tap_weights(self, tap1_weight, tap2_weight, tap3_weight, tap4_weight,
                                     tap5_weight,
                                     tap1_pol_positive=False, tap2_pol_positive=False,
                                     tap3_pol_positive=False, tap4_pol_positive=False,
                                     tap5_pol_positive=False):
            """
            Override DFE tap weights rather than use the ones determined by the adaptation system.

            Note that depending on the adaptation settin, these changes may be overridden,
            so make sure DFE adaptation is off. Also, expect changed DFE settings to cause the CTLE
            to lose lock, which may cause it to adapt its own settings depending on the adaptation
            mode in use.

            :param tapx_weight:     Absolute weight for tap 'x'. Tap1 is 5 bits, all others are 4.
            :param tapx_pol_positive:   Boolean. Set True to make weight positive. Negative default.
            """
            # Check Inputs
            if (tap1_weight & 0b11111) != tap1_weight:
                raise I2CException("Tap 1 weight must fit in 5 bit field")
            for current_weight in [tap2_weight, tap3_weight, tap4_weight, tap5_weight]:
                if (current_weight & 0b1111) != current_weight:
                    raise I2CException(
                        "Tap {} weight must fit in 4 bit field".format(current_weight))

            # Enable DFE override
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_DFE_Override_En,
                self.CID, 0b1)

            # Power up DFE
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_DFE_Power_Down,
                self.CID, 0b0)

            # Enable manual DFE tap settings
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_DFE_Force_En,
                self.CID, 0b1)

            # Set tap weights
            weights = [tap1_weight, tap2_weight, tap3_weight, tap4_weight, tap5_weight]
            fields = [DS110DF410._FIELD_Chn_DFE_Tap1_Weight, DS110DF410._FIELD_Chn_DFE_Tap1_Weight,
                      DS110DF410._FIELD_Chn_DFE_Tap1_Weight, DS110DF410._FIELD_Chn_DFE_Tap1_Weight,
                      DS110DF410._FIELD_Chn_DFE_Tap1_Weight]
            for weightnum in range(1, 6):
                self._ds110._write_field(fields[weightnum], self.CID, weights[weightnum])

            # Set tap polarities
            polarities = [tap1_pol_positive, tap2_pol_positive, tap3_pol_positive,
                          tap4_pol_positive, tap5_pol_positive]
            fields = [DS110DF410._FIELD_Chn_DFE_Tap1_Polarity,
                      DS110DF410._FIELD_Chn_DFE_Tap2_Polarity,
                      DS110DF410._FIELD_Chn_DFE_Tap3_Polarity,
                      DS110DF410._FIELD_Chn_DFE_Tap4_Polarity,
                      DS110DF410._FIELD_Chn_DFE_Tap5_Polarity]
            for tapnum in range(1, 6):
                self._ds110._write_field(fields[tapnum], self.CID, polarities[tapnum])

        """
        Output Driver Settings:
        """
        def select_output(self, mux_output):
            """
            Select a particular MUX output.

            :param mux_output:  Output selection, from MUX_OUTPUT_x
            """
            if (mux_output == MUX_OUTPUT_default):
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_PFD_MUX,
                    self.CID, MUX_OUTPUT_default)       # Set MUX to mute
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_Bypass_PFD_0V,
                    self.CID, 0b0)                      # Disable PFD bypass
            elif (mux_output == MUX_OUTPUT_raw):
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_PFD_MUX,
                    self.CID, MUX_OUTPUT_raw)           # Set MUX to raw
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_Bypass_PFD_0V,
                    self.CID, 0b1)                      # Enable PFD bypass
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_PRBS_EN_DIG_CLK,
                    self.CID, 0b0)                      # Disable PRBS clock
            elif (mux_output == MUX_OUTPUT_retimed):    # 'Forced'
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_PFD_MUX,
                    self.CID, MUX_OUTPUT_retimed)       # Set MUX to raw
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_Bypass_PFD_0V,
                    self.CID, 0b1)                      # Enable PFD bypass
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_PRBS_EN_DIG_CLK,
                    self.CID, 0b0)                      # Disable PRBS clock
            elif (mux_output == MUX_OUTPUT_prbs):
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_PFD_MUX,
                    self.CID, MUX_OUTPUT_prbs)          # Set MUX to raw
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_Bypass_PFD_0V,
                    self.CID, 0b1)                      # Enable PFD bypass
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_PRBS_EN,
                    self.CID, 0b1)                      # Enable PRBS clock
                self._ds110._write_field(
                    DS110DF410._FIELD_Chn_PRBS_EN_DIG_CLK,
                    self.CID, 0b1)                      # Enable PRBS

        def configure_output_driver(self, diff_voltage=0.6, de_emphasis_db=0.0,
                                    slow_rise_fall_time=False, invert_output=False):
            """
            Configure various aspects of the channel-specific output drivers.

            Inputs for differential voltage and de-emphasis are in numerical form, and are
            converted to the binary representations before writing.

            :param diff_voltage:    Differential output voltage. Should be a float between 0.6-1.3.
                                    Has a resolution of 0.1.
            :param de_emphasis_db:  The De-emphasis setting in dB. Must match exactly a supported
                                    value. See DS110DF410 datasheet for table.
            :param slow_rise_fall_time: By default, minimum possible rise and fall times will be
                                        used. Set True to approximately double rise/fall times.
            :param invert_output:   Set True to invert channel output polarity (8.5.16)
            """
            # Differential Voltage Output
            if (diff_voltage < 0.6) or (diff_voltage > 1.3):
                raise I2CException(
                    "Differential voltage in incorrect range. "
                    "Enter a voltage between 0.6 and 1.3 inclusive")
            if (round(diff_voltage, 1) != diff_voltage):
                diff_voltage = round(diff_voltage, 1)
                logger.warning(
                    "Differential voltage can only be set in increments of 0.1, "
                    "Rounding to {}".format(diff_voltage))
            field_value = int((diff_voltage - 0.6) * 10)
            self._ds110._write_field(DS110DF410._FIELD_Chn_Driver_VOD, self.CID, field_value)

            # De-emphasis
            if not (de_emphasis_db in DS110DF410._De_Emphasis_Value_Map.keys()):
                raise I2CException(
                    "De-emphasis setting must be one of the following values: "
                    "{}".format(list(DS110DF410._De_Emphasis_Value_Map.keys())))
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_Driver_DEM, self.CID,
                DS110DF410._De_Emphasis_Value_Map[de_emphasis_db])

            # Slow Rise / Fall Time
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_Driver_SLOW, self.CID,
                0b1 & slow_rise_fall_time)

            # Output Polarity Inversion
            self._ds110._write_field(
                DS110DF410._FIELD_Chn_Driver_POL, self.CID,
                0b1 & invert_output)

        """
        Channel Actions
        """
        def reset(self, selection=[RST_ALL]):
            """
            Reset entire device or only sections of it for a given channel.

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
                self._ds110._write_field(self._ds110._FIELD_Chn_Reset, self.CID, RST_ALL)
            else:
                # or values to combine into single reset write
                rst_combined = 0
                for rst_bit in selection:
                    if rst_bit in [RST_CORE, RST_REGS, RST_REFCLK, RST_VCO]:
                        rst_combined |= rst_bit
                    else:
                        raise I2CException(
                            "incorrect reset sigal supplied. list items may only be:"
                            " rst_core, rst_regs, rst_refclk, rst_vco")
                self._ds110._write_field(self._ds110._FIELD_Chn_Reset, self.CID, rst_combined)
