"""A script using main entry points to run the bme280 device.
Prints the temperature, humidity and pressure, with 1/3 of a second between each.
"""
from odin_devices.bme280 import BME280
from time import sleep

def main():
    """Create an instance of and launch the BME280 with SPI and I2C.

    Will print the temperature, humidity and pressure around the sensor evenly every one second.
    """
    bme_spi = BME280(use_spi=True)
    bme_i2c = BME280(use_spi=False, i2c_busnum=2)
    print("launching test BME280")

    try:
        while True:
            print("Temperature (SPI):  {:.2f} C".format(bme_spi.temperature))
            print("Temperature (I2C):  {:.2f} C".format(bme_i2c.temperature))
            sleep(0.33)
            print("Humidity (SPI):     {:.2f} %RH".format(bme_spi.humidity))
            print("Humidity (I2C):     {:.2f} %RH".format(bme_i2c.humidity))
            sleep(0.33)
            print("Pressure (SPI):   {:.2f} hPa".format(bme_spi.pressure))
            print("Pressure (I2C):   {:.2f} hPa".format(bme_i2c.pressure))
            sleep(0.33)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
