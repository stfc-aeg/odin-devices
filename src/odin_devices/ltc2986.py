"""
Driver for the LTC2986 temperautre management IC.

This is a multifunction device that allows for the dynamic configuration of up to 10 input channels
depending on the various hardware sensors that could be connected to it. These range from Diodes,
RTDs (PT100), raw ADC readings, etc.

The general process in using this device is:
    1. Init the device to establish a connection.
    2. Add sensors as required to each channel in use. For example with add_diode_channel().
    3. Read each channel as desired with measure_channel().

Supported sensors types:
- [x] RTDs
- [ ] Custom RTDs
- [ ] Thermocouples
- [ ] Custom Thermocouples
- [ ] Thermistors
- [ ] Custom Thermistors
- [x] Diodes
- [x] Raw ADC

Joseph Nobes, Embedded Sys Eng, STFC Detector Systems Software Group
"""

from odin_devices.spi_device import SPIDevice, SPIException
from enum import Enum
import time
import logging
import math

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


class _Fault_Bit_Definition(object):
    def __init__(self, is_hardfault_bool, definition_string):
        self.is_hardfault = is_hardfault_bool
        self.definition = definition_string


_FAULT_BIT_DEFINITIONS = {
    0b10000000: _Fault_Bit_Definition(True, 'Sensor Hard Fault'),
    0b01000000: _Fault_Bit_Definition(True, 'Hard ADC Out of Range'),
    0b00100000: _Fault_Bit_Definition(True, 'CJ Hard Fault'),          # Thermocouple only
    0b00010000: _Fault_Bit_Definition(False, 'CJ Soft Fault'),         # Thermocouple only
    0b00001000: _Fault_Bit_Definition(False, 'Sensor Over Range'),
    0b00000100: _Fault_Bit_Definition(False, 'Sensor Under Range'),
    0b00000010: _Fault_Bit_Definition(False, 'ADC Out of Range')
}


def _OR_Bytes(bytesa, bytesb):
    return bytes([x | y for x, y in zip(bytesa, bytesb)])


def _AND_Bytes(bytesa, bytesb):
    return bytes([x & y for x, y in zip(bytesa, bytesb)])


class LTCSensorException(Exception):
    """A general exception raised when issues with sensors are encountered."""

    pass


