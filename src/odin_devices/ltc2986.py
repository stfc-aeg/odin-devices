# Support:
# - [x] RTDs
# - [ ] Custom RTDs
# - [ ] Thermocouples
# - [ ] Custom Thermocouples
# - [ ] Thermistors
# - [ ] Custom Thermistors
# - [ ] Diodes

from odin_devices.spi_device import SPIDevice, SPIException
from enum import Enum
import time
import logging

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

_DIODE_ENDEDNESS_LSB = 26
_DIODE_CONVERSION_CYCLES_LSB = 25
_DIODE_RUNNING_AVG_LSB = 24
_DIODE_EXCITATION_CURRENT_LSB = 22

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

        SENSOR_TYPE_DIODE = (0x1C << _SENSOR_TYPE_LSB).to_bytes(4, byteorder='big')

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
        CH2_CH1 = (0x02 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CH3_CH2 = (0x03 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CH4_CH3 = (0x04 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CH5_CH4 = (0x05 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CH6_CH5 = (0x06 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CH7_CH6 = (0x07 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CH8_CH7 = (0x08 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CH9_CH8 = (0x09 << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')
        CH10_CH9 = (0x0A << _RTD_RSENSE_CHANNEL_LSB).to_bytes(4, byteorder='big')

    class RTD_Curve (Enum):
        EUROPEAN = (0x00 << _RTD_CURVE_LSB).to_bytes(4, byteorder='big')
        AMERICAN = (0x01 << _RTD_CURVE_LSB).to_bytes(4, byteorder='big')
        JAPANESE = (0x02 << _RTD_CURVE_LSB).to_bytes(4, byteorder='big')
        ITS_90 = (0x03 << _RTD_CURVE_LSB).to_bytes(4, byteorder='big')

    class RTD_Excitation_Current (Enum):
        EXTERNAL = (0x00 << _RTD_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')
        CURRENT_5UA = (0x01 << _RTD_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')
        CURRENT_10UA = (0x02 << _RTD_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')
        CURRENT_25UA = (0x03 << _RTD_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')
        CURRENT_50UA = (0x04 << _RTD_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')
        CURRENT_100UA = (0x05 << _RTD_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')
        CURRENT_250UA = (0x06 << _RTD_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')
        CURRENT_500UA = (0x07 << _RTD_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')
        CURRENT_1MA = (0x08 << _RTD_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')

    class RTD_Excitation_Mode (Enum):
        NO_ROTATION_NO_SHARING = (0x00 << _RTD_EXCITATION_MODE_LSB).to_bytes(4, byteorder='big')
        NO_ROTATION_SHARING = (0x01 << _RTD_EXCITATION_MODE_LSB).to_bytes(4, byteorder='big')
        ROTATION_SHARING = (0x02 << _RTD_EXCITATION_MODE_LSB).to_bytes(4, byteorder='big')

    class RTD_Num_Wires (Enum):
        NUM_2_WIRES = (0x00 << _RTD_NUM_WIRES_LSB).to_bytes(4, byteorder='big')
        NUM_3_WIRES = (0x01 << _RTD_NUM_WIRES_LSB).to_bytes(4, byteorder='big')
        NUM_4_WIRES = (0x02 << _RTD_NUM_WIRES_LSB).to_bytes(4, byteorder='big')
        NUM_4_WIRES_KELVIN_RSENSE = (0x03 << _RTD_NUM_WIRES_LSB).to_bytes(4, byteorder='big')

    """
    Diode Config Values:
    | Bit          | 31 30 29 28 27 | 26             | 25           | 24     | 23 22              |
    | ------------ | -------------- | -------------- | ------------ | ------ | ------------------ |
    | Diode Config | Type = 28      | Single or Diff | Num Readings | Avg on | Excitation Current |

                   | 21 20 19 18 17 16 15 14 13 12 11 10 9 8 7 6 5 4 3 2 1 0 |
                   | ------------------------------------------------------- |
                   | Diode Ideality Factor                                   |
    """
    class Diode_Endedness (Enum):
        SINGLE = (0x1 << _DIODE_ENDEDNESS_LSB).to_bytes(4, byteorder='big')
        DIFFERENTIAL = (0x0 << _DIODE_ENDEDNESS_LSB).to_bytes(4, byteorder='big')

    class Diode_Conversion_Cycles (Enum):
        CYCLES_2 = (0x0 << _DIODE_CONVERSION_CYCLES_LSB).to_bytes(4, byteorder='big')
        CYCLES_3 = (0x1 << _DIODE_CONVERSION_CYCLES_LSB).to_bytes(4, byteorder='big')

    class Diode_Running_Average_En (Enum):
        ON = (0x1 << _DIODE_RUNNING_AVG_LSB).to_bytes(4, byteorder='big')
        OFF = (0x0 << _DIODE_RUNNING_AVG_LSB).to_bytes(4, byteorder='big')

    class Diode_Excitation_Current (Enum):
        CUR_10UA_40UA_80UA = (0x0 << _DIODE_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')
        CUR_20UA_80UA_160UA = (0x1 << _DIODE_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')
        CUR_40UA_160UA_320UA = (0x2 << _DIODE_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')
        CUR_80UA_320UA_640UA = (0x3 << _DIODE_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')

    def __init__(self, bus=0, device=0):

        # Init SPI Device
        super().__init__(bus, device)

        self._logger = logging.getLogger('odin_devices.LTC2986')

        self._logger.info("Created new LTC2986 on SPIDev={}.{}".format(bus, device))

        # Check connection to device and that device POR is complete
        # TODO interrupt pin could be used for this if present
        init_complete = self._wait_for_status_done(timeout_ms=300)
        if not init_complete:
            latest_CSR = self._read_ram_bytes(start_address=_REG_COMMAND_STATUS,
                                                  num_bytes=1)[0]
            self._logger.warning(
                    "Device failed to complete init, " +
                    "command status register read as 0x{:02X}".format(latest_CSR))
            raise SPIException (
                    "SPI Device failed to complete setup. Connection may be bad")

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

        # Get raw output data and strip prefix, converting to/from list type for spidev
        output_data_full = bytes(self.transfer(list(input_data)))
        output_data = output_data_full[3:]     # Strip command and address

        self._logger.debug(
                "SPI Transfer(r={}): {} -> {} ".format(read, input_data, output_data_full) +
                "Data Received: {}".format(output_data))

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

    def _wait_for_status_done(self, timeout_ms, check_interval_ms=50):
        # Read the command status register until 0x40 (done bit) is high
        tstart = time.time()        # Epoch time in s, as a float
        command_status = self._read_ram_bytes(start_address=_REG_COMMAND_STATUS,
                                              num_bytes=1)[0]
        while (command_status & 0x40) == 0:
            time.sleep(check_interval_ms / 1000.0)
            command_status = self._read_ram_bytes(start_address=_REG_COMMAND_STATUS,
                                                  num_bytes=1)[0]

            # Conversion timeout
            if (time.time() - tstart) > (timeout_ms / 1000.0):
                self._logger.warning(
                        "Wait on done bit timed out after {}s ".format(time.time() - tstart) +
                        " with last status value: {:02X}".format(command_status))
                return False

        return True

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
            self._logger.debug(
                    "Multiple conversion mask created: 0x{}".format(channel_mask_bytes.hex()))
            self._write_ram_bytes(_REG_MULTIPLE_CONVERSION_MASK, channel_mask_bytes)

            # Starting a conversion with channel number 0 starts a multiple conversion
            control_channel_number = 0
        else:
            # For a single conversion, the chosen channel number is specified
            control_channel_number = channel_numbers[0]

        conversion_command = bytes([_CONVERSION_CONTROL_BYTE | control_channel_number])

        # Start conversion
        self._logger.debug(
                "Writing conversion command 0x{:02X} ".format(conversion_command[0]) +
                "to register 0x{:02x}".format(_REG_COMMAND_STATUS))
        self._write_ram_bytes(_REG_COMMAND_STATUS, conversion_command)

        # Wait for conversion to complete, unless timeout
        return self._wait_for_status_done(timeout_ms)

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

        self._logger.info("Starting conversion for channel {}".format(channel_number))
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

    def add_rtd_channel(self, sensor_type: Sensor_Type,
                        rsense_channel: RTD_RSense_Channel,
                        rsense_ohms: float,
                        num_wires: RTD_Num_Wires,
                        excitation_mode: RTD_Excitation_Mode,
                        excitation_current: RTD_Excitation_Current,
                        curve: RTD_Curve,
                        channel_num: int):
        # Note that the channel number for the RTD is the HIGHEST number connected to it
        # rsense_ohms is up to 131072.0, and will be accurate to 1/1024 Ohms.

        # Check the channel number is valid
        if channel_num not in range(1,10):
            raise ValueError("Channel Number must be between 1-10")

        # Check the sensor type is an RTD
        if sensor_type not in [LTC2986.Sensor_Type.SENSOR_TYPE_RTD_PT10,
                               LTC2986.Sensor_Type.SENSOR_TYPE_RTD_PT50,
                               LTC2986.Sensor_Type.SENSOR_TYPE_RTD_PT100,
                               LTC2986.Sensor_Type.SENSOR_TYPE_RTD_PT200,
                               LTC2986.Sensor_Type.SENSOR_TYPE_RTD_PT500,
                               LTC2986.Sensor_Type.SENSOR_TYPE_RTD_PT1000,
                               LTC2986.Sensor_Type.SENSOR_TYPE_RTD_PT1000_375,
                               LTC2986.Sensor_Type.SENSOR_TYPE_RTD_NI120,
                               LTC2986.Sensor_Type.SENSOR_TYPE_RTD_CUSTOM]:
            raise ValueError("Sensor Type must be RTD")

        # Check that RSense resistance is in range
        if rsense_ohms < 0 or rsense_ohms >  131072:
            raise ValueError("RSense resistance up to 131kOhm allowed")

        # TODO add other checks for input types

        # Assemble the RTD channel config value
        channel_config = bytearray(4)

        channel_config = _OR_Bytes(channel_config, sensor_type.value)
        channel_config = _OR_Bytes(channel_config, rsense_channel.value)
        channel_config = _OR_Bytes(channel_config, num_wires.value)
        channel_config = _OR_Bytes(channel_config, excitation_mode.value)
        channel_config = _OR_Bytes(channel_config, excitation_current.value)
        channel_config = _OR_Bytes(channel_config, curve.value)

        # Call the RTD Channel config assignment method
        self._logger.info(
                'Assigning new RTD channel with info bytes: {}'.format(channel_config))
        self._assign_channel(channel_num, channel_config)

        # Calculate RSense value field from target ohms
        rsense_value = int(rsense_ohms * 1024)
        rsense_value_bytes = (rsense_value).to_bytes(4, byteorder='big')

        # Decode the rsense channel number from the paired RTD channel setting
        rsense_ch_num = int.from_bytes(rsense_channel.value, byteorder='big') >> _RTD_RSENSE_CHANNEL_LSB

        # Call the RSense Channel config assignment method with combined fields
        rsense_config = bytearray(4)
        rsense_config = _OR_Bytes(channel_config, LTC2986.Sensor_Type.SENSOR_TYPE_SENSE_RESISTOR.value)
        rsense_config = _OR_Bytes(channel_config, rsense_value_bytes)
        self._logger.info(
                'Assigning RTD sense resistor on channel {} '.format(rsense_ch_num) +
                'with value {} ({} ohms)'.format(rsense_value_bytes, rsense_value / 1024))
        self._assign_channel(rsense_ch_num, rsense_config)

    def add_diode_channel(self, endedness: Diode_Endedness,
                          conversion_cycles: Diode_Conversion_Cycles,
                          average_en: Diode_Running_Average_En,
                          excitation_current: Diode_Excitation_Current,
                          diode_non_ideality: float,
                          channel_num):
        # The diode non-ideality is between 0.0 and 4.0, and will be accurate to 1/1048576

        # Check the channel number is valid
        if channel_num not in range(1,10):
            raise ValueError("Channel Number must be between 1-10")

        # Check the diode non-ideality factor is in the correct range
        if diode_non_ideality < 0.0 or diode_non_ideality >  4.0:
            raise ValueError("Diode non-ideality must be between 0.0 and 4.0")

        # TODO add other checks for input types

        # Calculate non-ideality factor byte field value
        non_ideality_value = int(diode_non_ideality * 1048576)
        non_ideality_factor_bytes = (non_ideality_value).to_bytes(4, byteorder='big')

        # Assemble the Diode channel config values
        channel_config = bytearray(4)

        channel_config = _OR_Bytes(channel_config, LTC2986.Sensor_Type.SENSOR_TYPE_DIODE.value)
        channel_config = _OR_Bytes(channel_config, endedness.value)
        channel_config = _OR_Bytes(channel_config, conversion_cycles.value)
        channel_config = _OR_Bytes(channel_config, average_en.value)
        channel_config = _OR_Bytes(channel_config, excitation_current.value)
        channel_config = _OR_Bytes(channel_config, non_ideality_factor_bytes)

        # Call the RTD Channel config assignment method
        self._logger.info(
                'Assigning new Diode channel with info bytes: {}'.format(channel_config))
        self._assign_channel(channel_num, channel_config)

    def add_thermistor_channel(self, channel_num):
        # TODO add channel config calculation for thermocouple
        pass
