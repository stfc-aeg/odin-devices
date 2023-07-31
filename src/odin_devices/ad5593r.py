
from odin_devices.i2c_device import I2CDevice, i2c_msg

class AD5593R(I2CDevice):

    ### Keywords :
    AD5593_ALL = 0
    AD5593_ADC = 1
    AD5593_DAC = 2
    AD5593_OUTPUT = 3
    AD5593_INPUT  = 4

    ##### POINTER BYTE CONSTANTS :
    ### Mode bits :
    AD5593_CONFIG_MODE  = 0b0000 << 4
    AD5593_DAC_WRITE    = 0b0001 << 4
    AD5593_ADC_READBACK = 0b0100 << 4
    AD5593_DAC_READBACK = 0b0101 << 4
    AD5593_GPIO_READBACK= 0b0110 << 4
    AD5593_REG_READBACK = 0b0111 << 4

    ### Control Register : (Descriptions from the datasheet)
    AD5593_NOP           = 0b0000 # No operation
    AD5593_ADC_SEQ_REG   = 0b0010 # Selects ADC for conversion (1 byte blank and 1 for the 8 I/Os)
    AD5593_GP_CONTR_REF  = 0b0011 # DAC and ADC control register
    AD5593_ADC_PIN_CONF  = 0b0100 # Selects which pins are ADC inputs
    AD5593_DAC_PIN_CONF  = 0b0101 # Selects which pins are DAC outputs
    AD5593_PULLDOWN_CONF = 0b0110 # Selects which pins have an 85kOhms pull-down resistor to GND
    AD5593_LDAC_MODE     = 0b0111 # Selects the operation of the load DAC
    AD5593_GPIO_W_CONF   = 0b1000 # Selects which pins are general-purpose outputs
    AD5593_GPIO_W_DATA   = 0b1001 # Writes data to general-purpose outputs
    AD5593_GPIO_R_CONF   = 0b1010 # Selects which pins are general-purpose inputs
    AD5593_PWRDWN_REFCONF= 0b1011 # Powers down the DACs and enables/disables the reference
    AD5593_OPENDRAIN_CONF= 0b1100 # Selects open-drain or push-pull for general-purpose outputs
    AD5593_3_STATES_PINS = 0b1101 # Selects which pins are three-stated
    AD5593_SOFT_RESET    = 0b1111 # Resets the AD5593R
    AD5593_BLANK         = 0b00000000

    def __init__(self, address=0x10, **kwargs):
        # Initialise the I2CDevice superclass instance
        I2CDevice.__init__(self, address, **kwargs)
    
    def setup_adc(self, adc_pin_mask):

        # Write ADC pin config register
        reg = self.AD5593_CONFIG_MODE | self.AD5593_ADC_PIN_CONF
        write_msg = i2c_msg.write(self.address, [reg, 0, adc_pin_mask])
        self.bus.i2c_rdwr(write_msg)

        # Write ADC sequence register
        reg = self.AD5593_CONFIG_MODE | self.AD5593_ADC_SEQ_REG
        write_msg = i2c_msg.write(self.address, [reg, 2, adc_pin_mask])
        self.bus.i2c_rdwr(write_msg)

        # Set to ADC readback mode
        reg = self.AD5593_ADC_READBACK
        write_msg = i2c_msg.write(self.address, [reg])
        self.bus.i2c_rdwr(write_msg)

    def read_adc(self, pin):

        # Write ADC sequence register
        reg = self.AD5593_CONFIG_MODE | self.AD5593_ADC_SEQ_REG

        # Set register MSB to enable repeated mode
        msb = 1 << 1

        # Set register LSB to select ADC pin
        lsb = 1 << pin

        # Construct I2C write transaction
        write_msg = i2c_msg.write(self.address, [reg, msb, lsb])

        # Write register
        self.bus.i2c_rdwr(write_msg)

        # Set to ADC readback mode
        reg = self.AD5593_ADC_READBACK
        write_msg = i2c_msg.write(self.address, [reg])
        self.bus.i2c_rdwr(write_msg)

        # Read ADC back and extract value
        read_msg = i2c_msg.read(self.address, 2)
        self.bus.i2c_rdwr(read_msg)
        vals = list(read_msg)
        adc_val = (vals[0] & 0b1111) << 8 | vals[1]

        return adc_val
    
        



