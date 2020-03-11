import time
from odin_devices.spi_device import SPIDevice
try:
    from struct import unpack
except ImportError:
    from ustruct import unpack


class ThermocoupleType:  # pylint: disable=too-few-public-methods
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

class Max31856(SPIDevice):
    """Max31856 device class.

    This class implements support for the max31856 device.
    """
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


    def __init__(self, thermocouple_type=ThermocoupleType.K):
        """Initialise the Max31856 device
        """
        SPIDevice.__init__(self, 0, 0)
        # SPI device settings
        self.set_clock_hz(500000)
        self.set_mode(1)
        self.set_bits_per_word(8)
        # All transfers are two bytes. Address, blank for read.
        self.set_buffer_length(2)

        # Assert on any fault
        self.handle_write(self.MASK_REG, 0x0)

        # Configure open circuit faults
        self.handle_write(self.CR0_REG, self.CR0_OCFAULT0)

        # Set thermocouple type
        # Get current value of CR1 reg
        conf_reg_1 = self.handle_transfer(self.CR1_REG, 1)[0]
        conf_reg_1 &= 0xF0  # Mask off bottom 4 bits
        conf_reg_1 |= int(thermocouple_type) & 0xF
        self.handle_write(self.CR1_REG, conf_reg_1)


    @property
    def temperature(self):
        """Read the temperature of the sensor and return its value in degrees celcius."""
        self._perform_one_shot_measurement()

        # Unpack the 3-byte temperature as 4 bytes
        raw_temp = unpack(">i", self.transfer([self.LTCBH_REG, 0x00, 0x00, 0x00])+bytes([0]))[0]
        # Using transfer() directly to bypass self.buffer

        # Shift to remove extra byte from unpack needing 4 bytes
        raw_temp >>= 8

        # Effectively shift raw_read >> 12 to convert pseudo-float
        temp_float = (raw_temp / 4096.0)

        return temp_float


    def _perform_one_shot_measurement(self):
        """Perform a single measurement of temperature."""
        self.handle_write(self.CJTO_REG, 0x0)
        # Read the current value of the first config register
        conf_reg_0 = self.handle_transfer(self.CR0_REG, 1)[0]

        # And the complement to guarantee the autoconvert bit is unset
        conf_reg_0 &= ~self.CR0_AUTOCONVERT
        # Or the oneshot bit to ensure it is set
        conf_reg_0 |= self.CR0_1SHOT

        # Write it back with the new values, prompting the sensor to perform a measurement
        self.handle_write(self.CR0_REG, conf_reg_0)


    def handle_write(self, address, val):
        """Set up the buffer for a write protocol.

        :param address: the provided address to write to.
        :param val: the value to be written.
        """
        # Max device has specific handling for addresses and reads/writes
        # See https://datasheets.maximintegrated.com/en/ds/MAX31856.pdf, p15
        self.buffer[0] = (address | 0x80) & 0xFF
        self.buffer[1] = val & 0xFF
        self.write_bytes(self.buffer, end=2)


    def handle_transfer(self, address):
        """Set up the buffer for transfer protocol.

        Second byte is always blank because nothing is to be written after the address.

        :param address: the provided address to read from.
        """
        self.buffer[0] = address & 0x7F
        self.buffer[1] = 0
        results = bytes(self.transfer(self.buffer)[1:])
        return results


def main():

    max = Max31856()
    print("launching test max")

    try:
        while True:
            print("Thermocouple temperature is {:.1f} C".format(max.temperature))
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()