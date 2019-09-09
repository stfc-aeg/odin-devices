"""AD5272 - device access class for the AD5272 I2C potentiometer

Provides access to control the wiper positions for the AD5272 device with
helper methods to set potential differences and resistances in potential
divider and rheostat mode respectively.

Adam Davis, STFC Application Engineering Group.
"""

from i2c_device import I2CDevice, I2CException

class AD5272(I2CDevice):
    #AD5272 class.
    #
    #This class implements support to set the resistance across the digital potentiometer
    #

    def __init__(self, address=0x2F, **kwargs):
        #Initialise the AD5272 device.
        #:param address: The address of the AD5272 default: 0x2F when ADDR=0, 2E when ADD= FLOAT (see schematics)
        #

        I2CDevice.__init__(self, address, **kwargs)
	self.write8(0x1C, 0x02) # enable the update of wiper position by default

        #Read back current wiper settings
        self.write8(0x08, 0x00) # Have to write code 0x0800 to initiate a read of the wiper 
        tmp=self.readU16(0) # read the result into tmp variable
        self.__wiper_pos = ((tmp&0x03) << 8) + ((tmp&0xFF00) >> 8) #mask off lower 8 bits and shift down 8, mask off upper 8 bits and bits 7-2 & shift up 8
	
        #read the contents of the control register
        #0x1 = 50-TP program enable 0 = default, dissable
        #0x2 = RDAC register write protect 0 = default, wiper position frozen, 1 = allow update via i2c
        #0x4 = Resistance performance enable 0 = default = enabled, 1 = dissbale
        #0x8 = 50-TP memory program success bit 0 = default = unsuccessful, 1 = successful
        
        #send the command to read the contents of the control register
        self.write8(0x20, 0x00) #send the command to read the contents of the control register
        
        # when read, byte swap to get register contents
        self.__control_reg = (self.readU16(0)&0xF00 >> 8) 


        #Internal variable settings depending on device / voltage connections
        self.__num_wiper_pos = 1024
        self.__tot_resistance = 100.0
        self.__low_pd = 0.0
        self.__high_pd = 3.3


    def set_total_resistance(self, resistance):
        #Sets the total resistance across the potentiometer for set_resistance()
        #:param resistance: Total resistance between H- and L- (Kiloohms)
        #

        self.__tot_resistance = float(resistance)

    def set_num_wiper_pos(self, positions):
        #Sets the number of write positions
        #:param resistance: Total resistance between H- and L- (Kiloohms)
        #

        self.__num_wiper_pos = int(positions)



    def set_resistance(self, resistance):
        #Sets the resistance of a given wiper in rheostat mode (see datasheet)
        #:param wiper: Wiper to set 0=A, 1=B
        #:param resistance: Desired resistance between H- and W- (Kiloohms)
        #

        if resistance < 0 or resistance > self.__tot_resistance:
            raise I2CException("Select a resistance between 0 and {:.2f}".format(self.__tot_resistance))

        self.__wiper_pos = int(resistance / self.__tot_resistance * self.__num_wiper_pos)
        self.write8(((self.__wiper_pos & 0xFF00) + 0x400)>>8, (self.__wiper_pos & 0xFF))


    def set_terminal_PDs(self, wiper, low, high):
        #Sets the potential difference for H- and L- on a given wiper for set_PD()
        #:param wiper: Wiper to set 0=A, 1=B
        #:param low: Low PD (Volts)
        #:param high: High PD (Volts)
        #

        self.__low_pd[wiper] = float(low)
        self.__high_pd[wiper] = float(high)

    def set_PD(self, pd):
        #Sets the potential difference of a given wiper in potential divider mode (see datasheet)
        #:param wiper: Wiper to set 0=A, 1=B
        #:param pd: Target potential difference (Volts)
        #

        self.__wiper_pos[wiper] = int((pd - self.__low_pd) / (self.__high_pd - self.__low_pd) * self.__wiper_pos)
	self.write8(((self.__wiper_pos & 0xFF00) + 0x400)>>8, (self.__wiper_pos & 0xFF))

    def set_wiper(self, position):
        #Manually sets a wiper position
        #:param wiper: Wiper to set 0=A, 1=B
        #:param position: Target position [0-255]
        #

        self.__wiper_pos = int(position)
	self.write8(((self.__wiper_pos & 0xFF00) + 0x400)>>8, (self.__wiper_pos & 0xFF))

    def get_wiper(self, force=False):
        #Gets a wiper position
  	#:param: 
        #:returns: Current position [0-255]
        #

        if force:
	    self.write8(0x08, 0x00) # Have to write code 0x8000 to initiate a read of the wiper 
	    tmp=self.readU16(0) # read the result into tmp variable
            self.__wiper_pos = ((tmp&0x03) << 8) + ((tmp&0xFF00) >> 8)

        return self.__wiper_pos


    def enable_50TP(self, enable):
        #Sets whether one can transfer the current RDAC setting to the memory

        if enable: self.write8(0x1C, self.__control_reg | 0x1)
        else: self.write8(0x1C, self.__control_reg & 0x6)


    def store_50TP(self, enable):
        #stores the current RDAC value in the 50TP memory locations
        #
        if enable :
            self.write8(0x0C, 0x00) # move the contents of the RDAC register to the memory
            tmp=self.readU16(0) # read the result into tmp variable
            return (((tmp&0x03) << 8) + ((tmp&0xFF00) >> 8))


    def set_shutdown(self, enable):
        #Sets whether to use shutdown mode
        #:param enable: true - device enters shutdown mode, false - normal operation
        #

        if enable: self.write8(0x24, 0x1)
        else: self.write8(0x24, 0x0)
