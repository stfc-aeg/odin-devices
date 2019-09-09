""" AD5694 Driver class, implements read/write access 
for the four DACs on the AD5694 chip 

Sophie Kirkham,  STFC Application Engineering Group

updated by Adam Davis to make more generic
"""

WRITE_UPDATE = 0x30

from odin_devices.i2c_device import I2CDevice, I2CException 

class ad5694(I2CDevice):

    def __init__(self, address, **kwargs):

        I2CDevice.__init__(self, address, **kwargs)
        self.address = address
	#addresses of the 4 DACs
        self.dacs = [0x01, 0x02, 0x04, 0x08]
	#store dac values to minimise i2c traffic	
        self.dac_values = [0x00, 0x00, 0x00, 0x00]
    #store 
        self.dac_mult = [0.0004, 0.1, 0.1, 0.00002]

    def set_up(self):
	""" Sets up the dac values readings,
	reads the raw i2c value from dac 1 (fine) and dac 4 (coarse)
	"""
	self.dac_values[0] = self.read_dac_value(1, True)
        self.dac_values[3] = self.read_dac_value(4, True)

    def set_multiplier(self, dac, value):
        """Allows the multiplier to be set"""
        self.dac_mult[dac-1]= value

    def set_from_voltage(self, dac, voltage):
	""" sets the dac i2c value from a voltage
	@param dac : the dac number to set
	@param voltage : the voltage value to use
	""" 
        if dac == 1:
            value = voltage / self.dac_mult[dac-1]
            self.set_from_value(dac, int(value))

        elif dac == 4:
            value = voltage / self.dac_mult[dac-1]
            self.set_from_value(dac, int(value))
        else:
            raise I2CException("Choose DAC 1 or 4, 2/3 not currently implemented")    
   
    def set_from_value(self, dac, value):
	""" sets the raw i2c dac value from an i2c value
	@param dac : the dac to set
	@param value : the value to set
	"""	
        bytearray = [0x00, 0x00]
        data = (value & 0xFFFF) << 4
        bytearray[0] = (data & 0xFFFF) >> 8
        bytearray[1] = (data & 0x00FF)
        self.writeList(WRITE_UPDATE + self.dacs[dac-1], bytearray)

    def read_dac_voltage(self, dac):
	""" reads the dac value and returns it as a voltage
	@param dac : the dac to set
	"""
        if dac == 1:
            return (self.read_dac_value(dac) * self.dac_mult[dac-1])
        elif dac == 4:
            return (self.read_dac_value(dac) * self.dac_mult[dac-1])
        else:
            raise I2CException("Choose DAC 1 or 4, 2/3 not currently implemented")

    def read_dac_value(self, dac):
        """ returns the dac value, if force - performs a new i2c read
	@param dac : the dac to read from
	@param force : boolean flag to determine whether to perform a new read
	"""

        result = [0x00, 0x00]
        byte1, byte2 =  self.readList(WRITE_UPDATE + self.dacs[dac-1], 2)
        self.dac_values[dac-1] = (((byte1 & 0xFF) << 8) + byte2) >> 4	
        return self.dac_values[dac-1] 
