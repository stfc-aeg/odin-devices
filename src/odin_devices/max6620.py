"""MAX6620 class.
    Data sheet: https://www.analog.com/media/en/technical-documentation/data-sheets/max6620.pdf
    Page 14: register map

Jack Santiago
"""

import math

from odin_devices.i2c_device import I2CDevice
import logging
from enum import Enum
from abc import ABC, abstractmethod

class BitMap():
    def __init__(self,  start, length, readonly = False):
        self.start = start
        self.length = length
        self.readonly = readonly
        
class I2CInterface(ABC):
    @abstractmethod
    def setup(self, address, busnum, **kwargs):
        pass

    @abstractmethod
    def write8(self, address, value):
        pass

    @abstractmethod
    def readU8(self, address):
        pass
        
        
class SMBUSInterface(I2CInterface):
    def setup(self, address, busnum, **kwargs):
        self.i2cDevice = I2CDevice(address, busnum, **kwargs)
        
    def write8(self, address, value):
        self.i2cDevice.write8(address, value)
        
    def readU8(self, address):
        return self.i2cDevice.readU8(address)
        

class MAX6620():
    """MAX6620 Fan Controller
    Data sheet: https://www.analog.com/media/en/technical-documentation/data-sheets/max6620.pdf
    Page 14: register map
    """

    device_registers = {
        "CONFIG": {"address": 0x00, "length": 1, "readonly": False, "Bits": {
            "RUNNING": BitMap(7, 1),
            "RESET": BitMap(6, 1),
            "I2CTIMEOUT": BitMap(5, 1),
            "MAXONFAIL": BitMap(4, 1),
            "OSCILLATORMODE": BitMap(3, 1),
        }},
        "FAULT": {"address": 0x01, "length": 1, "readonly": False, "Bits": {
            "FAN4FAULT": BitMap(7, 1, readonly=True),
            "FAN3FAULT": BitMap(6, 1, readonly=True),
            "FAN2FAULT": BitMap(5, 1, readonly=True),
            "FAN1FAULT": BitMap(4, 1, readonly=True),
            "FAN4FAULTMASK": BitMap(3, 1),
            "FAN3FAULTMASK": BitMap(2, 1),
            "FAN2FAULTMASK": BitMap(1, 1),
            "FAN1FAULTMASK": BitMap(0, 1),
        }},
        "FAN1CONFIG": {"address": 0x02, "length": 1, "readonly": False, "Bits": {
            "RPM/DACMODE": BitMap(7, 1),
            "SPINUP": BitMap(5, 2),
            "TACHINPUTENABLED": BitMap(3, 1),
            "TACHORLOCK": BitMap(2, 1),
            "LOCKPOLARITY": BitMap(1, 1),
        }},
        "FAN2CONFIG": {"address": 0x03, "length": 1, "readonly": False, "Bits": {
            "RPM/DACMODE": BitMap(7, 1),
            "SPINUP": BitMap(5, 2),
            "TACHINPUTENABLED": BitMap(3, 1),
            "TACHORLOCK": BitMap(2, 1),
            "LOCKPOLARITY": BitMap(1, 1),
        }},
        "FAN3CONFIG": {"address": 0x04, "length": 1, "readonly": False, "Bits": {
            "RPM/DACMODE": BitMap(7, 1),
            "SPINUP": BitMap(5, 2),
            "TACHINPUTENABLED": BitMap(3, 1),
            "TACHORLOCK": BitMap(2, 1),
            "LOCKPOLARITY": BitMap(1, 1),
        }},
        "FAN4CONFIG": {"address": 0x05, "length": 1, "readonly": False, "Bits": {
            "RPM/DACMODE": BitMap(7, 1),
            "SPINUP": BitMap(5, 2),
            "TACHINPUTENABLED": BitMap(3, 1),
            "TACHORLOCK": BitMap(2, 1),
            "LOCKPOLARITY": BitMap(1, 1),
        }},
        "FAN1DYNAMICS": {"address": 0x06, "length": 1, "readonly": False, "Bits": {
            "SPEEDRANGE": BitMap(5, 3),
            "DACRATEOFCHANGE": BitMap(2, 3),
        }},
        "FAN2DYNAMICS": {"address": 0x07, "length": 1, "readonly": False, "Bits": {
            "SPEEDRANGE": BitMap(5, 3),
            "DACRATEOFCHANGE": BitMap(2, 3),
        }},
        "FAN3DYNAMICS": {"address": 0x08, "length": 1, "readonly": False, "Bits": {
            "SPEEDRANGE": BitMap(5, 3),
            "DACRATEOFCHANGE": BitMap(2, 3),
        }},
        "FAN4DYNAMICS": {"address": 0x09, "length": 1, "readonly": False, "Bits": {
            "SPEEDRANGE": BitMap(5, 3),
            "DACRATEOFCHANGE": BitMap(2, 3),
        }},
        "FAN1TACH": {"address": 0x10, "length": 2, "readonly": True, "Bits": {"TACHCOUNT": BitMap(5, 11, readonly=True),}},
        "FAN2TACH": {"address": 0x12, "length": 2, "readonly": True, "Bits": {"TACHCOUNT": BitMap(5, 11, readonly=True),}},
        "FAN3TACH": {"address": 0x14, "length": 2, "readonly": True, "Bits": {"TACHCOUNT": BitMap(5, 11, readonly=True),}},
        "FAN4TACH": {"address": 0x16, "length": 2, "readonly": True, "Bits": {"TACHCOUNT": BitMap(5, 11, readonly=True),}},
        "FAN1VOLTAGE": {"address": 0x18, "length": 2, "readonly": True, "Bits": {"VOLTAGE": BitMap(7, 9, readonly=True),}},
        "FAN2VOLTAGE": {"address": 0x1A, "length": 2, "readonly": True, "Bits": {"VOLTAGE": BitMap(7, 9, readonly=True),}},
        "FAN3VOLTAGE": {"address": 0x1C, "length": 2, "readonly": True, "Bits": {"VOLTAGE": BitMap(7, 9, readonly=True),}},
        "FAN4VOLTAGE": {"address": 0x1E, "length": 2, "readonly": True, "Bits": {"VOLTAGE": BitMap(7, 9, readonly=True),}},
        "FAN1TARGETTACH": {"address": 0x20, "length": 2, "readonly": False, "Bits": {"TACHCOUNT": BitMap(5, 11),}},
        "FAN2TARGETTACH": {"address": 0x22, "length": 2, "readonly": False, "Bits": {"TACHCOUNT": BitMap(5, 11),}},
        "FAN3TARGETTACH": {"address": 0x24, "length": 2, "readonly": False, "Bits": {"TACHCOUNT": BitMap(5, 11),}},
        "FAN4TARGETTACH": {"address": 0x26, "length": 2, "readonly": False, "Bits": {"TACHCOUNT": BitMap(5, 11),}},
        "FAN1TARGETVOLTAGE": {"address": 0x28, "length": 2, "readonly": False, "Bits": {"VOLTAGE": BitMap(7, 9),}},
        "FAN2TARGETVOLTAGE": {"address": 0x2A, "length": 2, "readonly": False, "Bits": {"VOLTAGE": BitMap(7, 9),}},
        "FAN3TARGETVOLTAGE": {"address": 0x2C, "length": 2, "readonly": False, "Bits": {"VOLTAGE": BitMap(7, 9),}},
        "FAN4TARGETVOLTAGE": {"address": 0x2E, "length": 2, "readonly": False, "Bits": {"VOLTAGE": BitMap(7, 9),}},
    }
        
    def __init__(
        self,
        address,
        busnum,
        i2cInterface: I2CInterface = SMBUSInterface(),
        pulsesPerRev = 2
    ):
        self.i2cInterface = i2cInterface
        self.i2cInterface.setup(address, busnum)
        self.pulsesPerRev = pulsesPerRev
        
    def read_bits(self, name, bits_name, debug=False):
        if name in self.device_registers.keys():
            if bits_name in self.device_registers[name]["Bits"].keys():
                bitMap = self.device_registers[name]["Bits"][bits_name]
                ones = (1 << bitMap.length) - 1
                mask = ones << bitMap.start
                register = self.read_register_by_name(name, debug)
                value = register & mask 
                return value >> bitMap.start
            else:
                raise KeyError("No bits found matching name '" + name + "'.")
        else:
            raise KeyError("No register found matching name '" + name + "'.")
        
    def write_bits(self, name, bits_name, value, debug=False):
        if name in self.device_registers.keys():
            if bits_name in self.device_registers[name]["Bits"].keys():
                bitMap = self.device_registers[name]["Bits"][bits_name]
                if (bitMap.readonly):
                    raise KeyError("Bits '" + bits_name + "' in register '" + name + "' are readonly.")
                if (value < 0):
                    raise OverflowError("Negative values not supported in " + str(bitMap.length) + " bit section '" + bits_name + "' in register '" + name + "'.")
                if value > pow(2, bitMap.length) - 1:
                    raise OverflowError("Value to large for " + str(bitMap.length) + " bit section '" + bits_name + "' in register '" + name + "'.")
                ones = (1 << bitMap.length) - 1
                mask = ones << bitMap.start
                value_to_write = value << bitMap.start
                self.read_modify_write_register(name, value_to_write, mask, debug)
            else:
                raise KeyError("No bits found matching name '" + name + "'.")
        else:
            raise KeyError("No register found matching name '" + name + "'.")

    def read_modify_write_register(self, name, value, mask=0, debug=False):
        """Perform a read-modify-write operation on a register.

        Args:
            register_name (string): Name of the register to modify.
            mask (int): Bit mask specifying the bits to modify.
            value (int): value to write.
        """
        current_value = self.read_register_by_name(name, debug)
        modified_value = (current_value & ~mask) | (value & mask)
        self.write_register_by_name(name, modified_value,debug)

    def write_register_by_name(self, name, value, debug=False):
        """Write a value to a register accessed using the name

        Args:
            name (string): Address of the register to write.
            value (int): value to write to the register.
            debug (bool, optional): If true, print the operation that happened. Used for testing
            and debugging. Defaults to False.
        """
        if name in self.device_registers.keys():
            if not self.device_registers[name]["readonly"]:
                register_address = self.device_registers[name]["address"]
                length = self.device_registers[name]["length"]
                if (value < 0):
                    raise OverflowError("Negative values not supported in register '" + name + "'.")
                if value > pow(2, length * 8) - 1:
                    raise OverflowError("Value to large for " + str(8 * length) + " bit register '" + name + "'.")
                for i in range(0, length):
                    value_section = (value >> (8*i)) & 11111111
                    self.i2cInterface.write8(register_address+i, value_section)
                if debug:
                    logging.debug(
                        "Wrote value "
                        + str(bin(value))
                        + " to register at address "
                        + str(hex(register_address)))  # pragma: no cover
            else:
                raise KeyError("Register '" + name + "' is readonly.")
        else:
            raise KeyError("No register found matching name '" + name + "'.")
        

    def read_register_by_name(self, name, debug=False):
        """Read a value from a register accessed using the name

        Args:
            name (string): name of the register to read from.
            debug (bool, optional): prints the output

        Raises:
            KeyError: If no register is found with a name matching that provided, a KeyError is
            raised as an invalid name was entered.

        Returns:
            int: the value stored in the register that was read
        """
        if name in self.device_registers.keys():
            register_address = self.device_registers[name]["address"]
            length = self.device_registers[name]["length"]
            result = 0
            for i in range(0, length):
                section = self.i2cInterface.readU8(register_address + i)
                result += section << (8*((length-1)-i))
            if debug:
                logging.debug(
                    "Read register at address "
                    + str(hex(register_address))
                    + " as "
                    + str(bin(result))
                )
            return result
        else:
            raise KeyError("No register found matching name '" + name + "'.")
        
        
    def get_running(self, debug = False):
        return not bool(self.read_bits("CONFIG", "RUNNING", debug))
    
    def set_running(self, value, debug = False):
        self.write_bits("CONFIG", "RUNNING", int(not value), debug)
    
    def trigger_reset(self, debug = False):
        self.write_bits("CONFIG", "RESET", 1, debug)
    
    def get_i2c_timeout(self, debug = False):
        return not bool(self.read_bits("CONFIG", "I2CTIMEOUT", debug))
    
    def set_i2c_timeout(self, value, debug = False):
        self.write_bits("CONFIG", "I2CTIMEOUT", int(not value), debug)
    
    def get_fans_max_on_fail(self, debug = False):
        return not bool(self.read_bits("CONFIG", "MAXONFAIL", debug))
    
    def set_fans_max_on_fail(self, value, debug = False):
        self.write_bits("CONFIG", "MAXONFAIL", int(not value), debug)
    
    class OscillatorMode(Enum):
        internal = 0
        external_crystal = 1
    
    def get_oscillator_mode(self, debug = False):
        value = self.read_bits("CONFIG", "OSCILLATORMODE", debug)
        return self.OscillatorMode(value)
    
    def set_oscillator_mode(self, value: OscillatorMode, debug = False):
        self.write_bits("CONFIG", "OSCILLATORMODE", value.value, debug)
        
    
    def get_fault(self, index, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        return bool(self.read_bits("FAULT", "FAN" + str(index) + "FAULTMASK", debug))
    
    def get_fault_mask(self, index, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        return self.read_bits("FAULT", "FAN" + str(index) + "FAULT", debug)
    
    def set_fault_mask(self, index, value, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        self.write_bits("FAULT", "FAN" + str(index) + "FAULT", value, debug)
        
    class RpmDACMode(Enum):
        DAC = 0
        RPM = 1
        
    def get_DAC_mode(self, index, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        value = self.read_bits("FAN" + str(index) + "CONFIG", "RPM/DACMODE", debug)
        return self.RpmDACMode(value)
    
    def set_DAC_mode(self, index, value: RpmDACMode, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        self.write_bits("FAN" + str(index) + "CONFIG", "RPM/DACMODE", value.value, debug)
    
    class SpinUp(Enum):
        NoSpinUp: 0b0
        TwoTachPulsesOrHalfASecond: 0b1
        TwoTachPulsesOr1Second: 0b10
        TwoTachPulsesOr2Seconds: 0b11
    
    def get_spin_up(self, index, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        value = self.read_bits("FAN" + str(index) + "CONFIG", "SPINUP", debug)
        return self.SpinUp(value)
    
    def set_spin_up(self, index, value: SpinUp, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        self.write_bits("FAN" + str(index) + "CONFIG", "SPINUP", value.value, debug)
    
    def get_tach_input_enabled(self, index, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        return bool(self.read_bits("FAN" + str(index) + "CONFIG", "TACHINPUTENABLED", debug))
    
    def set_tach_input_enabled(self, index, value, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        self.write_bits("FAN" + str(index) + "CONFIG", "TACHINPUTENABLED", value, debug)
    
    class TachInputMode(Enum):
        TachCount = 0
        LockedRotor = 1
    
    def get_tach_or_locked_rotor(self, index, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        value = self.read_bits("FAN" + str(index) + "CONFIG", "TACHORLOCK", debug)
        return self.TachInputMode(value)
    
    def set_tach_or_locked_rotor(self, index, value: TachInputMode, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        self.write_bits("FAN" + str(index) + "CONFIG", "TACHORLOCK", value.value, debug)
    
    class Polarity(Enum):
        Low = 0
        High = 1
        
    def get_locked_rotor_polarity(self, index, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        value = self.read_bits("FAN" + str(index) + "CONFIG", "LOCKPOLARITY", debug)
        return self.Polarity(value)
    
    def set_locked_rotor_polarity(self, index, value: Polarity, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        self.write_bits("FAN" + str(index) + "CONFIG", "LOCKPOLARITY", value.value, debug)
        
    def tach_period_to_speed_range(self, value):
        return math.log2(value)
        
    def speed_range_to_tach_period(self, value):
        value = min(value, 0b101)
        return pow(2, value)
    
    def get_speed_range(self, index, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        value = self.read_bits("FAN" + str(index) + "DYNAMICS", "SPEEDRANGE", debug)
        return self.speed_range_to_tach_period(value)
        
    def set_speed_range(self, index, value, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        self.write_bits("FAN" + str(index) + "DYNAMICS", "SPEEDRANGE", self.tach_period_to_speed_range(value), debug)
    
    class VoltageIncrement(Enum):
        _0 = 0b0
        _0_015625 = 0b1
        _0_03125 = 0b10
        _0_0625 = 0b11
        _0_125 = 0b100
        _0_25 = 0b101
        _0_5 = 0b110
        _1 = 0b111
    
    def get_DAC_rate_of_change(self, index, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        value = self.read_bits("FAN" + str(index) + "DYNAMICS", "DACRATEOFCHANGE", debug)
        return self.VoltageIncrement(value)
    
    def set_DAC_rate_of_change(self, index, value: VoltageIncrement, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        self.write_bits("FAN" + str(index) + "DYNAMICS", "DACRATEOFCHANGE", value.value, debug)
    
    def get_tach(self, index, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        value = self.read_bits("FAN" + str(index) + "TACH", "TACHCOUNT", debug)
        return value
    
    def get_voltage(self, index, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        value = self.read_bits("FAN" + str(index) + "VOLTAGE", "VOLTAGE", debug)
        return value
    
    def get_target_tach(self, index, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        value = self.read_bits("FAN" + str(index) + "TARGETTACH", "TACHCOUNT", debug)
        return value
    
    def set_target_tach(self, index, value, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        self.write_bits("FAN" + str(index) + "TARGETTACH", "TACHCOUNT", value, debug)
        
    def get_target_voltage(self, index, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        value = self.read_bits("FAN" + str(index) + "TARGETVOLTAGE", "VOLTAGE", debug)
        return value
    
    def set_target_voltage(self, index, value, debug=False):
        if (index < 1 or index > 4):
            raise IndexError("Fan index " + str(index) + " is not a valid index (1-4)")
        self.write_bits("FAN" + str(index) + "TARGETVOLTAGE", "VOLTAGE", value, debug) 

    def getRequiredSpeedRange(self, rpm):
        speedRanges = [1, 2, 4, 8, 16, 32]
        bestSpeedRange = -1
        bestTachCount = -1
        for speedRange in speedRanges:
            tachCount = (491520 * speedRange) / (self.pulsesPerRev * rpm)
            if (tachCount < 2047 and tachCount > bestTachCount):
                bestSpeedRange = speedRange
                bestTachCount = tachCount

        return bestSpeedRange  
        
    def get_rpm(self, index, debug=False):
        speedRange = self.get_speed_range(index, debug)
        tachCount = self.get_tach(index, debug)

        return (491520 * speedRange) / (self.pulsesPerRev * tachCount)
        
    def get_target_rpm(self, index, debug=False):
        speedRange = self.get_speed_range(index, debug)
        tachCount = self.get_target_tach(index, debug)

        return (491520 * speedRange) / (self.pulsesPerRev * tachCount)
        
    def set_target_rpm(self, index, value, debug=False):
        speedRange = self.getRequiredSpeedRange(value)
        self.set_speed_range(index, speedRange, debug)

        tachCount = (491520 * speedRange) / (self.pulsesPerRev * value)
        if (tachCount > 511):
            tachCount = 511
        tachCount = round(tachCount)
        
        self.write_bits("FAN" + str(index) + "TARGETTACH", "TACHCOUNT", tachCount, debug)
