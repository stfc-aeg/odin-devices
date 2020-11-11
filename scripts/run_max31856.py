"""A script using main entry points to run the max31856 device.
The temperature is fetched and printed once per second.
"""

from odin_devices.max31856 import Max31856 
from odin_devices.max31856 import ThermocoupleType
from time import sleep


def main():
    """Create an instance of the max31856 class.

    Read and print the temperature around the device once per second until interrupted.
    """
    max = Max31856()
    # print("Launching Max31856 script.")

    try:
        while True:
            print("Thermocouple temperature is {:.1f} C".format(max.temperature))
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