class LTC2986 (SPIDevice):
    """Control instance for an LTC2986 temperature monitoring IC."""

    class Sensor_Type (Enum):
        """Enum encoding the general type of sensor attached to a given channel.

        This ranges from 'Diode' to 'Raw ADD', but note that for RTDs each different type
        from PT100 to PT1000 has its own enum.
        """

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
        """Enum encoding which pair of channels is connected to an RTD device."""

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
        """Enum encoding which calibration curve to use when measuring with an RTD device."""

        EUROPEAN = (0x00 << _RTD_CURVE_LSB).to_bytes(4, byteorder='big')
        AMERICAN = (0x01 << _RTD_CURVE_LSB).to_bytes(4, byteorder='big')
        JAPANESE = (0x02 << _RTD_CURVE_LSB).to_bytes(4, byteorder='big')
        ITS_90 = (0x03 << _RTD_CURVE_LSB).to_bytes(4, byteorder='big')

    class RTD_Excitation_Current (Enum):
        """Enum encoding the current used to excite a connected RTD device during measurements."""

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
        """Enum encoding the method used to excite a connected RTD device during measurements."""

        NO_ROTATION_NO_SHARING = (0x00 << _RTD_EXCITATION_MODE_LSB).to_bytes(4, byteorder='big')
        NO_ROTATION_SHARING = (0x01 << _RTD_EXCITATION_MODE_LSB).to_bytes(4, byteorder='big')
        ROTATION_SHARING = (0x02 << _RTD_EXCITATION_MODE_LSB).to_bytes(4, byteorder='big')

    class RTD_Num_Wires (Enum):
        """Enum encoding which circuit is being used for RTD measurements."""

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
        """Enum encoding whether or not the diode is being measured in single or differential mode."""

        SINGLE = (0x1 << _DIODE_ENDEDNESS_LSB).to_bytes(4, byteorder='big')
        DIFFERENTIAL = (0x0 << _DIODE_ENDEDNESS_LSB).to_bytes(4, byteorder='big')

    class Diode_Conversion_Cycles (Enum):
        """Enum encoding whether 2 or 3 cycles are used during diode measurements."""

        CYCLES_2 = (0x0 << _DIODE_CONVERSION_CYCLES_LSB).to_bytes(4, byteorder='big')
        CYCLES_3 = (0x1 << _DIODE_CONVERSION_CYCLES_LSB).to_bytes(4, byteorder='big')

    class Diode_Running_Average_En (Enum):
        """Enum encoding whether or not a running average is used for diode measurements."""

        ON = (0x1 << _DIODE_RUNNING_AVG_LSB).to_bytes(4, byteorder='big')
        OFF = (0x0 << _DIODE_RUNNING_AVG_LSB).to_bytes(4, byteorder='big')

    class Diode_Excitation_Current (Enum):
        """Enum encoding how much current is used to excite the diode.

        The excitation current is represented as I, 4*I and 8*I. In two-conversion mode the first conversion
        will be at I, then the second at 8*I. In three-conversion mode, they will be I, 4*I and 8*I.
        """

        CUR_10UA_40UA_80UA = (0x0 << _DIODE_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')
        CUR_20UA_80UA_160UA = (0x1 << _DIODE_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')
        CUR_40UA_160UA_320UA = (0x2 << _DIODE_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')
        CUR_80UA_320UA_640UA = (0x3 << _DIODE_EXCITATION_CURRENT_LSB).to_bytes(4, byteorder='big')

    def __init__(self, bus, device, ignore_hardfaults=False, hz=1000000):
        """Establish initial contact with the device.

        Args:
            bus: SPI bus to use
            device: SPI device number in SPIdev
            ignore_hardfaults: Boolean, if True will simply log errors rather than raising exceptions for hard faults.
            hz: Speed of the SPI bus in HZ.
        """
        # Init SPI Device
        super().__init__(bus, device, hz=hz)  # Max allowed speed for device is 2MHz
        self.set_mode(0b00)

        # Store hardfault ignore setting
        self._ignore_hardfaults = ignore_hardfaults

        self._logger = logging.getLogger('odin_devices.LTC2986' + '@Spidev{}.{}'.format(bus, device))

        self._logger.info("Created new LTC2986 on SPIDev={}.{}".format(bus, device))

        # Assume all channels unassigned on init
        self._channel_assignment_data = {
            1: LTC2986.Sensor_Type.SENSOR_TYPE_NONE,
            2: LTC2986.Sensor_Type.SENSOR_TYPE_NONE,
            3: LTC2986.Sensor_Type.SENSOR_TYPE_NONE,
            4: LTC2986.Sensor_Type.SENSOR_TYPE_NONE,
            5: LTC2986.Sensor_Type.SENSOR_TYPE_NONE,
            6: LTC2986.Sensor_Type.SENSOR_TYPE_NONE,
            7: LTC2986.Sensor_Type.SENSOR_TYPE_NONE,
            8: LTC2986.Sensor_Type.SENSOR_TYPE_NONE,
            9: LTC2986.Sensor_Type.SENSOR_TYPE_NONE,
            10: LTC2986.Sensor_Type.SENSOR_TYPE_NONE
        }

        # Check connection to device and that device POR is complete
        # TODO interrupt pin could be used for this if present
        init_complete = self._wait_for_status_done(timeout_ms=300)
        if not init_complete:
            latest_CSR = self._read_ram_bytes(
                start_address=_REG_COMMAND_STATUS,
                num_bytes=1
            )[0]
            self._logger.warning(
                "Device failed to complete init, command status register read as 0x{:02X}".format(latest_CSR))
            raise SPIException(
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
            "SPI Transfer(r={}): {} -> {} Data Received: {}".format(read, input_data, output_data_full, output_data)
        )

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

    @staticmethod
    def _get_channel_assignment_address(channel_number):
        """Calculate the address at which the assignment bytes should be set for a given channel number."""
        # Check the channel number is valid
        if channel_number < 1 or channel_number > 10:
            raise ValueError("Channel number {} is invalid".format(channel_number))

        return _CH1_ASSIGNMENT_ADDRESS + (4 * (channel_number - 1))

    @staticmethod
    def _get_channel_result_address(channel_number):
        """Calcalate the address where the result for a given channel number should be found."""
        # Check the channel number is valid
        if channel_number < 1 or channel_number > 10:
            raise ValueError("Channel number {} is invalid".format(channel_number))

        return _CH1_TEMP_RESULT_ADDRESS + (4 * (channel_number - 1))

    def _process_fault_bits(self, fault_bits, channel_number):
        """Take a set of fault bits from a reading and react accordingly.

        Each fault is considered 'hard' or 'soft'. By default, soft errors will only result in an error
        message, and hard faults will also throw an exception LTCSensorException. However, if the property
        self._ignore_hardfaults has been set, the exception will not be thrown.

        Args:
            fault_bits: Single value containing the faults bits.
            channel_number: The channel number being processed; used only to make the logs more descriptive.
        """
        hardfault_detected = False

        for fault_bit_position in _FAULT_BIT_DEFINITIONS.keys():
            if fault_bits & fault_bit_position:     # Fault detected
                current_fault = _FAULT_BIT_DEFINITIONS[fault_bit_position]
                if current_fault.is_hardfault:
                    hardfault_detected = True
                    self._logger.critical(
                        "Hardfault detected on channel {}: {}".format(
                            channel_number,
                            current_fault.definition))
                else:
                    self._logger.warning(
                        "Softfault detected on channel {}: {}".format(
                            channel_number,
                            current_fault.definition))

        if hardfault_detected and not self._ignore_hardfaults:
            raise LTCSensorException(
                "Found at least one hardfault, full fault bits: {}".format(hex(fault_bits)))

    def _assign_channel(self, channel_number, channel_assignment_bytes):
        """Write the chosen channel assignement bytes to the device for a channel.

        Args:
            channel_number: The number of the channel to be assigned to.
            channel_assignment_bytes: The already generated configuration bytes, stored as a
                list of byte values.
        """
        # Check that there are 4 bytes of data
        if len(channel_assignment_bytes) != 4:
            raise ValueError("Channel assignment bytes object must have 4 bytes")

        # Write channel assignment data to device
        channel_address = self._get_channel_assignment_address(channel_number)
        self._write_ram_bytes(channel_address, channel_assignment_bytes)

        # Store latest assignment
        sensor_type_bytes = _AND_Bytes(channel_assignment_bytes, b'\xF8\x00\x00\x00')
        self._channel_assignment_data[channel_number] = LTC2986.Sensor_Type(sensor_type_bytes)

    def get_channel_assignment(self, channel_number):
        """Get the current assignment setting for a given channel number.

        Args:
            channel_number; The number of the channel to be checked.

        Returns:
            The numberical version of the current channel assignment. Should be compared with
            the enum Sensor_Type.
        """
        # Check the channel number is valid
        if channel_number < 1 or channel_number > 10:
            raise ValueError("Channel number {} is invalid".format(channel_number))

        return self._channel_assignment_data[channel_number]

    def _wait_for_status_done(self, timeout_ms, check_interval_ms=50):
        """Wait for a given number of ms for a done status on all conversions.

        Read the command status register until the DONE bit is high and START is 0.
        This means that if the bus reads all 0 or all 1 by default it will actually
        fail if the device does not respond.

        Args:
            timeout_ms: Numbver of ms to wait until an error is logged and failed conversion is
                indicated (below).

        Returns:
            A boolean, True if conversion was achieved in the given timescale and False otherwise.
        """
        tstart = time.time()        # Epoch time in s, as a float
        command_status = self._read_ram_bytes(start_address=_REG_COMMAND_STATUS,
                                              num_bytes=1)[0]
        while ((command_status & 0xC0) == 0b01000000) == 0:
            time.sleep(check_interval_ms / 1000.0)
            command_status = self._read_ram_bytes(start_address=_REG_COMMAND_STATUS,
                                                  num_bytes=1)[0]

            # Conversion timeout
            if (time.time() - tstart) > (timeout_ms / 1000.0):
                self._logger.warning(
                    "Wait on done bit timed out after {}s  with last status value: {:02X}".format(
                        time.time() - tstart, command_status
                    )
                )
                return False

        return True

    def _convert_channels(self, channel_numbers, timeout_ms=2600):
        """Perform the channel conversion for a given set of channels.

        Timeout is set to a predicted maximum by default. In 3-cycle mode where each conversion
        takes 3 cycles of 82ms, the potential delay would be 2510ms for 10 channels.

        Args:
            channel_numbers: A list of channel numbers to convert
            timeout_ms: Number of ms to wait for a done status for all channels. See above; ensure
                that you wait long enough for all channels to convert.

        Returns:
            A boolean, True if conversion was achieved in the given timescale and False otherwise.
        """
        # Check timeout and warn if too low
        if (timeout_ms < (len(channel_numbers) * 3 * 82)):
            self._logger.warning("".join([
                "Timeout may not be long enough if 3-cycle conversion is used",
                " Anticipated conversion time for 3-cycle sensors on",
                " {} channels: {}ms".format(len(channel_numbers), len(channel_numbers) * 3 * 82),
            ]))

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
        self._logger.debug("".join([
            "Writing conversion command 0x{:02X} ".format(conversion_command[0]),
            "to register 0x{:02x}".format(_REG_COMMAND_STATUS),
        ]))
        self._write_ram_bytes(_REG_COMMAND_STATUS, conversion_command)

        # Wait for conversion to complete, unless timeout
        return self._wait_for_status_done(timeout_ms)

    def _read_channel_result_temp(self, channel_number):
        """Return both the temperature result and fault bits associated with the last conversion.

        Args:
            channel_number: Number of the channel to read stored result in from.

        Returns:
            A scaled temperature result as a float
        """
        channel_start_address = self._get_channel_result_address(channel_number)

        raw_channel_bytes = self._read_ram_bytes(start_address=channel_start_address,
                                                 num_bytes=4)

        self._logger.debug(
            "Read raw channel {} result as {}".format(channel_number, raw_channel_bytes))

        # Result is in the last 24 LSBs (last 3 bytes)
        raw_result_bytes = raw_channel_bytes[1:]

        # Convert to a signed integer
        result_sint = int.from_bytes(raw_result_bytes, byteorder='big', signed=True)

        # Scale the result before returning
        result = (float(result_sint) / 1024.0)

        # The fault bits are in the first 8 MSBs
        fault_bits = raw_channel_bytes[0]

        self._logger.info("Channel {} result as float: {}".format(channel_number, result))

        # Warn if fault bits found
        if fault_bits != 1:     # 1 means valid
            self._process_fault_bits(fault_bits, channel_number)

        return result

    def _read_channel_raw_voltage_resistance(self, channel_number):
        """Return the raw voltage or resistance reading captured during the last conversion.

        Args:
            channel_number: Number of the channel to read stored result in from.

        Returns:
            A scaled voltage or resistance as a float.
        """
        channel_start_address = self._get_channel_raw_address(channel_number)

        raw_channel_bytes = self._read_ram_bytes(start_address=channel_start_address,
                                                 num_bytes=4)

        # Return scaled value
        return (float(raw_channel_bytes) / 1024.0)

    def _read_channel_raw_adc(self, channel_number):
        """Return the ADC input voltage as a float.

        This uses a different signed format to other results.

        Args:
            channel_number: The channel number of the pin to read.

        Returns:
            Either the looked up (table) result, or a float voltage value.
        """
        channel_start_address = self._get_channel_result_address(channel_number)
        raw_channel_bytes = self._read_ram_bytes(start_address=channel_start_address, num_bytes=4)

        # Result is in the last 24 LSBs (last 3 bytes)
        raw_result_bytes = raw_channel_bytes[1:]

        # Do not use 'signed', as this will assume 2's complement
        raw_result_24bit = int.from_bytes(raw_result_bytes, byteorder='big', signed=False)

        # The fault bits are in the first 8 MSBs
        fault_bits = raw_channel_bytes[0]

        # Calculate result based on 24-bit format <+/-> <2v> <1v> <0.5v> <0.25v> ...
        is_negative = (raw_result_24bit & 0x800000) > 0
        int_preshift = raw_result_24bit & 0x7FFFFF
        float_postshift = int_preshift / math.pow(2, 21)
        result = (-1.0 * float_postshift) if is_negative else float_postshift

        self._logger.info("Channel {} result (raw ADC) as float: {}".format(channel_number, result))

        # Warn if fault bits found
        if fault_bits != 1:     # 1 means valid
            self._process_fault_bits(fault_bits, channel_number)

        return result

    def measure_channel(self, channel_number):
        """Measure a channel by triggering a conversion.

        The code will wait for the conversion to complete, and then scale the reading data.

        Args:
            channel_number: The channel number of the pin / sensor to read.

        Returns:
            Depending on the channel setup, either a direct ADC reading or the float result.
        """
        self._logger.debug("Starting conversion for channel {}".format(channel_number))
        conversion_complete = self._convert_channels([channel_number])

        if not conversion_complete:
            raise TimeoutError("Conversion Complete Timed Out")

        self._logger.debug("Conversion complete")

        # Raw ADC is a special case output format, assumes not using table mode
        if self.get_channel_assignment(channel_number) == LTC2986.Sensor_Type.SENSOR_TYPE_DIRECT_ADC:
            return self._read_channel_raw_adc(channel_number)
        else:
            return self._read_channel_result_temp(channel_number)

    def add_raw_adc_channel(self, channel_num: int, use_table=False, differential=False):
        """Assign the given channel number as a raw ADC input.

        Args:
            channel_num: Channel number of the given input pin.
            use_table: Boolean. If configured for table lookup, the output will be a 24-bit signed
                integer table lookup. Otherwise, it will be a 24-bit fixed-point voltage.
            differential: Boolean, whether or not the input is differential or relative to COM.
        """
        # TODO polish this up and add full options and checks (like use_table)
        sensor_type = LTC2986.Sensor_Type.SENSOR_TYPE_DIRECT_ADC

        # Assemble the ADC channel config value
        channel_config = bytearray(4)

        channel_config = _OR_Bytes(channel_config, sensor_type.value)
        if not differential:
            channel_config = _OR_Bytes(channel_config, (0b1 << 26).to_bytes(4, byteorder='big'))
        # TODO other values

        # Call the ADC Channel config assignment method
        self._logger.info(
            'Assigning channel {} as raw ADC with info bytes: {}'.format(
                channel_num,
                channel_config))
        self._assign_channel(channel_num, channel_config)

    def add_thermocouple_channel(self, channel_num):
        """Assign the given channel number as a thermocouple. Not yet implemented."""
        # TODO add channel config calculation for thermocouple
        raise NotImplementedError('Thermocouple setup not implemented')

    def add_rtd_channel(self, sensor_type: Sensor_Type,
                        rsense_channel: RTD_RSense_Channel,
                        rsense_ohms: float,
                        num_wires: RTD_Num_Wires,
                        excitation_mode: RTD_Excitation_Mode,
                        excitation_current: RTD_Excitation_Current,
                        curve: RTD_Curve,
                        channel_num: int):
        """Configure channel for use with a RTD (.e.g PT100).

        Args:
            sensor_type: Sensor_Type enum, , including a range of PTx00 as well as custom devices.
            rsense_channel: RTD_RSense_Channel enum specifying the pair of channels used.
            rsense_ohms: The impedance in ohms of the sense resistor. This is up to 131072 ohms, and
                will be stored to a precision of 1/1024 ohms.
            num_wires: RTD_Num_Wires enum, use with 2, 3 or 4 wire based circuits.
            excitation_mode: RTD_Excitation_Mode enum, varying currents from 5uA-10mA, or external.
            curve: RTD_Curve enum, which calibration curve to use.
            channel_num: The channel number to use for the actual measurement.
        """
        # Note that the channel number for the RTD is the HIGHEST number connected to it
        # rsense_ohms is up to 131072.0, and will be accurate to 1/1024 Ohms.

        # Check the channel number is valid
        if channel_num not in range(1, 10):
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
        if rsense_ohms < 0 or rsense_ohms > 131072:
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
            'Assigning channel {} as RTD with info bytes: {}'.format(
                channel_num,
                channel_config))
        self._assign_channel(channel_num, channel_config)

        # Calculate RSense value field from target ohms
        rsense_value = int(rsense_ohms * 1024)
        rsense_value_bytes = (rsense_value).to_bytes(4, byteorder='big')

        # Decode the rsense channel number from the paired RTD channel setting
        rsense_ch_num = int.from_bytes(rsense_channel.value, byteorder='big') >> _RTD_RSENSE_CHANNEL_LSB

        # Call the RSense Channel config assignment method with combined fields
        rsense_config = bytearray(4)
        rsense_config = _OR_Bytes(rsense_config, LTC2986.Sensor_Type.SENSOR_TYPE_SENSE_RESISTOR.value)
        rsense_config = _OR_Bytes(rsense_config, rsense_value_bytes)
        self._logger.debug("".join([
            'Assigning RTD sense resistor on channel {} '.format(rsense_ch_num),
            'with value {} ({} ohms) '.format(rsense_value_bytes, rsense_value / 1024),
            'and resulting info byte: {}'.format(rsense_config),
        ]))
        self._assign_channel(rsense_ch_num, rsense_config)

    def add_diode_channel(self, endedness: Diode_Endedness,
                          conversion_cycles: Diode_Conversion_Cycles,
                          average_en: Diode_Running_Average_En,
                          excitation_current: Diode_Excitation_Current,
                          diode_non_ideality: float,
                          channel_num):
        """Configure channel for use as a temperature sensing diode.

        Args:
            endedness: Diode_Endedness enum, Single or Differential.
            conversion_cycles: Diode_Conversion_Cycles enum, either 2 or 3 cycles.
            average_en: Diode_Running_Average_En enum, whether or not a running average
                is used.
            excitation_current: Diode_Excitation_Current enum, choose a current from 10uA to
                80mA as I. The max current used will be 8*I (see enum class).
            diode_non_ideality: Float between 0.0-4.0, which will be accurate to 1/1048576
                when stored by the device. This is a propertly of the specific diode. A
                perfect ideality would be 1.
            channel_num: The channel number (D) of the pin connected to the diode anode (
                when used in differential mode, the cathode will be connected to (D-1).
        """
        # The diode non-ideality is between 0.0 and 4.0, and will be accurate to 1/1048576

        # Check the channel number is valid
        if channel_num not in range(1, 10):
            raise ValueError("Channel Number must be between 1-10")

        # Check the diode non-ideality factor is in the correct range
        if diode_non_ideality < 0.0 or diode_non_ideality > 4.0:
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
            'Assigning channel {} as Diode with info bytes: {}'.format(
                channel_num,
                channel_config))
        self._assign_channel(channel_num, channel_config)

    def add_unassigned_channel(self, channel_num):
        """Remove the channel assignment for a given channel number."""
        channel_config = b'\x00\x00\x00\x00'
        self._logger.info(
            'Setting channel {} unassigned'.format(channel_num))
        self._assign_channel(channel_num, channel_config)

    def add_thermistor_channel(self, channel_num):
        """Assign the given channel number as a thermistor. Not yet implemented."""
        # TODO add channel config calculation for thermistor
        raise NotImplementedError('Thermistor setup not implemented')
