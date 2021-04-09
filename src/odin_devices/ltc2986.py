# Support:
# - [x] RTDs
# - [ ] Custom RTDs
# - [ ] Thermocouples
# - [ ] Custom Thermocouples
# - [ ] Thermistors
# - [ ] Custom Thermistors
# - [ ] Diodes

from odin_devices.spi_device import SPIDevice
from enum import Enum
import time

_SPI_CMD_WRITE_RAM = bytes([0x02])
_SPI_CMD_READ_RAM = bytes([0x03])

_CH1_TEMP_RESULT_ADDRESS = 0x0010
_CH1_ASSIGNMENT_ADDRESS = 0x0200

_REG_COMMAND_STATUS = 0x0000
_REG_MULTIPLE_CONVERSION_MASK = 0x00F6

_CONVERSION_CONTROL_BYTE = 0x80

_SENSOR_TYPE_LSB = 27

_RTD_RSENSE_CHANNEL_LSB = 22
_RTD_NUM_WIRES_LSB = 20
_RTD_EXCITATION_MODE_LSB = 18
_RTD_EXCITATION_CURRENT_LSB = 14
_RTD_CURVE_LSB = 12

def _OR_Bytes(bytesa, bytesb):
    return bytes([x | y for x, y in zip(bytesa, bytesb)])

