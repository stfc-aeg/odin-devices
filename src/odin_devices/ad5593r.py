
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
    AD5593_GP_CONTR_REG  = 0b0011 # DAC and ADC control register
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

    def __init__(self, busnum= 0, address=0x10, vref=2.5, **kwargs):
        # Initialise the I2CDevice superclass instance
        I2CDevice.__init__(self, address, busnum, **kwargs)

        # Internal voltage reference is 2.5v, but is disabled by default
        self._vref = vref

    def setup_adc(self, adc_pin_mask, double_range=False):
        # double_range is a global ADC setting that allows the ADC to read inputs in
        # the range 0v - (2*vref)v

        # Get old value of general purpose config register
        reg = self.AD5593_REG_READBACK | self.AD5593_GP_CONTR_REG
        write_msg = i2c_msg.write(self.address, [reg])
        read_msg = i2c_msg.read(self.address, 2)
        self.execute_transaction(write_msg, read_msg)
        old_gp_reg = list(read_msg)

        # Substitute in the double range bit
        adc_range_bit = 0b100000 if double_range else 0
        new_gp_reg = [old_gp_reg[0], (old_gp_reg[1] & 0b11100000) | adc_range_bit]

        # Write the new general purpose config register
        reg = self.AD5593_CONFIG_MODE | self.AD5593_GP_CONTR_REG
        write_msg = i2c_msg.write(self.address, [reg, new_gp_reg[0], new_gp_reg[1]])
        self.execute_transaction(write_msg)

        self._adc_double_range = double_range

        # Write ADC pin config register
        reg = self.AD5593_CONFIG_MODE | self.AD5593_ADC_PIN_CONF
        write_msg = i2c_msg.write(self.address, [reg, 0, adc_pin_mask])
        self.execute_transaction(write_msg)

        # Write ADC sequence register
        reg = self.AD5593_CONFIG_MODE | self.AD5593_ADC_SEQ_REG
        write_msg = i2c_msg.write(self.address, [reg, 2, adc_pin_mask])
        self.execute_transaction(write_msg)

        # Set to ADC readback mode
        reg = self.AD5593_ADC_READBACK
        write_msg = i2c_msg.write(self.address, [reg])
        self.execute_transaction(write_msg)

    def read_adc_raw(self, pin):

        # Write ADC sequence register
        reg = self.AD5593_CONFIG_MODE | self.AD5593_ADC_SEQ_REG

        # Set register MSB to enable repeated mode
        msb = 1 << 1

        # Set register LSB to select ADC pin
        lsb = 1 << pin

        # Construct I2C write transaction
        write_msg = i2c_msg.write(self.address, [reg, msb, lsb])

        # Write register
        self.execute_transaction(write_msg)

        # Set to ADC readback mode
        reg = self.AD5593_ADC_READBACK
        write_msg = i2c_msg.write(self.address, [reg])
        self.execute_transaction(write_msg)

        # Read ADC back and extract value
        read_msg = i2c_msg.read(self.address, 2)
        self.execute_transaction(read_msg)
        vals = list(read_msg)
        adc_val = (vals[0] & 0b1111) << 8 | vals[1]

        return adc_val

    def read_adc(self, pin):
        # Actual voltage will depend on the reference, and whether ADC is using double
        # refeference range.
        adc_count = self.read_adc_raw(pin)

        range_multiplier = 2 if self._adc_double_range else 1
        voltage = (adc_count / 4095) * self._vref * range_multiplier

        return voltage

    def setup_dac(self, dac_pin_mask, double_range=False):
        # double_range is a global setting that allows the DAC to set voltages in the
        # range 0v -(2*vref)v

        # Note that it is allowed to set I/On as ADC and DAC to readback the DAC output.

        # Get old value of general purpose config register
        reg = self.AD5593_REG_READBACK | self.AD5593_GP_CONTR_REG
        write_msg = i2c_msg.write(self.address, [reg])
        read_msg = i2c_msg.read(self.address, 2)
        self.execute_transaction(write_msg, read_msg)
        old_gp_reg = list(read_msg)

        # Substitute in the double range bit
        dr_bit = 0b10000 if double_range else 0
        new_gp_reg = [old_gp_reg[0], (old_gp_reg[1] & 0b11100000) | dr_bit]

        # Write the new general purpose config register
        reg = self.AD5593_CONFIG_MODE | self.AD5593_GP_CONTR_REG
        write_msg = i2c_msg.write(self.address, [reg, new_gp_reg[0], new_gp_reg[1]])
        self.execute_transaction(write_msg)

        self._dac_double_range = double_range

        # Write DAC pin config register
        reg = self.AD5593_CONFIG_MODE | self.AD5593_DAC_PIN_CONF
        write_msg = i2c_msg.write(self.address, [reg, 0, dac_pin_mask])
        self.execute_transaction(write_msg)

    def set_dac(self, pin, voltage):

        # max voltage depends on whether range is double or not
        max_voltage = (self._vref * 2) if self._dac_double_range else self._vref

        # Check input is in range
        if voltage < 0 or voltage > max_voltage:
            raise Exception('Voltage {}v is out of range ({}v-{}v)'.format(
                voltage, 0, max_voltage))

        # Calculate decimal DAC setting
        dac_input = int(((voltage / max_voltage) * 4095)) & 0xFFF

        # Select the pin for DAC write
        reg = self.AD5593_DAC_WRITE | pin

        # DAC write register is 12-bit MSB and LSB combined
        msb = (dac_input >> 8) & 0xF
        lsb = (dac_input) & 0xFF

        # Construct I2C write transaction
        write_msg = i2c_msg.write(self.address, [reg, msb, lsb])

        # Write register
        self.execute_transaction(write_msg)

    def enable_internal_reference(self):
        # Get old value of power config register
        reg = self.AD5593_REG_READBACK | self.AD5593_PWRDWN_REFCONF
        write_msg = i2c_msg.write(self.address, [reg])
        read_msg = i2c_msg.read(self.address, 2)
        self.execute_transaction(write_msg, read_msg)
        old_pd_reg = list(read_msg)

        # Substitute in the internal reference enable
        ir_bit = 0b00000010
        new_pd_reg = [(old_pd_reg[0] & 0b11111011) | ir_bit, old_pd_reg[1]]

        # Write the new general purpose config register
        reg = self.AD5593_CONFIG_MODE | self.AD5593_PWRDWN_REFCONF
        write_msg = i2c_msg.write(self.address, [reg, new_pd_reg[0], new_pd_reg[1]])
        self.execute_transaction(write_msg)

        self._vref = 2.5
