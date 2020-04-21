"""BME280 - bme280 device access class.

derived from Adafruit implementation for CircuitPython available at:
https://github.com/adafruit/Adafruit_CircuitPython_BME280/blob/80757ff2146c62ac7192c94b060c67d4751868b4/adafruit_bme280.py

"""

import math
from time import sleep

from struct import unpack

from odin_devices.spi_device import SPIDevice


#    I2C ADDRESS/BITS/SETTINGS
_BME280_ADDRESS = 0x77
_BME280_CHIPID = 0x60

_BME280_REGISTER_CHIPID = 0xD0
_BME280_REGISTER_DIG_T1 = 0x88
_BME280_REGISTER_DIG_H1 = 0xA1
_BME280_REGISTER_DIG_H2 = 0xE1
_BME280_REGISTER_DIG_H3 = 0xE3
_BME280_REGISTER_DIG_H4 = 0xE4
_BME280_REGISTER_DIG_H5 = 0xE5
_BME280_REGISTER_DIG_H6 = 0xE7

_BME280_REGISTER_SOFTRESET = 0xE0
_BME280_REGISTER_CTRL_HUM = 0xF2
_BME280_REGISTER_STATUS = 0xF3
_BME280_REGISTER_CTRL_MEAS = 0xF4
_BME280_REGISTER_CONFIG = 0xF5
_BME280_REGISTER_PRESSUREDATA = 0xF7
_BME280_REGISTER_TEMPDATA = 0xFA
_BME280_REGISTER_HUMIDDATA = 0xFD

_BME280_PRESSURE_MIN_HPA = 300
_BME280_PRESSURE_MAX_HPA = 1100
_BME280_HUMIDITY_MIN = 0
_BME280_HUMIDITY_MAX = 100

# iir filter values
IIR_FILTER_DISABLE = 0
IIR_FILTER_X2 = 0x01
IIR_FILTER_X4 = 0x02
IIR_FILTER_X8 = 0x03
IIR_FILTER_X16 = 0x04

_BME280_IIR_FILTERS = (IIR_FILTER_DISABLE, IIR_FILTER_X2,
                       IIR_FILTER_X4, IIR_FILTER_X8, IIR_FILTER_X16)

# overscan values for pressure, temperature and humidity
OVERSCAN_DISABLE = 0x00
OVERSCAN_X1 = 0x01
OVERSCAN_X2 = 0x02
OVERSCAN_X4 = 0x03
OVERSCAN_X8 = 0x04
OVERSCAN_X16 = 0x05

_BME280_OVERSCANS = {OVERSCAN_DISABLE: 0, OVERSCAN_X1: 1, OVERSCAN_X2: 2,
                     OVERSCAN_X4: 4, OVERSCAN_X8: 8, OVERSCAN_X16: 16}

# mode values
MODE_SLEEP = 0x00
MODE_FORCE = 0x01
MODE_NORMAL = 0x03
_BME280_MODES = (MODE_SLEEP, MODE_FORCE, MODE_NORMAL)

# Standby timeconstant values
# TC_X[_Y] where X=milliseconds and Y=tenths of a millisecond
STANDBY_TC_0_5 = 0x00    # 0.5ms
STANDBY_TC_10 = 0x06     # 10ms
STANDBY_TC_20 = 0x07     # 20ms
STANDBY_TC_62_5 = 0x01   # 62.5ms
STANDBY_TC_125 = 0x02    # 125ms
STANDBY_TC_250 = 0x03    # 250ms
STANDBY_TC_500 = 0x04    # 500ms
STANDBY_TC_1000 = 0x05   # 1000ms

_BME280_STANDBY_TCS = (STANDBY_TC_0_5, STANDBY_TC_10, STANDBY_TC_20,
                       STANDBY_TC_62_5, STANDBY_TC_125, STANDBY_TC_250,
                       STANDBY_TC_500, STANDBY_TC_1000)


