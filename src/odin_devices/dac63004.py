"""ADAC63004 class.
    Data sheeet: https://www.ti.com/product/DAC63004
    Page 54: register map

Adam Davis, STFC Application Engineering Group.
"""

from odin_devices.i2c_device import I2CDevice
import logging
import math
from enum import Enum

class DAC63004(I2CDevice):
    """ADAC63004 class - DAC device converting register values to voltage or constant current
    Data sheeet: https://www.ti.com/product/DAC63004
    Page 54: register map
    """
    _25rangeOffset = -0.13042
    _50rangeOffset = -10.9617
    _125rangeOffset = -11.1254
    _250rangeOffset = -10.7742
    device_registers = {
        'NOOP':{'address': 0x00,'flipped': False}, 
        'DAC_0_MARGIN_HIGH':{'address': 0x01, 'flipped': True}, 
        'DAC_0_MARGIN_LOW':{ 'address': 0x02, 'flipped': True},
        'DAC_0_VOUT_CMP_CONFIG':{'address': 0x03,'flipped': True},
        'DAC_0_IOUT_MISC_CONFIG':{'address': 0x04,'flipped': True},
        'DAC_0_CMP_MODE_CONFIG':{'address': 0x05,'flipped': True},
        'DAC_0_FUNC_CONFIG': {'address': 0x06, 'flipped': True},
        'DAC_1_MARGIN_HIGH':{'address': 0x07,'flipped':True},
        'DAC_1_MARGIN_LOW':{'address': 0x08,'flipped': True},
        'DAC_1_VOUT_CMP_CONFIG':{'address': 0x09,'flipped': True},
        'DAC_1_IOUT_MISC_CONFIG':{'address': 0x0A,'flipped': True},
        'DAC_1_CMP_MODE_CONFIG':{'address': 0x0B,'flipped': True},
        'DAC_1_FUNC_CONFIG':{'address': 0x0C,'flipped': True},
        'DAC_2_MARGIN_HIGH':{'address': 0x0D,'flipped': True},
        'DAC_2_MARGIN_LOW':{'address': 0x0E,'flipped': True},
        'DAC_2_VOUT_CMP_CONFIG':{'address': 0x0F,'flipped': True},
        'DAC_2_IOUT_MISC_CONFIG':{'address': 0x10,'flipped': True},
        'DAC_2_CMP_MODE_CONFIG':{'address': 0x11,'flipped': True},
        'DAC_2_FUNC_CONFIG':{'address': 0x12,'flipped': True},
        'DAC_3_MARGIN_HIGH':{'address': 0x13, 'flipped': True},
        'DAC_3_MARGIN_LOW':{'address': 0x14, 'flipped': True},
        'DAC_3_VOUT_CMP_CONFIG':{'address': 0x15,'flipped': True},
        'DAC_3_IOUT_MISC_CONFIG':{'address': 0x16,'flipped': True},
        'DAC_3_CMP_MODE_CONFIG':{'address': 0x17,'flipped': True},
        'DAC_3_FUNC_CONFIG':{'address': 0x18,'flipped': True},
        'DAC_0_DATA':{'address': 0x19,'flipped': True},
        'DAC_1_DATA':{'address': 0x1A,'flipped': True},
        'DAC_2_DATA':{'address': 0x1B,'flipped': True},
        'DAC_3_DATA':{'address': 0x1C,'flipped': True},
        'COMMON_CONFIG':{'address': 0x1F,'flipped': True},
        'COMMON_TRIGGER':{'address': 0x20,'flipped': False},
        'COMMON_DAC_TRIG':{'address': 0x21,'flipped': False},
        'GENERAL_STATUS':{'address': 0x22,'flipped': False},
        'CMP_STATUS':{'address': 0x23,'flipped': False},
        'GPIO_CONFIG':{'address': 0x24,'flipped': False},
        'DEVICE_MODE_CONFIG':{'address': 0x25,'flipped': False},
        'INTERFACE_CONFIG':{'address': 0x26, 'flipped': False},
        'SRAM_CONFIG':{'address': 0x2B, 'flipped': False},
        'SRAM_DATA':{'address': 0x2C, 'flipped': False},
        'DAC_0_DATA_8BIT':{'address': 0x40, 'flipped': False},
        'DAC_1_DATA_8BIT':{'address': 0x41, 'flipped': False},
        'DAC_2_DATA_8BIT':{'address': 0x42, 'flipped': False},
        'DAC_3_DATA_8BIT':{'address': 0x43, 'flipped': False},
        'BRDCAST_DATA':{'address': 0x50, 'flipped': True},
        #end of register space
    }
    internal_reference_voltage = 1.212
    external_reference_voltage = None
    VDD_reference_voltage = None
    
    class VoltageGain(Enum):
        EXT_REF_1x = 0b000
        VDD_REF_1x = 0b001
        INT_REF_1_5x = 0b010
        INT_REF_2x = 0b011
        INT_REF_3x = 0b100
        INT_REF_4x = 0b101
        
    class VoltagePowerDownMode(Enum):
        POW_DOWN_10k = 0b1
        POW_DOWN_100k = 0b10
        POW_DOWN_HI_Z = 0b11
        
    class CurrentRange(Enum):
        RANGE_0_25 = 0b0
        RANGE_0_50 = 0b1000000000
        RANGE_0_125 = 0b10000000000
        RANGE_0_250 = 0b11000000000
        RANGE_0_negative_24 = 0b100000000000
        RANGE_0_negative_48 = 0b101000000000
        RANGE_0_negative_120 = 0b110000000000
        RANGE_0_negative_240 = 0b111000000000
        RANGE_negative_25_25 = 0b1000000000000
        RANGE_negative_50_50 = 0b1001000000000
        RANGE_negative_125_125 = 0b1010000000000
        RANGE_negative_250_250 = 0b1011000000000

    def __init__(self, address, busnum, external_reference_voltage=None, VDD_reference_voltage=None, **kwargs):
        I2CDevice.__init__(self, address, busnum, **kwargs)
        self.external_reference_voltage = external_reference_voltage
        self.VDD_reference_voltage = VDD_reference_voltage
        

    def read_all_registers(self):
        """Iterate over each register in the device_registers dictionary, read them and print the result."""
        for i in self.device_registers:
            if (self.device_registers[i]["flipped"]):
                print("Read register " + i + " as " + str(hex(self.readU16flipped(self.read_register_address(i)))))
            else:
                print("Read register " + i + " as " + str(hex(self.readU16(self.read_register_address(i)))))
        
    def read_register_address(self, register_name):
        """Gets the address of the specified register by name, returning none if the name does not match any registers.
        
        Args:
            register_name (string): the name of the register we want to get the address for
        """
        if register_name in self.device_registers:
            return self.device_registers[register_name]['address']
        else:
            print(f"Register '{register_name}' not found.")
            return None
        
    def read_modify_write(self, register_name, mask, value):
        """
        Perform a read-modify-write operation on a register.

        :param register_address: Address of the register to modify.
        :param mask: Bit mask specifying the bits to modify.
        :param value: 16-bit integer value to apply to the masked bits.
        """
        current_value = self.read_register(self.read_register_address(register_name), self.device_registers[register_name]["flipped"], False)
        modified_value = (current_value & ~mask) | (value & mask)
        self.write_register(self.read_register_address(register_name), modified_value, self.device_registers[register_name]["flipped"])
    
    def write_register(self, register_address, value, flipped=False, debug=True):
        """
        Write a 16-bit value to a register accessed using the address

        :param register_address: Address of the register to write.
        :param value: 16-bit integer value to write to the register.
        :param flipped: For certain registers, the first 8 bits and the last 8 bits are read in the wrong order. 
            If flipped is set to true, it swaps the first and last 8 bits to fix this.
        """
        if (flipped):
            self.write16flipped(register_address, value)
        else:
            self.write16(register_address, value)
        if (debug):
            print("Wrote value " + str(bin(value)) + " to register at address " + str(hex(register_address)))
            
    def read_register_by_name(self, name, debug=True):
        """
        Read a 16-bit value from a register accessed using the name 

        :param register_name: name of the register to read from.
        :param flipped: For certain registers, the first 8 bits and the last 8 bits are read in the wrong order. 
            If flipped is set to true, it swaps the first and last 8 bits to fix this.
        """
        if (name in self.device_registers.keys()):
            register_address = self.device_registers[name].address
            flipped = self.device_registers[name].flipped
            if (flipped):
                result = self.readU16flipped(register_address)
            else:
                result = self.readU16(register_address)
            if (debug):
                print("Read register at address " + str(hex(register_address)) + " as " + str(bin(result)))
            return result
        else:
            raise Exception("No register found matching name '" + name + "'.")
            
    def read_register(self, register_address, flipped=False, debug=True):
        """
        Read a 16-bit value from a register accessed using the address

        :param register_address: Address of the register to read from.
        :param flipped: For certain registers, the first 8 bits and the last 8 bits are read in the wrong order. 
            If flipped is set to true, it swaps the first and last 8 bits to fix this.
        """
        if (flipped):
            result = self.readU16flipped(register_address)
        else:
            result = self.readU16(register_address)
        if (debug):
            print("Read register at address " + str(hex(register_address)) + " as " + str(bin(result)))
        return result
        
    def write16flipped(self, reg, value):
        """Write a 16-bit value to the specified register/address pair, replacing the first 8 bits with the last 8 bits and vice versa
        
        reg (int): the address of the register to write to
        value (int): the value to write to the register
        """
        try:
            #flip the first and last 8 bits around
            flipped_value = ((value & 0xFF00) >> 8) | ((value & 0x00FF) << 8)            
            #write the flipped value
            self.bus.write_word_data(self.address, reg, flipped_value)
        except IOError as err:
            logging.error("--------------------------------------------------")
            logging.error("Error: " + str(err))
            logging.error("Write16 failed to write value " + str(bin(value)) + " to register " + str(hex(reg)))
            logging.error("--------------------------------------------------")
            return -1
        
    def readU16flipped(self, reg):
        """Read an unsigned 16-bit value from the I2C device, replacing the first 8 bits with the last 8 bits and vice versa
        
        reg (int): the address of the register to read
        """
        try:
            original = self.bus.read_word_data(self.address, reg)
            #flip the first and last 8 bits around
            result = ((original & 0xFF00) >> 8) | ((original & 0x00FF) << 8)
            return result
        except IOError as err:
            logging.error("--------------------------------------------------")
            logging.error("Error: " + str(err))
            logging.error("Read16 failed to read value from register " + str(hex(reg)))
            logging.error("--------------------------------------------------")
            return -1

    def put_dac_into_current_mode(self, index, voltageTermination=VoltagePowerDownMode.POW_DOWN_HI_Z):
        """ Set the dac at the provided index into current output mode, powering down the voltage mode in the method specified
        
        voltageTermination (string):
            "01": Power-down VOUT-X with 10 KΩ to AGND
            "10": Power-down VOUT-X with 100 KΩ to AGND
            "11": Power-down VOUT-X with Hi-Z to AGND
        """
        #There are only 4 dacs, so check there is a valid index
        if (index >= 0 and index <= 3):
            # Build the mask and value to write based on the index of the dac we want to enable. 
            # To set a dac to current, we want to write 110 to the appropriate section on the COMMON_CONFIG register.
            # The 11 sets the voltage output for the dac to Hi-Z power down mode
            # The 0 sets the current output for the dac to powered up mode
            # See page 61 in the data sheet for more info on the COMMON_CONFIG register
            mask = 0b111 << (3*index)
            write = voltageTermination.value << ((3*index)+1)
            
            self.read_modify_write("COMMON_CONFIG", mask, write)
        else:
            print("Not a valid index.")
            return
        
    def put_dac_into_voltage_mode(self, index):
        """Set the dac at the provided input to voltage output mode, powering down current mode

        Args:
            index (int): a number between zero and 3, telling us which dac we want to put into voltage mode
        """
        #There are only 4 dacs, so check there is a valid index
        if (index >= 0 and index <= 3):
            # Build the mask and value to write based on the index of the dac we want to enable. 
            # To set a dac to voltage, we want to write 001 to the appropriate section on the COMMON_CONFIG register.
            # The 00 sets the voltage output for the dac to powered up mode
            # The 1 sets the current output for the dac to powered down mode
            # See page 61 in the data sheet for more info on the COMMON_CONFIG register
            mask = 0b111 << (3*index)
            write = 0b001 << ((3*index)+1)
            self.read_modify_write("COMMON_CONFIG", mask, write)
        else:
            print("Not a valid index.")
            return
        
    def set_dac_current_range(self, current_range: CurrentRange, index):
        """specify a current range for the dac at the provided index 
        
        current_range (string):
        "0": 0 μA to 25 μA,
        "1000000000": 0 μA to 50 μA,
        "10000000000": 0 μA to 125 μA,
        "11000000000": 0 μA to 250 μA,
        "100000000000": 0 μA to -24 μA,
        "101000000000": 0 μA to -48 μA,
        "110000000000": 0 μA to -120 μA,
        "111000000000": 0 μA to -240 μA,
        "1000000000000": -25 μA to +25 μA,
        "1001000000000": -50 μA to +50 μA,
        "1010000000000": -125 μA to +125 μA,
        "1011000000000": -250 μA to +250 μA,
        index (int): the index of the dac we want to specify the current range for
        """
        #Change the current range for the DAC with the index provided. The value provided should be a binary string, one of those listed above. 
        #See page 58 for more info on the DAC_X_IOUT_MISC_CONFIG register
        self.read_modify_write("DAC_" + str(index) + "_IOUT_MISC_CONFIG", 0b1111000000000, current_range.value)
        
    def set_external_reference_voltage(self, new_reference_voltage):
        self.external_reference_voltage = new_reference_voltage
        
    def set_VDD_reference_voltage(self, new_reference_voltage):
        self.VDD_reference_voltage = new_reference_voltage
        
    def set_dac_voltage(self, index, voltage):
        """Set the output for the given index to the given voltage based on the reference voltage

        Args:
            index (int): the index of the dac we want to specify the voltage for
            voltage (int): the voltage we want to set the output to
        """
        setting = self.read_register_by_name("DAC_" + str(index) + "_VOUT_CMP_CONFIG") & 0b1110000000000
        setting = setting >> 10
        reference_voltage = None
        gain = None
        
        if setting == 0b0:
            reference_voltage = self.external_reference_voltage
            gain = 1
        elif setting == 0b001:
            reference_voltage = self.VDD_reference_voltage
            gain = 1
        elif setting == 0b010:
            reference_voltage = self.internal_reference_voltage
            gain = 1.5
        elif setting == 0b011:
            reference_voltage = self.internal_reference_voltage
            gain = 2
        elif setting == 0b100:
            reference_voltage = self.internal_reference_voltage
            gain = 3
        elif setting == 0b101:
            reference_voltage = self.internal_reference_voltage
            gain = 4
        else:
            logging.error("Error - reference voltage setting not recognised (" + str(bin(setting)) + ")")
            return
        if (reference_voltage is not None):
            value_to_write = round(voltage * 4096/(reference_voltage * gain))
            self._set_dac_output(value_to_write, index, False)
        else:
            logging.error("No reference voltage value provided for the current reference voltage setting (Check you have set values for the VDD and external reference inputs).")
    
    def set_dac_current_micro_amps(self, index, current):
        """ Set the current range to an approriate value for the current requested, then calculate the value that needs to be written to get the current we want and write that value.

        Args:
            index (int): the index of the dac we want to set the current for
            current (int): the amount of microamps we want to set the current to
        """
        if (current > 250 or current < -240):
            raise Exception("Invalid current - current must be between -240 and 250.")
        range = None
        value_to_write = None
        #get the range based on the current entered
        if (current > 125):
            range = 0b0011000000000
            value_to_write = math.floor((256* abs(current)/250)+self._250rangeOffset)
        elif (current > 50):
            range = 0b0010000000000
            value_to_write = math.floor((256* abs(current)/125)+self._125rangeOffset)
        elif (current > 25):
            range = 0b0001000000000
            value_to_write = math.floor((256* abs(current)/50)+self._50rangeOffset)
        elif (current > 0):
            range = 0b0000000000000
            value_to_write = math.floor((256* abs(current)/25)+self._25rangeOffset)
        elif (current > -24):
            range = 0b0100000000000
            value_to_write = math.floor((20000* abs(current)/1957)-12)#+13.04241
        elif (current > -48):
            range = 0b0101000000000
            value_to_write = math.floor((2000* abs(current)/391)-13)#+13.16266
        elif (current > -120):
            range = 0b0110000000000
            value_to_write = math.floor((4000* abs(current)/1951)-13)#+13.18298
        elif (current > -240):
            range = 0b0111000000000
            value_to_write = math.floor((10000* abs(current)/9751)-13.1)#+13.1966
            
        if (range is not None):
            self.write_register(self.read_register_address("DAC_" + str(index) + "_IOUT_MISC_CONFIG"), range, True)
            if (value_to_write is not None):
                #write the value to the register
                self._set_dac_output(value_to_write, index, True)
            else:
                raise Exception("Invalid current provided.")
        else:
            raise Exception("Invalid range generation.")
        
        
    def set_dac_voltage_gain(self, voltage_gain: VoltageGain, index):
        """ set the voltage gain for the dac with the provided index
        
        Args: 
            voltage_gain (enum):
                "000": Gain = 1x, external reference on VREF pin,
                "001": Gain = 1x, VDD as reference,
                "010": Gain = 1.5x, internal reference,
                "011": Gain = 2x, internal reference,
                "100": Gain = 3x, internal reference,
                "101": Gain = 4x, internal reference
            index (int): the index of the dac we want to specify the voltage gain for
        """
        #Change the gain for the DAC with the index provided. Gain should be a binary string, one of those listed above. 
        #See page 57 in the manual for more details on the DAC_X_VOUT_CMP_CONFIG register
        self.read_modify_write("DAC_" + str(index) + "_VOUT_CMP_CONFIG", 0b0001110000000000, voltage_gain.value)
    
    def _set_dac_output(self, value, index, current=False):
        """Set the value in the DAC-X-DATA register (where X is the index) to the value provided, changing the current or voltage output based on the value provided
        
        See page 61 in the manual for more info on the DAC_X_DATA register

        Args:
            value (int): an 8 bit if current, or 12 bit if voltage integer detailing the value to write to set the dac output
            index (int): the index of the dac we want to write to
            current (bool, optional): whether we are writing a current value or a voltage value. Defaults to False.
        """
        value = value << 4
        if (current):
            value << 4
        self.read_modify_write("DAC_" + str(index) + "_DATA", 0b1111111111110000, value)
    
    def set_all_dacs_to_voltage(self, gain=VoltageGain.EXT_REF_1x):
        """Switch all dacs into voltage output mode, setting the provided gain for each one

        Args:
            gain (str, optional): gain to set all the voltage outputs to. Defaults to "000".
        """
        #set the gain for each dac, default is EXT_REF_1x which equates to 1x external reference on VREF pin
        self.set_dac_voltage_gain(gain, 0)
        self.set_dac_voltage_gain(gain, 1)
        self.set_dac_voltage_gain(gain, 2)
        self.set_dac_voltage_gain(gain, 3)
        #switch each dac into voltage output mode
        self.put_dac_into_voltage_mode(0)
        self.put_dac_into_voltage_mode(1)
        self.put_dac_into_voltage_mode(2)
        self.put_dac_into_voltage_mode(3)
        
    def set_all_dacs_to_current(self, current_range=CurrentRange.RANGE_0_250):
        """switch all dacs into current output mode and set all their ranges to the provided range

        Args:
            current_range (str, optional): The range all the dacs should use for their current. Defaults to (0-250 microamps)
        """
        #Set the current range for each dac, defaulting to 0010 which equates to 0-250 μA
        self.set_dac_current_range(current_range, 0)
        self.set_dac_current_range(current_range, 1)
        self.set_dac_current_range(current_range, 2)
        self.set_dac_current_range(current_range, 3)
        #Set each dac into current output mode
        self.put_dac_into_current_mode(0, DAC63004.VoltagePowerDownMode.POW_DOWN_HI_Z)
        self.put_dac_into_current_mode(1, DAC63004.VoltagePowerDownMode.POW_DOWN_HI_Z)
        self.put_dac_into_current_mode(2, DAC63004.VoltagePowerDownMode.POW_DOWN_HI_Z)
        self.put_dac_into_current_mode(3, DAC63004.VoltagePowerDownMode.POW_DOWN_HI_Z)
        
        
if __name__ == "__main__":
    u34 = DAC63004(0x48, 3)
    #u34.set_all_dacs_to_voltage()
    #u34.set_all_dacs_to_current(DAC63004.CurrentRange.RANGE_0_250)
    u34.read_all_registers()
    #current = int(input("Enter current "))
    #u34.set_dac_current_micro_amps(1, current)
