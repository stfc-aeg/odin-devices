import time
import spidev
try:
    from struct import unpack
except ImportError:
    from ustruct import unpack

class ThermocoupleType: # pylint: disable=too-few-public-methods
    """An enum-like class representing the different types of thermocouples that the MAX31856 can
    use. The values can be referenced like ``ThermocoupleType.K`` or ``ThermocoupleType.S``
    Possible values are

    - ``ThermocoupleType.B``
    - ``ThermocoupleType.E``
    - ``ThermocoupleType.J``
    - ``ThermocoupleType.K``
    - ``ThermocoupleType.N``
    - ``ThermocoupleType.R``
    - ``ThermocoupleType.S``
    - ``ThermocoupleType.T``

    """
    # pylint: disable=invalid-name
    B = 0b0000
    E = 0b0001
    J = 0b0010
    K = 0b0011
    N = 0b0100
    R = 0b0101
    S = 0b0110
    T = 0b0111
    G8 = 0b1000
    G32 = 0b1100

class Max31856():

    # Register constants
    CR0_REG = 0x00
    CR0_AUTOCONVERT = 0x80
    CR0_1SHOT = 0x40
    CR0_OCFAULT1 = 0x20
    CR0_OCFAULT0 = 0x10
    CR0_CJ = 0x08
    CR0_FAULT = 0x04
    CR0_FAULTCLR = 0x02

    CR1_REG = 0x01
    MASK_REG = 0x02
    CJHF_REG = 0x03
    CJLF_REG = 0x04
    LTHFTH_REG = 0x05
    LTHFTL_REG = 0x06
    LTLFTH_REG = 0x07
    LTLFTL_REG = 0x08
    CJTO_REG = 0x09
    CJTH_REG = 0x0A
    CJTL_REG = 0x0B
    LTCBH_REG = 0x0C
    LTCBM_REG = 0x0D
    LTCBL_REG = 0x0E
    SR_REG = 0x0F

    # fault types
    FAULT_CJRANGE = 0x80
    FAULT_TCRANGE = 0x40
    FAULT_CJHIGH = 0x20
    FAULT_CJLOW = 0x10
    FAULT_TCHIGH = 0x08
    FAULT_TCLOW = 0x04
    FAULT_OVUV = 0x02
    FAULT_OPEN = 0x01

    _BUFFER = bytearray(4)

    def __init__(self, thermocouple_type=ThermocoupleType.K):

        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)

        # baudrate = 50000 polarity = 0 phase = 1, bits_per_word = 8
        self.spi.max_speed_hz = 500000
        self.spi.mode = 1
        self.spi.bits_per_word = 8

        # Assert on any fault
        self._write_u8(self.MASK_REG, 0x0)

        # Configure open circuit faults
        self._write_u8(self.CR0_REG, self.CR0_OCFAULT0)

        # Set thermocouple type
        # Get current valuye of CR1 reg
        conf_reg_1 = self._read_register(self.CR1_REG, 1)[0]
        conf_reg_1 &= 0xF0 # mask off bottom 4 bits
        conf_reg_1 |= int(thermocouple_type) & 0xF
        self._write_u8(self.CR1_REG, conf_reg_1)

    @property
    def temperature(self):
        """The temperature of the sensor and return its value in degrees celsius. (read-only)"""
        self._perform_one_shot_measurement()

        # unpack the 3-byte temperature as 4 bytes
        raw_temp = unpack(">i", self._read_register(self.LTCBH_REG, 3)+bytes([0]))[0]

        # shift to remove extra byte from unpack needing 4 bytes
        raw_temp >>= 8

        # effectively shift raw_read >> 12 to convert pseudo-float
        temp_float = (raw_temp / 4096.0)

        return temp_float

    def _perform_one_shot_measurement(self):

        self._write_u8(self.CJTO_REG, 0x0)
        # read the current value of the first config register
        conf_reg_0 = self._read_register(self.CR0_REG, 1)[0]

        # and the complement to guarantee the autoconvert bit is unset
        conf_reg_0 &= ~self.CR0_AUTOCONVERT
        # or the oneshot bit to ensure it is set
        conf_reg_0 |= self.CR0_1SHOT

        # write it back with the new values, prompting the sensor to perform a measurement
        self._write_u8(self.CR0_REG, conf_reg_0)

        time.sleep(0.250)

    def _read_register(self, address, length, write_value=0):

        end = length + 1
        for i in range(1, end):
            self._BUFFER[i] = write_value
        self._BUFFER[0] = address & 0x7F

        result = bytes((self.spi.xfer2(self._BUFFER[:length+1]))[1:])
        return result

    def _write_u8(self, address, val):

        self._BUFFER[0] = (address | 0x80) & 0xFF
        self._BUFFER[1] = val & 0xFF
        self._write(self._BUFFER, end=2)

    def _write(self, buf, start=0, end=None):

        if not buf:
            return
        if end is None:
            end = len(buf)
        self.spi.writebytes2(buf[start:end])

    def _readinto(self, buf, start=0, end=None, write_value=0):

        if not buf:
            return
        if end is None:
            end = len(buf)

        data = self.spi.xfer([write_value]*(end-start))

        for i in range(end - start):
            buf[start+i] = data[i]

def main():

    max = Max31856()

    try:
        while True:
            print("Thermocouple temperature is {:.1f} C".format(max.temperature))
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
   main()