class BME280(SPIDevice):
    """BME280 class.

    This class implements support for the BME280 device.
    """

    def __init__(self):
        """Initialise the BME280 device.

        Any SPI settings can be adjusted with the functions in spi_device.
        SPIDevice.__init__ is provided bus, device, bits_per_word (optional) and hz (optional).
        """
        SPIDevice.__init__(self, 0, 0)  # bus, device

        # This device is compatible with SPI modes 0 and 3 (00, 11).
        self.set_mode(0)

        # Longest transaction is 24 bytes read, one written.
        self.set_buffer_length(25)

        # Check device ID.
        chip_id = self._read_byte(_BME280_REGISTER_CHIPID)
        print("Chip ID: 0x%x" % int(chip_id))

        if _BME280_CHIPID != chip_id:
            raise RuntimeError('Failed to find BME280! Chip ID 0x%x' % chip_id)

        # Reasonable defaults.
        self._iir_filter = IIR_FILTER_DISABLE
        self._overscan_humidity = OVERSCAN_X1
        self._overscan_temperature = OVERSCAN_X1
        self._overscan_pressure = OVERSCAN_X16
        self._t_standby = STANDBY_TC_125
        self._mode = MODE_SLEEP
        self._reset()
        self._read_coefficients()
        self._write_ctrl_meas()
        self._write_config()

        # Pressure in hPa at sea level. Used to calibrate altitude.
        self_t_fine = None

    def _read_temperature(self):
        """Perform one temperature measurement."""
        if self.mode != MODE_NORMAL:
            self.mode = MODE_FORCE

            while self._get_status() & 0x08:
                sleep(0.002)
        raw_temperature = self._read24(_BME280_REGISTER_TEMPDATA) / 16  # Drop lowest 4 bits
        var1 = (raw_temperature / 16384.0 - self._temp_calib[0] / 1024.0) * self._temp_calib[1]
        var2 = ((raw_temperature / 131072.0 - self._temp_calib[0] / 8192) * (raw_temperature / 131072.0 - self._temp_calib[0] / 8192.0)) * self._temp_calib[2]

        self._t_fine = int(var1 + var2)

    def _reset(self):
        """Soft reset the sensor."""
        self._write_register_byte(_BME280_REGISTER_SOFTRESET, 0xB6)
        sleep(0.004)  # Datasheet says 2ms, using 4ms to be safe

    def _write_ctrl_meas(self):
        """Write the values to ctrl_meas and ctrl_hum registers in the device.

        ctrl_meas sets the pressure and temperature data acquisition options.
        ctrl_hum sets the humidity oversampling and must be written to first.
        """
        self._write_register_byte(_BME280_REGISTER_STATUS, self._overscan_humidity)
        self._write_register_byte(_BME280_REGISTER_CTRL_MEAS, self._ctrl_meas)

    def _get_status(self):
        """Get the value from the status register in the device."""
        return self._read_byte(_BME280_REGISTER_STATUS)

    def _read_config(self):
        """Read the value from the config register in the device."""
        return self._read_byte(_BME280_REGISTER_CONFIG)

    def _write_config(self):
        """Write the value to the config register in the device."""
        normal_flag = False
        if self._mode == MODE_NORMAL:
            # Write to the config register may be ignored while in normal mode
            normal_flag = True
            self.mode = MODE_SLEEP  # So we switch to sleep mode first
        self._write_register_byte(_BME280_REGISTER_CONFIG, self._config)
        if normal_flag:
            self.mode = MODE_NORMAL

    @property
    def mode(self):
        """Operation mode. Allowed values are the constants MODE_*."""
        return self._mode

    @mode.setter
    def mode(self, value):
        if value not in _BME280_MODES:
            raise ValueError('Mode \'%s\' not supported' % (value))
        self._mode = value
        self._write_ctrl_meas()

    @property
    def standby_period(self):
        """Control the inactive period when in Normal mode.

        Allowed standby periods are the constants STANDBY_TC_*
        """
        return self._t_standby

    @standby_period.setter
    def standby_period(self, value):
        if value not in _BME280_STANDBY_TCS:
            raise ValueError('Standby Period \'%s\' not supported' % (value))
        if self._t_standby == value:
            return
        self._t_standby = value
        self._write_config()

    @property
    def overscan_humidity(self):
        """Humidity oversampling.

        Allowed values are the constants OVERSCAN_*
        """
        return self._overscan_humidity

    @overscan_humidity.setter
    def overscan_humidity(self, value):
        if value not in _BME280_OVERSCANS:
            raise ValueError('Overscan value \'%s\' not supported' % (value))
        self._overscan_humidity = value
        self._write_ctrl_meas()

    @property
    def overscan_pressure(self):
        """Pressure oversamplings.

        Allowed value are the constants OVERSCAN_*
        """
        return self._overscan_pressure

    @overscan_pressure.setter
    def overscan_pressure(self, value):
        if value not in _BME280_OVERSCANS:
            raise ValueError('Overscan value \'%s\' not supported' % (value))
        self._overscan_pressure = value
        self._write_ctrl_meas()

    @property
    def overscan_temperature(self):
        """Temperature Oversampling.

        Allowed values are the constants OVERSCAN_*
        """
        return self._overscan_temperature

    @overscan_temperature.setter
    def overscan_temperature(self, value):
        if value not in _BME280_OVERSCANS:
            raise ValueError('Overscan value \'%s\' not supported' % (value))
        self._overscan_temperature = value
        self._write_ctrl_meas()

    @property
    def iir_filter(self):
        """Control the time constant of the IIR filter.

        ALlowed values are the constanst IIR_FILTER_*.
        """
        return self._iir_filter

    @iir_filter.setter
    def iir_filter(self, value):
        if value not in _BME280_IIR_FILTERS:
            raise ValueError('IIR Filter \'%s\' not supported' % (value))
        self._iir_filter = value
        self._write_config()

    @property
    def _config(self):
        """Value to be written to the device's config register."""
        config = 0
        if self.mode == MODE_NORMAL:
            config += (self._t_standby << 5)
        if self._iir_filter:
            config += (self._iir_filter << 2)
        return config

    @property
    def _ctrl_meas(self):
        """Value to be written to the device's ctrl_meas register."""
        ctrl_meas = (self.overscan_temperature << 5)
        ctrl_meas += (self.overscan_pressure << 2)
        ctrl_meas += self.mode
        return ctrl_meas

    @property
    def measurement_time_typical(self):
        """Typical time in milliseconds required to complete a measurement in normal mode."""
        meas_time_ms = 1.0
        if self.overscan_temperature != OVERSCAN_DISABLE:
            meas_time_ms += (2 * _BME280_OVERSCANS.get(self.overscan_temperature))
        if self.overscan_pressure != OVERSCAN_DISABLE:
            meas_time_ms += (2 * _BME280_OVERSCANS.get(self.overscan_pressure) + 0.5)
        if self.overscan_humidity != OVERSCAN_DISABLE:
            meas_time_ms += (2 * _BME280_OVERSCANS.get(self.overscan_humidity) + 0.5)
        return meas_time_ms

    @property
    def measurement_time_max(self):
        """Maximum time in milliseconds required to complete a measurement in normal mode."""
        meas_time_ms = 1.25
        if self._overscan_temperature != OVERSCAN_DISABLE:
            meas_time_ms += (2.3 * _BME280_OVERSCANS.get(self._overscan_temperature))
        if self.overscan_pressure != OVERSCAN_DISABLE:
            meas_time_ms += (2.3 * _BME280_OVERSCANS.get(self.overscan_pressure) + 0.575)
        if self.overscan_humidity != OVERSCAN_DISABLE:
            meas_time_ms += (2.3 * _BME280_OVERSCANS.get(self.overscan_humidity) + 0.575)
        return meas_time_ms

    @property
    def temperature(self):
        """Get the compensated temperature in degrees celcius."""
        self._read_temperature()
        return self._t_fine / 5120.0

    @property
    def pressure(self):
        """Calculate the compensated pressure in hPa.

        Returns None if pressure measurement is disabled.
        """
        self._read_temperature()

        # Algorithm from the BME280 driver:
        # https://github.com/BoschSensortec/BME280_driver/blob/master/bme280.c
        adc = self._read24(_BME280_REGISTER_PRESSUREDATA) / 16  # lowest 4 bits get dropped
        var1 = float(self._t_fine) / 2.0 - 64000.0
        var2 = var1 * var1 * self._pressure_calib[5] / 32768.0
        var2 = var2 + var1 * self._pressure_calib[4] * 2.0
        var2 = var2 / 4.0 + self._pressure_calib[3] * 65536.0
        var3 = self._pressure_calib[2] * var1 * var1 / 524288.0
        var1 = (var3 + self._pressure_calib[1] * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * self._pressure_calib[0]
        if not var1:  # avoid exception caused by division by zero
            raise ArithmeticError("Invalid result possibly related to error while \
reading the calibration registers")
        pressure = 1048576.0 - adc
        pressure = ((pressure - var2 / 4096.0) * 6250.0) / var1
        var1 = self._pressure_calib[8] * pressure * pressure / 2147483648.0
        var2 = pressure * self._pressure_calib[7] / 32768.0
        pressure = pressure + (var1 + var2 + self._pressure_calib[6]) / 16.0

        pressure /= 100
        if pressure < _BME280_PRESSURE_MIN_HPA:
            return _BME280_PRESSURE_MIN_HPA
        if pressure > _BME280_PRESSURE_MAX_HPA:
            return _BME280_PRESSURE_MAX_HPA
        return pressure

    @property
    def humidity(self):
        """Calculate the relative humidity in RH %.

        returns None if humidity measurement is disabled.
        """
        self._read_temperature()
        hum = self._read_register(_BME280_REGISTER_HUMIDDATA, end=3)
        # print("Humidity data: ", hum)
        adc = float(hum[0] << 8 | hum[1])
        # print("adc:", adc)

        # Algorithm from the BME280 driver
        # https://github.com/BoschSensortec/BME280_driver/blob/master/bme280.c
        var1 = float(self._t_fine) - 76800.0
        # print("var1 ", var1)
        var2 = (self._humidity_calib[3] * 64.0 + (self._humidity_calib[4] / 16384.0) * var1)
        # print("var2 ",var2)
        var3 = adc - var2
        # print("var3 ",var3)
        var4 = self._humidity_calib[1] / 65536.0
        # print("var4 ",var4)
        var5 = (1.0 + (self._humidity_calib[2] / 67108864.0) * var1)
        # print("var5 ",var5)
        var6 = 1.0 + (self._humidity_calib[5] / 67108864.0) * var1 * var5
        # print("var6 ",var6)
        var6 = var3 * var4 * (var5 * var6)
        humidity = var6 * (1.0 - self._humidity_calib[0] * var6 / 524288.0)

        if humidity > _BME280_HUMIDITY_MAX:
            return _BME280_HUMIDITY_MAX
        if humidity < _BME280_HUMIDITY_MIN:
            return _BME280_HUMIDITY_MIN
        # else...
        return humidity

    @property
    def altitude(self):
        """Calculate the altitude based on current ``pressure`` versus the sea level pressure.

        (``sea_level_pressure``) - which you must enter ahead of time).
        """
        pressure = self.pressure  # in Si units for hPascal
        return 44330 * (1.0 - math.pow(pressure / self.sea_level_pressure, 0.1903))

    def _read_coefficients(self):
        """Read & save the calibration coefficients."""
        coeff = self._read_register(_BME280_REGISTER_DIG_T1, end=25)
        coeff = list(unpack('<HhhHhhhhhhhh', bytes(coeff)))
        coeff = [float(i) for i in coeff]
        self._temp_calib = coeff[:3]
        self._pressure_calib = coeff[3:]

        self._humidity_calib = [0]*6
        self._humidity_calib[0] = self._read_byte(_BME280_REGISTER_DIG_H1)
        coeff = self._read_register(_BME280_REGISTER_DIG_H2, end=8)
        coeff = list(unpack('<hBbBbb', bytes(coeff)))
        self._humidity_calib[1] = float(coeff[0])
        self._humidity_calib[2] = float(coeff[1])
        self._humidity_calib[3] = float((coeff[2] << 4) | (coeff[3] & 0xF))
        self._humidity_calib[4] = float((coeff[4] << 4) | (coeff[3] >> 4))
        self._humidity_calib[5] = float(coeff[5])

    def _read_byte(self, register):
        """Read a byte register value and return it.

        :param register: the register to be read from.
        """
        return self._read_register(register, end=2)[0]

    def _read24(self, register):
        """Read an unsigned 24-bit value as a floating point and return it.

        self.buffer is set to four to allow for one register byte to be transferred too.
        :param register: the register to read from.
        :returns ret: the 24-bit value.
        """
        ret = 0.0
        for b in self._read_register(register, end=4):
            ret *= 256.0
            ret += float(b & 0xFF)
        return ret

    def _read_register(self, register, end=None, write_value=0):
        """Read length number of bytes from a register on the SPI device.

        Length defaults to the length of buffer. The read is done via an SPI transfer.

        :param end: specifies where to write up to in buffer. To be passed to transfer().
        :param write_value: value to fill the buffer with. Default: 0

        :returns result: the MISO transfer response, an array of length equal to buffer.
        """
        for i in range(len(self.buffer)):
            self.buffer[i] = write_value

        register = (register | 0x80) & 0xFF  # Read single, bit 7 high
        self.buffer[0] = register

        result = self.transfer(self.buffer, end=end)[1:]
        return result

    def _write_register_byte(self, register, value):
        """Write a byte to the specified register."""
        register &= 0x7F  # Write, bit 7 low.
        self.buffer[0] = register
        self.buffer[1] = value & 0xFF
        self.write_bytes(bytes(self.buffer), end=2)
