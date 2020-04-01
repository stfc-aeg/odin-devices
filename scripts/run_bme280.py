"""A script using main entry points to run the bme280 device.
Prints the temperature, humidity and pressure, with 1/3 of a second between each.
"""
from odin_devices.bme280 import BME280

def main():
    """Create an instance of and launch the BME280.

    Will print the temperature, humidity and pressure around the sensor evenly every one second.
    """
    bme = BME280()
    print("launching test BME280")

    try:
        while True:
            print("Temperature:  {:.2f} C".format(bme.temperature))
            sleep(0.33)
            print("Humidity:     {:.2f} %RH".format(bme.humidity))
            sleep(0.33)
            print("Pressure:   {:.2f} hPa".format(bme.pressure))
            sleep(0.33)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
