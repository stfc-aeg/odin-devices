"""
SI5324 - device access class for the SI5324 Clock Multiplier

Provides access to control settings registers for the SI5234 device both
individually through access functions as well as using settings generated
using a register map generated with DSPLLsim software.
"""

from odin_devices.i2c_device import I2CDevice, I2CException
import time
import logging

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('si5324')

class _Field:
    """
    Field Class:
    Used to address specific bit fields within 8-bit register addresses for the
    device. This means the function of the fields are kept abstract from the
    physical register location.
    """
    def __init__(self, register, startbit, length):
        self.register = register
        self.startbit = startbit
        self.length = length

    def get_endbit (self):
        return (self.startbit - (self.length-1))

class SI5324(I2CDevice):
    """
    SI4324 Class:
    TODO add description
    """

    # Registers that will require an iCAL calibration after modification
    _ICAL_sensitive_registers = [0,1,2,4,5,7,7,9,10,11,19,25,31,34,40,43,46,55]
    # Registers that should be included in the extracted register mapfile
    _regmap_registers = [0,1,2,3,4,5,6,7,8,9,
            10,11,19,
            20,21,22,23,24,25,
            31,32,33,34,35,36,
            40,41,42,43,44,45,46,47,48,
            55,
            131,132,137,138,139,
            142,143,
            136]                        # Register 136 is here by convention (iCAL trigger)

    def __init__(self, address=0x68, **kwargs):
        """
        Initialise the SI5324 device.

        :param address: The address of the SI5324 is determined by pins A[2:0] as follows: 0b1101[A2][A1][A0].
        """

        # Define control fields within I2C registers
        SI5324._FIELD_Free_Run_Mode = _Field(0,6,1)     #FREE_RUN Free Run Mode Enable
        SI5324._FIELD_Clock_1_Priority = _Field(1,1,2)  #CK_PRIOR2 Clock with 2nd priority
        SI5324._FIELD_Clock_2_Priority = _Field(1,3,2)  #CK_PRIOR1 Clock with 1st priority

        SI5324._FIELD_Autoselection = _Field(4,7,2)     #AUTOSEL_REG Autoselection mode

        SI5324._FIELD_LOS1_INT = _Field(129,1,1)        #LOS1_INT Loss of Signal alarm for CLKIN_1
        SI5324._FIELD_LOS2_INT = _Field(129,2,1)        #LOS2_INT Loss of Signal alarm for CLKIN_2
        SI5324._FIELD_LOSX_INT = _Field(129,0,1)        #LOSX_INT Loss of Signal alarm for XA/XB

        SI5324._FIELD_FOSC1_INT = _Field(130,1,1)       #FOSC1_INT Frequency Offset alarm for CLKIN_1
        SI5324._FIELD_FOSC2_INT = _Field(130,2,1)       #FOSC2_INT Frequency Offset alarm for CLKIN_2
        SI5324._FIELD_LOL_INT = _Field(130,0,1)         #LOL_INT Loss of Lock alarm

        SI5324._FIELD_ICAL_TRG = _Field(136,6,1)        #ICAL Internal Calibration Trigger
        SI5324._FIELD_RST_TRG = _Field(137,7,1)          #RST_REG Internal Reset Trigger

        # NOTE: FLGs need manual clearing, for live alarm status, use corresponding INT signals...
        SI5324._FIELD_FOSC1_FLG = _Field(132,2,1)       #FOSC1_FLG Frequency Offset Flag for CLKIN_1
        SI5324._FIELD_FOSC2_FLG = _Field(132,3,1)       #FOSC2_FLG Frequency Offset Flag for CLKIN_2
        SI5324._FIELD_LOL_FLG = _Field(132,1,1)         #LOL_FLG Loss of Lock Flag

        # TODO define remaining relevant registers

        I2CDevice.__init__(self, address, **kwargs)
        #TODO init device (read file if present, otherwise specify other settings?)

        #self.run_ical()

    def calc_address(A2,A1,A0):
        """
        Return value of address that self.will be used by the device based on the
        address pin states A[2:0]. Arguments should be supplied as 1/0.
        """
        return (0b1101000 | (A2 << 2) | (A1 << 1) | A0)


    """
    Direct Control Field Functions
    """
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
        logger.info("Writing value {} to field {}-{} in register {}".format(value,field.startbit,field.get_endbit(),field.register))

        # check input fits in specified field
        if (1 << (field.length + 1)) <= value:
            raise I2CException(
                    "Value {} does not fit in specified field of length {}.".format(value, field.length))

        old_value = self.readU8(field.register)
        new_msk = (0xff >> (8-field.length))<< field.get_endbit()
        logger.debug("Register {}: field start: {}, field end: {} -> mask {:b}".format(field.register,field.startbit,field.get_endbit(), new_msk))
        new_value = (old_value & ~new_msk)| (value << field.get_endbit())
        logger.info("Register {}: {:b} -> {:b}".format(field.register, old_value, new_value))
        if new_value != old_value:
            self.write8(field.register, new_value)

        if verify:
            verify_value = self.get_register_field(field)
            logger.debug("Verifying value written ({:b}) against re-read: {:b}".format(value,verify_value))
            if verify_value != value:
                raise I2CException(
                        "Value {} was not successfully written to Field {}".format(value, field))

        if (not (ICAL_holdoff)) and (field.register in SI5324._ICAL_sensitive_registers):
            logger.info("Register {} requireds iCAL run".format(field.register))
            self.run_ical()


    def get_register_field(self, field):
        """
        Read only the field-specific bits from the relevant register

        :param field: _Field instance holding relevant register and location of field bits
        """
        logger.debug("Getting field starting at bit {}, length {} from register {}".format(field.startbit,field.length,field.register))

        raw_register_value = self.readU8(field.register)
        logger.debug("Raw value: {0:b}".format(raw_register_value))

        # remove high bits
        value = raw_register_value & (0xFF >> (7-field.startbit))
        logger.debug("high bits removed: {0:b}".format(value))

        # shift value to position 0
        value = value >> field.get_endbit()
        logger.debug("Low bits removed: {0:b}".format(value))
        return value


    """
    Register Map File Functions
    """
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

                if register == 136 and (value & 0x40):
                    logger.info("Ignoring write to iCAL, will be applied next")
                    continue

                # Write register value
                logger.info("Writing register {} with value {:02X}".format(register,value))
                self.write8(register, value) 

                if verify:
                    verify_value = self.readU8(register)
                    logger.debug("Verifying value written ({:b}) against re-read: {:b}".format(value,verify_value))
                    if verify_value != value:
                       raise I2CException(
                               "Write of byte to register {} failed.".format(register))

        # ICAL-sensitive registers will have been modified during this process
        self.run_ical()

    def extract_register_map (self, mapfile_location):
        """
        Generate a register map file using the current settings in device control
        registers. This file can then be loaded using apply_register_map(filename).

        :param mapfile_location@ location of register map file that will be written to.
        """
        f = open(mapfile_location, 'w')
        f.write("# This register map has been generated for the odin-devices SI5324 driver.\n")

        # The registers that will be read are the ones found in output register
        # maps from DSPLLsim.
        for register in SI5324._regmap_registers:

            if register == 136:
                # This register will read 00, but should be written as 0x40 to match
                # the versions generated by DSPLLsim. This would trigger an iCAL if
                # written, but is ignored in apply_register_map().
                f.write("136, 40h\n")
                continue

            value = self.readU8(register)
            logger.info("Read register {}: {:02X}".format(register, value))
            f.write("{}, {:02X}h\n".format(register, value))

        logger.info("Register map extraction complete, to file: {}".format(mapfile_location))
        f.truncate()
        f.close()


    """
    Calibration
    """
    def run_ical (self):
        """
        Runs the ICAL calibration. This should be peformed before any usage, since
        accuracy is not guaranteed until it is complete.

        By default, output will be disabled before calibration has been completed, but
        enabled during the calibration. The output can be squelched during these periods,
        with CKOUT_ALWAYS_ON controlling for former, and SQ_ICAL the latter.

        The ICAL will typically take around 1s, and will hold LOL_INT high during.
        """
        # Write register 136 bit 6 high (self-resetting)
        self.set_register_field(SI5324._FIELD_ICAL_TRG, 1);

        logger.info("iCAL initiated")

        # Wait for LOL low signal before proceeding (signals end of calibration)
        # Lock time (tLOCKMP) is:
        #       SI5324E*        Typ:1.0s    Max:1.5s
        #       SI5324A/B/C/D*  Typ:0.8s    Max:1.0s
        time.sleep(1.000)
        while self.get_register_field(SI5324._FIELD_LOL_INT):
            time.sleep(0.100)
            logger.debug("iCAL waiting...")

        logger.info("iCAL done")


    """
    Manual Access Functions:
    """
    def set_freerun_mode(self, mode):
        """
        Set true to enable Free Run mode, where XA-XB is routed to replace Clock Input 2.

        :param mode: Boolean. If True, Free Run mode is enabled.
        """
        if (mode):
            self.set_register_field(SI5324._FIELD_Free_Run_Mode, 1, False)
        else :
            self.set_register_field(SI5324._FIELD_Free_Run_Mode, 0, False)

    def set_clock_priority(self, top_priority_clock, check_auto_en = True):
        """
        Set the clock that takes priority if clock autoselection is enabled.

        :param top_priority_clock: 1 or 2, indicating which clock has higher priority
        :param check_auto_en: Set False to disable checking if clock auto-selection is enabled
        """
        if self.get_register_field(SI5324._FIELD_Autoselection) or check_auto_en == False:
            raise I2CException(
                    "Warning: setting priority clock without enabling auto-selection. Enable this first, or disable this warning with 'check_auto_en=False'")

        if top_priority_clock == 1:
            self.set_register_field(SI5324._FIELD_Clock_1_Priority, 0b00, True, True)
            self.set_register_field(SI5324._FIELD_Clock_2_Priority, 0b01, True, True)
        elif top_priority_clock == 2:
            self.set_register_field(SI5324._FIELD_Clock_1_Priority, 0b01, True, True)
            self.set_register_field(SI5324._FIELD_Clock_2_Priority, 0b00, True, True)
        else:
            raise I2CException(
                    "Supply either 1 or 2 for argument 1, the Clock ID")

        # Clock priority is ICAL-sensitive, but cal was held off, so it must be called manually.
        self.run_ical()

