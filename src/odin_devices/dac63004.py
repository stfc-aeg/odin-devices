"""ADAC63004 class.
    Data sheeet: https://www.ti.com/product/DAC63004
    Page 54: register map

Adam Davis, STFC Application Engineering Group.
"""

from odin_devices.i2c_device import I2CDevice
import logging
import math

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

    def __init__(self, address, busnum, **kwargs):
        I2CDevice.__init__(self, address, busnum, **kwargs)

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
        Write a 16-bit value to a register.

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
            
    def read_register(self, register_address, flipped=False, debug=True):
        """
        Read a 16-bit value from a register.

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
            #Convert the value to binary
            value = str(bin(value)).replace("0b", "")
            #make sure the value is 16 bits long
            while (len(value) < 16):
                value = "0" + value
            #flip the first and last 8 bits around
            value = value[8:] + value[:8]
            #write the flipped value
            self.bus.write_word_data(self.address, reg, int("0b" + value, 2))
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
            result = self.bus.read_word_data(self.address, reg)
            #convert the read value to binary
            result = str(bin(result)).replace("0b", "")
            #make sure the read value is 16 bits long
            while (len(result) < 16):
                result = "0" + result
            #flip the first and last 8 bits around
            result = result[8:] + result[:8]
            #convert the result back to denary
            return int("0b" + result, 2)
        except IOError as err:
            logging.error("--------------------------------------------------")
            logging.error("Error: " + str(err))
            logging.error("Read16 failed to read value from register " + str(hex(reg)))
            logging.error("--------------------------------------------------")
            return -1

    def set_dac_as_current(self, index, voltagePowerDown="11"):
        """ Set the dac at the provided index into current output mode, powering down the voltage mode in the method specified
        
        voltagePowerDown (string):
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
            mask = "0000" + ("000" * (3-index)) + "111" + ("000" * index)
            write = "0000" + ("000" * (3-index)) + voltagePowerDown + "0" + ("000" * index)
            self.read_modify_write("COMMON_CONFIG", int(mask, 2), int(write, 2))
        else:
            print("Not a valid index.")
            return
        
    def set_dac_as_voltage(self, index):
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
            mask = "0000" + ("000" * (3-index)) + "111" + ("000" * index)
            write = "0000" + ("000" * (3-index)) + "001" + ("000" * index)
            self.read_modify_write("COMMON_CONFIG", int(mask, 2), int(write, 2))
        else:
            print("Not a valid index.")
            return
        
    def set_dac_current_range(self, current_range, index):
        """specify a current range for the dac at the provided index 
        
        current_range (string):
        "0000": 0 μA to 25 μA,
        "0001": 0 μA to 50 μA,
        "0010": 0 μA to 125 μA,
        "0011": 0 μA to 250 μA,
        "0100": 0 μA to -24 μA,
        "0101": 0 μA to -48 μA,
        "0110": 0 μA to -120 μA,
        "0111": 0 μA to -240 μA,
        "1000": -25 μA to +25 μA,
        "1001": -50 μA to +50 μA,
        "1010": -125 μA to +125 μA,
        "1011": -250 μA to +250 μA,
        index (int): the index of the dac we want to specify the current range for
        """
        #Change the current range for the DAC with the index provided. The value provided should be a binary string, one of those listed above. 
        #See page 58 for more info on the DAC_X_IOUT_MISC_CONFIG register
        self.read_modify_write("DAC_" + str(index) + "_IOUT_MISC_CONFIG", 0b0001111000000000, int(current_range + "000000000", 2))
        
    def set_dac_voltage(self, index, voltage, referenceVoltage):
        """Set the output for the given index to the given voltage based on the reference voltage

        Args:
            index (int): the index of the dac we want to specify the voltage for
            voltage (int): the voltage we want to set the output to
            referenceVoltage (int): the reference voltage being used by the dac
        """
        value_to_write = voltage*4096/referenceVoltage 
        self.set_dac_output(str(bin(value_to_write)).replace("0b", ""), index, False)
    
    def set_dac_current_micro_amps(self, index, current):
        """ Set the current range to an approriate value for the current requested, then calculate the value that needs to be written to get the current we want and write that value.

        Args:
            index (int): the index of the dac we want to set the current for
            current (int): the amount of microamps we want to set the current to
        """
        if (current > 250 or current < -240):
            raise Exception("Invalid current - current must be between -240 and 250.")
        range = "0000"
        #get the range either based on the current entered
        set_current = "0000"
        if (current > 125):
            set_current = "0011"
        elif (current > 50):
            set_current = "0010"
        elif (current > 25):
            set_current = "0001"
        elif (current > 0):
            set_current = "0000"
        elif (current > -24):
            set_current = "0100"
        elif (current > -48):
            set_current = "0101"
        elif (current > -120):
            set_current = "0110"
        elif (current > -240):
            set_current = "0111"
        elif (current > -250):
            set_current = "1011"
        self.write_register(self.read_register_address("DAC_" + str(index) + "_IOUT_MISC_CONFIG"), int(set_current + "000000000", 2), True)
        range = set_current
        #make the current value positive since the range determines whether the output is negative or positive
        current = abs(current)
        value_to_write = "-1"
        #calculate the value that needs to be written based on the range being used
        #0-25
        if range == "0000":
            value_to_write = math.floor((256*current/25)+self._25rangeOffset)
        #0-50
        elif range == "0001":
            value_to_write = math.floor((256*current/50)+self._50rangeOffset)
        #0-125
        elif range == "0010":
            value_to_write = math.floor((256*current/125)+self._125rangeOffset)
        #0-250
        elif range == "0011":
            value_to_write = math.floor((256*current/250)+self._250rangeOffset)
        #0- -24
        elif range == "0100":
            value_to_write = math.floor((20000*current/1957)-12)#+13.04241
        #0- -48
        elif range == "0101":
            value_to_write = math.floor((2000*current/391)-13)#+13.16266
        #0- -120
        elif range == "0110":
            value_to_write = math.floor((4000*current/1951)-13)#+13.18298
        #0- -240
        elif range == "0111":
            value_to_write = math.floor((10000*current/9751)-13.1)#+13.1966
        if (value_to_write != "-1"):
            #write the value to the register
            self.set_dac_output(str(bin(value_to_write)).replace("0b", ""), index, True)
        else:
            raise Exception("Invalid range provided.")
        
    def set_dac_voltage_gain(self, voltage_gain, index):
        """ set the voltage gain for the dac with the provided index
        
        Args: 
            voltage_gain (string):
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
        self.read_modify_write("DAC_" + str(index) + "_VOUT_CMP_CONFIG", 0b0001110000000000, int(voltage_gain + "0000000000", 2))
    
    def set_dac_output(self, value, index, current=False):
        """Set the value in the DAC-X-DATA register (where X is the index) to the value provided, changing the current or voltage output based on the value provided
        
        See page 61 in the manual for more info on the DAC_X_DATA register

        Args:
            value (string): a 12 bit if current, or 8 bit if voltage binary string detailing the value to write to set the dac output
            index (int): the index of the dac we want to write to
            current (bool, optional): whether we are writing a current value or a voltage value. Defaults to False.
        """
        value = value + "0000"
        if (current):
            value = value + "0000"
        self.read_modify_write("DAC_" + str(index) + "_DATA", 0b1111111111110000, int(value, 2))
    
    def set_all_dacs_to_voltage(self, gain="000"):
        """Switch all dacs into voltage output mode, setting the provided gain for each one

        Args:
            gain (str, optional): gain to set all the voltage outputs to. Defaults to "000".
        """
        #set the gain for each dac, default is 000 which equates to 1x external reference on VREF pin
        u34.set_dac_voltage_gain(gain, 0)
        u34.set_dac_voltage_gain(gain, 1)
        u34.set_dac_voltage_gain(gain, 2)
        u34.set_dac_voltage_gain(gain, 3)
        #switch each dac into voltage output mode
        u34.set_dac_as_voltage(0)
        u34.set_dac_as_voltage(1)
        u34.set_dac_as_voltage(2)
        u34.set_dac_as_voltage(3)
        
    def set_all_dacs_to_current(self, current_range="0011"):
        """switch all dacs into current output mode and set all their ranges to the provided range

        Args:
            current_range (str, optional): The range all the dacs should use for their current. Defaults to "0011" (0-250 microamps)
        """
        #Set the current range for each dac, defaulting to 0010 which equates to 0-250 μA
        u34.set_dac_current_range(current_range, 0)
        u34.set_dac_current_range(current_range, 1)
        u34.set_dac_current_range(current_range, 2)
        u34.set_dac_current_range(current_range, 3)
        #Set each dac into current output mode
        u34.set_dac_as_current(0)
        u34.set_dac_as_current(1)
        u34.set_dac_as_current(2)
        u34.set_dac_as_current(3)
        
if __name__ == "__main__":
    u34 = DAC63004(0x47, 3)
    u34.set_all_dacs_to_current()
    u34.read_all_registers()     
