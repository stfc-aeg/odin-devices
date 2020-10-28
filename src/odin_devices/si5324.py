"""
SI5324 - device access class for the SI5324 Clock Multiplier

Provides access to control settings registers for the SI5234 device both
individually through access functions as well as using settings generated
using a register map generated with DSPLLsim software.
"""

from odin_devices.i2c_device import I2CDevice, I2CException
import time

class _Field:
    def __init__(self, register, startbit, length):
        self.register = register
        self.startbit = startbit
        self.length = length

    def get_endbit (self):
        return (self.startbit - (length+1))

class SI5324:
    """
    SI4324 Class:
    TODO add description
    """

    _ICAL_sensitive_registers = [0,1,2,4,5,7,7,9,10,11,19,25,31,34,40,43,46,55]

    def __init__(self, address=0x68, **kwargs):
        """
        Initialise the SI5324 device.

        :param address: The address of the SI5324 is determined by pins A[2:0] as follows: 0b1101[A2][A1][A0].
        """

        # Define control fields within I2C registers
        SI5324._FIELD_Free_Run_Mode = _Field(0,6,0)     #FREE_RUN Free Run Mode Enable
        SI5324._FIELD_Clock_1_Priority = _Field(1,1,2)  #CK_PRIOR2 Clock with 2nd priority
        SI5324._FIELD_Clock_2_Priority = _Field(1,3,2)  #CK_PRIOR1 Clock with 1st priority

        SI5324._FIELD_ICAL_TRG = _Field(136,6,1)        #ICAL Internal Calibration Trigger
        SI5324._FIELD_RST_TRG = Field(136,7,1)          #RST_REG Internal Reset Trigger

        SI5324._FIELD_FOSC1_FLG = _FIELD(132,2,1)       #FOSC1_FLG Frequency Offset Flag for CLKIN_1
        SI5324._FIELD_FOSC2_FLG = _FIELD(132,3,1)       #FOSC2_FLG Frequency Offset Flag for CLKIN_2
        SI5324._FIELD_LOL_FLG = _FIELD(132,1,1)         #LOL_FLG Loss of Lock Flag

        # TODO define remaining relevant registers

        I2CDevice.__init__(self, address, **kwargs)
        #TODO init device (read file if present, otherwise specify other settings?)

        run_ical()

    def calc_address(A2,A1,A0):
        """
        Return value of address that will be used by the device based on the
        address pin states A[2:0]. Arguments should be supplied as 1/0.
        """
        return (0b1101000 & (A2 << 2) & (A1 << 1) & A0)


    def set_register_field(self, field, value, verify = False, ICAL_holdoff = False):
        """
        Write a field of <=8 bits into an 8-bit register.
        Field bits are masked to preserve other settings held within the same register.

        Some registers for this device are 'ICAL sensitive', meaning that a calibration
        procedure must be run if they are changed. This is handled automatically unless
        otherwise specified.

        :param field: _Field instance holding relevant register and location of field bits
        :param value: Unsigned byte holding unshifted value to be written to the field
        :param verify: Boolean. If true, read values back to verify correct writing.
        :param ICAL_holdoff: Prevents automatic ICAL run if an ICAL-sensitive register is modified. Useful if writing several values at the same time, but ENSURE that the ICAL is run manually if sensitive values have been modified.
        """
        # check input fits in specified field
        if (1 << (field.length + 1)) <= value:
            raise I2CException(
                    "Value {} does not fit in specified field of length {}.".format(value, field.length))

        old_value = self.readU8(field.register)
        new_value = old_value & (value << field.startbit)
        if new_value != old_value:
            self.write8(field.register, new_value)

        if verify:
            if get_register_field(field) != value:
                raise I2CException(
                        "Value {} was not successfully written to Field {}".format(value, field))

        if (not (ICAL_holdoff)) and (field.register in _ICAL_sensitive_registers):
            self.run_ical()


    def get_register_field(self, field):
        """
        Read only the field-specific bits from the relevant register

        :param field: _Field instance holding relevant register and location of field bits
        """
        raw_register_value = self.readU8(field.register)

        # remove high bits
        value = raw_register_value & (0xFF >> (7-field.startbit))

        # shift value to position 0
        value = value >> FIELD.get_endbit()
        return value

    def apply_register_map (self, mapfile_location, verify = True):
        """
        Write configuration from a register map generated with DSPLLsim.
        Since the map is register rather than value-based, there is no need to make use
        of the _Field access functions.

        :param mapfile_location: location of register map file to be read
        :param verify: Boolean. If true, read registers back to verify they are written correctly.
        """
        f = open(mapfile_location, 'r')

        for line in f.readlines():
            # The register map starts after general information is printed preceded by '#'
            if line[0] != '#':
                # Extract register-value pairing from register map
                register, value = line.split(',')
                register = int(register)
                value = int(value[1:3],16) # Value is in hex

                # Write register value
                self.write8(register, value)

                if verify:
                   if self.readU8(register) != value:
                       raise I2CException(
                               "Write of byte to register {} failed.".format(register))

        # ICAL-sensitive registers will have been modified during this process
        self.run_ical()

    def extract_register_map (self):
        pass
        #TODO add function to read current config to file for backup


    def run_ical (self):
        """
        Runs the ICAL calibration. This should be peformed before any usage, since
        accuracy is not guaranteed until it is complete.

        By default, output will be disabled before calibration has been completed, but
        enabled during the calibration. The output can be squelched during these periods,
        with CKOUT_ALWAYS_ON controlling for former, and SQ_ICAL the latter.

        The ICAL will typically take around 1s, and will hold LOL_FLG high during.
        """
        # Write register 136 bit 6 high (self-resetting)
        set_register_field(_FIELD_CAL_TRG, 1);

        # Wait for LOL low signal before proceeding (signals end of calibration)
        # Lock time (tLOCKMP) is:
        #       SI5324E*        Typ:1.0s    Max:1.5s
        #       SI5324A/B/C/D*  Typ:0.8s    Max:1.0s
        time.sleep(1000)
        while get_register_field(_FIELD_LOL_FLG):
            time.sleep(100)


    """
    Manual Access Functions:
    """
    def set_freerun_mode(self, mode):
        """
        Set true to enable Free Run mode, where XA-XB is routed to replace Clock Input 2.

        :param mode: Boolean. If True, Free Run mode is enabled.
        """
        if (mode):
            set_register_field(SI5324._FIELD_Free_Run_Mode, 1, False)
        else :
            set_register_field(SI5324._FIELD_Free_Run_Mode, 0, False)

    def set_clock_priority(self, top_priority_clock, check_auto_en = True):
        """
        Set the clock that takes priority if clock autoselection is enabled.

        :param top_priority_clock: 1 or 2, indicating which clock has higher priority
        :param check_auto_en: Set False to disable checking if clock auto-selection is enabled
        """
        if not get_clock_autoselection() :
            raise I2CException(
                    "Warning: setting priority clock without enabling auto-selection. Enable this first, or disable this warning with 'check_auto_en=False'")

        if top_priority_clock == 1:
            set_register_field(SI5324._FIELD_Clock_1_Priority, 0b00, True, False)
            set_register_field(SI5324._FIELD_Clock_2_Priority, 0b01, True, False)
        elif top_priority_clock == 2:
            set_register_field(SI5324._FIELD_Clock_1_Priority, 0b01, True, False)
            set_register_field(SI5324._FIELD_Clock_2_Priority, 0b00, True, False)
        else:
            raise I2CException(
                    "Supply either 1 or 2 for argument 1, the Clock ID")

        # Clock priority is ICAL-sensitive, but cal was held off, so it must be called manually.
        run_ical()