class LTC2986 (SPIDevice):
    """
    All Sensor Types:
    """
    class Sensor_Type (Enum):
        SENSOR_TYPE_NONE = (0x0 << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')

        SENSOR_TYPE_RTD_PT10 = (0xA << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')
        SENSOR_TYPE_RTD_PT50 = (0xB << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')
        SENSOR_TYPE_RTD_PT100 = (0xC << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')
        SENSOR_TYPE_RTD_PT200 = (0xD << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')
        SENSOR_TYPE_RTD_PT500 = (0xE << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')
        SENSOR_TYPE_RTD_PT1000 = (0xF << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')
        SENSOR_TYPE_RTD_PT1000_375 = (0x10 << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')
        SENSOR_TYPE_RTD_NI120 = (0x11 << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')
        SENSOR_TYPE_RTD_CUSTOM = (0x12 << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')

        SENSOR_TYPE_SENSE_RESISTOR = (0x1D << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')
        SENSOR_TYPE_ACTIVE_ANALOG = (0x1F << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')

        SENSOR_TYPE_DIRECT_ADC = (0x1E << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')

        # TODO Add Thermistors

        # TODO Add Thermocouples

        SENSOR_TYPE_OFF_CHIP_DIODE = (0x1C << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')

    """
    RTD Config Values:
    | Bit        | 31 30 29 28 27 | 26 25 24 23 22 | 21 20     | 19 18           |
    | ---------- | -------------- | -------------- | --------- | --------------- |
    | RTD Config | RTD Type       | RSense Channel | Num Wires | Excitation Mode |

                 | 17 16 15 14        | 13 12 | 11 10 9 8 7 6  | 5 4 3 2 1 0   |
                 | ------------------ | ----- | -------------- | ------------- |
                 | Excitation Current | Curve | Custom Address | Custom length |
    """
    class RTD_RSense_Channel (Enum):
        CHANNEL_NONE = (0x00 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CHANNEL_1 = (0x01 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CHANNEL_2 = (0x02 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CHANNEL_3 = (0x03 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CHANNEL_4 = (0x04 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CHANNEL_5 = (0x05 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CHANNEL_6 = (0x06 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CHANNEL_7 = (0x07 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CHANNEL_8 = (0x08 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CHANNEL_9 = (0x09 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CHANNEL_10 = (0x0A << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')

    class RTD_Standard (Enum):
        EUROPEAN = (0x00 << _RTD_CURVE_LSB).to_bytes(4, byteorder='big')
        AMERICAN = (0x01 << _RTD_CURVE_LSB).to_bytes(4, byteorder='big')
        JAPANESE = (0x02 << _RTD_CURVE_LSB).to_bytes(4, byteorder='big')
        ITS_90 = (0x03 << _RTD_CURVE_LSB).to_bytes(4, byteorder='big')

    class RTD_Excitation_Current (Enum):
        EXTERNAL = 0x00
        CURRENT_5UA = 0x01
        CURRENT_10UA = 0x02
        CURRENT_25UA = 0x03
        CURRENT_50UA = 0x04
        CURRENT_100UA = 0x05
        CURRENT_250UA = 0x06
        CURRENT_500UA = 0x07
        CURRENT_1MA = 0x08

    class RTD_Excitation_Mode (Enum):
        NO_ROTATION_NO_SHARING = 0x00
        NO_ROTATION_SHARING = 0x01
        ROTATION_SHARING = 0x02

    class RTD_Num_Wires (Enum):
        NUM_2_WIRES = 0x00
        NUM_3_WIRES = 0x01
        NUM_4_WIRES = 0x02
        NUM_4_WIRES_KELVIN_RSENSE = 0x03

    def __init__(self, bus=0, device=0):

        # Init SPI Device
        super(self).__init__(bus, device)

    def _transfer_ram_bytes(self, read, start_address, io_bytes):

        # Check address is valid
        # TODO

        # Construct packet for transfer
        input_data = bytearray()
        if read:
            input_data.extend(_SPI_CMD_READ_RAM)
        else:
            input_data.extend(_SPI_CMD_WRITE_RAM)
        input_data.extend(start_address.to_bytes(2, byteorder='big'))
        input_data.extend(io_bytes)

        # Get raw output data and strip prefix
        output_data = self.transfer(input_data)[3:]

        return output_data

    def _read_ram_bytes(self, start_address, num_bytes):
        io_bytes = bytes(num_bytes)
        return self._transfer_ram_bytes(read=True,
                                        start_address=start_address,
                                        io_bytes=io_bytes)

    def _write_ram_bytes(self, start_address, io_bytes):
        self._transfer_ram_bytes(read=False,
                                 start_address=start_address,
                                 io_bytes=io_bytes)

    def _get_channel_assignment_address(self, channel_number):
        return _CH1_ASSIGNMENT_ADDRESS + (4 * (channel_number - 1))

    def _get_channel_result_address(self, channel_number):
        return _CH1_TEMP_RESULT_ADDRESS + (4 * (channel_number - 1))

    def _assign_channel(self, channel_number, channel_assignment_bytes):
        # Check that there are 4 bytes of data
        if len(channel_assignment_bytes) != 4:
            raise ValueError("Channel assignment bytes object must have 4 bytes")

        channel_address = self._get_channel_assignment_address(channel_number)
        self._write_ram_bytes(channel_address, channel_assignment_bytes)

    def _convert_channels(self, channel_numbers, timeout_ms=2600):
        # Timeout is set to a predicted maximum by default. In 3-cycle mode where each conversion
        # takes 3 cycles of 82ms, the potential delay would be 2510ms for 10 channels.

        # Check timeout and warn if too low
        if (timeout_ms < (len(channel_numbers) * 3 * 82)):
            self._logger.warning(
                "Timeout may not be long enough if 3-cycle conversion is used" +
                " Anticipated conversion time for 3-cycle sensors on" +
                " {} channels: {}ms".format(len(channel_numbers), len(channel_numbers)*3*82))

        # Check if this is a single conversion, or multiple conversion for several channels
        if len(channel_numbers) > 1:
            # Create a mask of required channels for the multiple conversion
            channel_mask = 0
            for channel in channel_numbers:
                channel_mask += (0b1 << (channel - 1))

            # The target field is 2 bytes, with ch10-ch1 MSB to LSB
            channel_mask_bytes = channel_mask.to_bytes(2, byteorder='big')

            # Write the mask to the multiple conversion mask register
            self._write_ram_bytes(_REG_MULTIPLE_CONVERSION_MASK, channel_mask_bytes)

            # Starting a conversion with channel number 0 starts a multiple conversion
            control_channel_number = 0
        else:
            # For a single conversion, the chosen channel number is specified
            control_channel_number = channel_numbers[0]

        conversion_command = bytes([_CONVERSION_CONTROL_BYTE | control_channel_number])

        # Start conversion
        self._write_ram_bytes(_REG_COMMAND_STATUS, conversion_command)

        # Wait for conversion to complete, until timeout
        tstart = time.time()        # Epoch time in s, as a float
        command_status = self._read_ram_bytes(start_address=_REG_COMMAND_STATUS,
                                              num_bytes=1)
        while (command_status & 0x40) == 0:
            time.sleep(0.05)
            command_status = self._read_ram_bytes(start_address=_REG_COMMAND_STATUS,
                                                  num_bytes=1)

            # Conversion timeout
            if (time.time() - tstart) < (timeout_ms / 1000.0):
                return False

        return True

    def _read_channel_result_temp(self, channel_number):
        # Returns both the temperature result and fault bits associated with the last conversion

        channel_start_address = self._get_channel_result_address(channel_number)

        raw_channel_bytes = self._read_ram_bytes(start_address=channel_start_address,
                                                 num_bytes=4)

        # Result is in the last 24 LSBs (last 3 bytes)
        raw_result_bytes = raw_channel_bytes[1:]

        # Convert to a signed integer
        result_sint = int.from_bytes(raw_result_bytes, signed=True)

        # Scale the result before returning
        result = (float(result_sint) / 1024.0)

        # The fault bits are in the first 8 MSBs
        fault_bits = raw_channel_bytes[0]

        return (result, fault_bits)

    def _read_channel_raw_voltage_resistance(self, channel_number):
        # Returns the raw voltage or resistance reading captured during the last conversion

        channel_start_address = self._get_channel_raw_address(channel_number)

        raw_channel_bytes = self._read_ram_bytes(start_address=channel_start_address,
                                                 num_bytes=4)

        # Return scaled value
        return (float(raw_channel_bytes) / 1024.0)

    def measure_channel(self, channel_number, include_raw_input=False):
        # Measure a channel by triggering a conversion, waiting for it to complete and then scaling
        # the reading data. include_raw_input adds the raw voltage/resistance to the output.

        conversion_complete = self._convert_channels([channel_number])

        if not conversion_complete:
            raise TimeoutError("Conversion Complete Timed Out")

        if include_raw_input:
            return (self._read_channel_result_temp(channel_number),
                    self._read_channel_raw_voltage_resistance(channel_number))
        else:
            return self._read_channel_result_temp(channel_number)

    def add_thermocouple_channel(self, channel_num):
        # TODO add channel config calculation for thermocouple
        pass

    def add_rtd_channel(self, sensor_type: LTC2986.Sensor_Type,
                        rsense_channel: RTD_RSense_Channel,
                        num_wires: LTC2986.RTD_Num_Wires,
                        excitation_mode: LTC2986.RTD_Excitation_Mode,
                        excitation_current: LTC2986.RTD_Excitation_Current,
                        curve: LTC2986.RTD_Curve,
                        channel_num: int):
        # Check the channel number is valid
        if channel_num not in range(1,10):
            raise ValueError("Channel Number must be between 1-10")

        # Check the sensor type is an RTD
        if sensor_type not in [SENSOR_TYPE_RTD_PT10,
                               SENSOR_TYPE_RTD_PT50,
                               SENSOR_TYPE_RTD_PT100,
                               SENSOR_TYPE_RTD_PT200,
                               SENSOR_TYPE_RTD_PT500,
                               SENSOR_TYPE_LSB,
                               SENSOR_TYPE_RTD_PT1000,
                               SENSOR_TYPE_RTD_PT1000_375,
                               SENSOR_TYPE_RTD_NI120,
                               SENSOR_TYPE_RTD_CUSTOM]:
            raise ValueError("Sensor Type must be RTD")

        # Assemble the channel config value
        channel_config = bytearray(4)

        channel_config = _OR_Bytes(channel_config, sensor_type)
        channel_config = _OR_Bytes(channel_config, rsense_channel)
        channel_config = _OR_Bytes(channel_config, num_wires)
        channel_config = _OR_Bytes(channel_config, excitation_mode)
        channel_config = _OR_Bytes(channel_config, excitation_current)
        channel_config = _OR_Bytes(channel_config, curve)

        # Call the config assignment method
        self._assign_channel(channel_num, channel_config)

    def add_diode_channel(self, channel_num):
        # TODO add channel config calculation for diode
        pass

    def add_thermistor_channel(self, channel_num):
        # TODO add channel config calculation for thermocouple
        pass
