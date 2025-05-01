"""SI5338 class.
    Data sheet:
        https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5338.pdf
    Reference manual:
        https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/Si5338-RM.pdf

Jack Santiago, STFC DSSG.
"""

from odin_devices.i2c_device import I2CDevice
import logging
import time


class SI5338(I2CDevice):
    """SI5338 class to access an si5338 clock generator over i2c and write register maps generated
    using clockbuilder pro to it"""
    registers = [
        6,
        27,
        28,
        29,
        30,
        31,
        32,
        33,
        34,
        35,
        36,
        37,
        38,
        39,
        40,
        41,
        42,
        45,
        46,
        47,
        48,
        49,
        50,
        51,
        52,
        53,
        54,
        55,
        56,
        57,
        58,
        59,
        60,
        61,
        62,
        63,
        64,
        65,
        66,
        67,
        68,
        69,
        70,
        71,
        72,
        73,
        74,
        75,
        76,
        77,
        78,
        79,
        80,
        81,
        82,
        83,
        84,
        85,
        86,
        87,
        88,
        89,
        90,
        91,
        92,
        93,
        94,
        95,
        97,
        98,
        99,
        100,
        101,
        102,
        103,
        104,
        105,
        106,
        107,
        108,
        109,
        110,
        111,
        112,
        113,
        114,
        115,
        116,
        117,
        118,
        119,
        120,
        121,
        122,
        123,
        124,
        125,
        126,
        127,
        128,
        129,
        130,
        131,
        132,
        133,
        134,
        135,
        136,
        137,
        138,
        139,
        140,
        141,
        142,
        143,
        144,
        152,
        153,
        154,
        155,
        156,
        157,
        158,
        159,
        160,
        161,
        162,
        163,
        164,
        165,
        166,
        167,
        168,
        169,
        170,
        171,
        172,
        173,
        174,
        175,
        176,
        177,
        178,
        179,
        180,
        181,
        182,
        183,
        184,
        185,
        186,
        187,
        188,
        189,
        190,
        191,
        192,
        193,
        194,
        195,
        196,
        197,
        198,
        199,
        200,
        201,
        202,
        203,
        204,
        205,
        206,
        207,
        208,
        209,
        210,
        211,
        212,
        213,
        214,
        215,
        216,
        217,
        230,
        287,
        288,
        289,
        290,
        291,
        292,
        293,
        294,
        295,
        296,
        297,
        298,
        299,
        303,
        304,
        305,
        306,
        307,
        308,
        309,
        310,
        311,
        312,
        313,
        314,
        315,
        319,
        320,
        321,
        322,
        323,
        324,
        325,
        326,
        327,
        328,
        329,
        330,
        331,
        335,
        336,
        337,
        338,
        339,
        340,
        341,
        342,
        343,
        344,
        345,
        346,
        347,
    ]

    masks = {
        0: 0x00,
        1: 0x00,
        2: 0x00,
        3: 0x00,
        4: 0x00,
        5: 0x00,
        6: 0x1D,
        7: 0x00,
        8: 0x00,
        9: 0x00,
        10: 0x00,
        11: 0x00,
        12: 0x00,
        13: 0x00,
        14: 0x00,
        15: 0x00,
        16: 0x00,
        17: 0x00,
        18: 0x00,
        19: 0x00,
        20: 0x00,
        21: 0x00,
        22: 0x00,
        23: 0x00,
        24: 0x00,
        25: 0x00,
        26: 0x00,
        27: 0x80,
        28: 0xFF,
        29: 0xFF,
        30: 0xFF,
        31: 0xFF,
        32: 0xFF,
        33: 0xFF,
        34: 0xFF,
        35: 0xFF,
        36: 0x1F,
        37: 0x1F,
        38: 0x1F,
        39: 0x1F,
        40: 0xFF,
        41: 0x7F,
        42: 0x3F,
        43: 0x00,
        44: 0x00,
        45: 0xFF,
        46: 0xFF,
        47: 0xFF,
        48: 0xFF,
        49: 0xFF,
        50: 0xFF,
        51: 0xFF,
        52: 0x7F,
        53: 0xFF,
        54: 0xFF,
        55: 0xFF,
        56: 0xFF,
        57: 0xFF,
        58: 0xFF,
        59: 0xFF,
        60: 0xFF,
        61: 0xFF,
        62: 0x3F,
        63: 0x7F,
        64: 0xFF,
        65: 0xFF,
        66: 0xFF,
        67: 0xFF,
        68: 0xFF,
        69: 0xFF,
        70: 0xFF,
        71: 0xFF,
        72: 0xFF,
        73: 0x3F,
        74: 0x7F,
        75: 0xFF,
        76: 0xFF,
        77: 0xFF,
        78: 0xFF,
        79: 0xFF,
        80: 0xFF,
        81: 0xFF,
        82: 0xFF,
        83: 0xFF,
        84: 0x3F,
        85: 0x7F,
        86: 0xFF,
        87: 0xFF,
        88: 0xFF,
        89: 0xFF,
        90: 0xFF,
        91: 0xFF,
        92: 0xFF,
        93: 0xFF,
        94: 0xFF,
        95: 0x3F,
        96: 0x00,
        97: 0xFF,
        98: 0xFF,
        99: 0xFF,
        100: 0xFF,
        101: 0xFF,
        102: 0xFF,
        103: 0xFF,
        104: 0xFF,
        105: 0xFF,
        106: 0xBF,
        107: 0xFF,
        108: 0x7F,
        109: 0xFF,
        110: 0xFF,
        111: 0xFF,
        112: 0x7F,
        113: 0xFF,
        114: 0xFF,
        115: 0xFF,
        116: 0xFF,
        117: 0xFF,
        118: 0xFF,
        119: 0xFF,
        120: 0xFF,
        121: 0xFF,
        122: 0xFF,
        123: 0xFF,
        124: 0xFF,
        125: 0xFF,
        126: 0xFF,
        127: 0xFF,
        128: 0xFF,
        129: 0x0F,
        130: 0x0F,
        131: 0xFF,
        132: 0xFF,
        133: 0xFF,
        134: 0xFF,
        135: 0xFF,
        136: 0xFF,
        137: 0xFF,
        138: 0xFF,
        139: 0xFF,
        140: 0xFF,
        141: 0xFF,
        142: 0xFF,
        143: 0xFF,
        144: 0xFF,
        145: 0x00,
        146: 0x00,
        147: 0x00,
        148: 0x00,
        149: 0x00,
        150: 0x00,
        151: 0x00,
        152: 0xFF,
        153: 0xFF,
        154: 0xFF,
        155: 0xFF,
        156: 0xFF,
        157: 0xFF,
        158: 0x0F,
        159: 0x0F,
        160: 0xFF,
        161: 0xFF,
        162: 0xFF,
        163: 0xFF,
        164: 0xFF,
        165: 0xFF,
        166: 0xFF,
        167: 0xFF,
        168: 0xFF,
        169: 0xFF,
        170: 0xFF,
        171: 0xFF,
        172: 0xFF,
        173: 0xFF,
        174: 0xFF,
        175: 0xFF,
        176: 0xFF,
        177: 0xFF,
        178: 0xFF,
        179: 0xFF,
        180: 0xFF,
        181: 0x0F,
        182: 0xFF,
        183: 0xFF,
        184: 0xFF,
        185: 0xFF,
        186: 0xFF,
        187: 0xFF,
        188: 0xFF,
        189: 0xFF,
        190: 0xFF,
        191: 0xFF,
        192: 0xFF,
        193: 0xFF,
        194: 0xFF,
        195: 0xFF,
        196: 0xFF,
        197: 0xFF,
        198: 0xFF,
        199: 0xFF,
        200: 0xFF,
        201: 0xFF,
        202: 0xFF,
        203: 0x0F,
        204: 0xFF,
        205: 0xFF,
        206: 0xFF,
        207: 0xFF,
        208: 0xFF,
        209: 0xFF,
        210: 0xFF,
        211: 0xFF,
        212: 0xFF,
        213: 0xFF,
        214: 0xFF,
        215: 0xFF,
        216: 0xFF,
        217: 0xFF,
        218: 0x00,
        219: 0x00,
        220: 0x00,
        221: 0x00,
        222: 0x00,
        223: 0x00,
        224: 0x00,
        225: 0x00,
        226: 0x04,
        227: 0x00,
        228: 0x00,
        229: 0x00,
        230: 0xFF,
        231: 0x00,
        232: 0x00,
        233: 0x00,
        234: 0x00,
        235: 0x00,
        236: 0x00,
        237: 0x00,
        238: 0x00,
        239: 0x00,
        240: 0x00,
        241: 0xFF,
        242: 0x02,
        243: 0x00,
        244: 0x00,
        245: 0x00,
        246: 0xFF,
        247: 0x00,
        248: 0x00,
        249: 0x00,
        250: 0x00,
        251: 0x00,
        252: 0x00,
        253: 0x00,
        254: 0x00,
        255: 0xFF,
        256: 0x00,
        257: 0x00,
        258: 0x00,
        259: 0x00,
        260: 0x00,
        261: 0x00,
        262: 0x00,
        263: 0x00,
        264: 0x00,
        265: 0x00,
        266: 0x00,
        267: 0x00,
        268: 0x00,
        269: 0x00,
        270: 0x00,
        271: 0x00,
        272: 0x00,
        273: 0x00,
        274: 0x00,
        275: 0x00,
        276: 0x00,
        277: 0x00,
        278: 0x00,
        279: 0x00,
        280: 0x00,
        281: 0x00,
        282: 0x00,
        283: 0x00,
        284: 0x00,
        285: 0x00,
        286: 0x00,
        287: 0xFF,
        288: 0xFF,
        289: 0xFF,
        290: 0xFF,
        291: 0xFF,
        292: 0xFF,
        293: 0xFF,
        294: 0xFF,
        295: 0xFF,
        296: 0xFF,
        297: 0xFF,
        298: 0xFF,
        299: 0x0F,
        300: 0x00,
        301: 0x00,
        302: 0x00,
        303: 0xFF,
        304: 0xFF,
        305: 0xFF,
        306: 0xFF,
        307: 0xFF,
        308: 0xFF,
        309: 0xFF,
        310: 0xFF,
        311: 0xFF,
        312: 0xFF,
        313: 0xFF,
        314: 0xFF,
        315: 0x0F,
        316: 0x00,
        317: 0x00,
        318: 0x00,
        319: 0xFF,
        320: 0xFF,
        321: 0xFF,
        322: 0xFF,
        323: 0xFF,
        324: 0xFF,
        325: 0xFF,
        326: 0xFF,
        327: 0xFF,
        328: 0xFF,
        329: 0xFF,
        330: 0xFF,
        331: 0x0F,
        332: 0x00,
        333: 0x00,
        334: 0x00,
        335: 0xFF,
        336: 0xFF,
        337: 0xFF,
        338: 0xFF,
        339: 0xFF,
        340: 0xFF,
        341: 0xFF,
        342: 0xFF,
        343: 0xFF,
        344: 0xFF,
        345: 0xFF,
        346: 0xFF,
        347: 0x0F,
        348: 0x00,
        349: 0x00,
        350: 0x00
    }

    def __init__(self, address, busnum, **kwargs):
        """Initialise the class - initialise the parent class and get the current page we are on.

        Args:
            address (int): the i2c address of this device
            busnum (int): the i2c bus this device is on
        """
        I2CDevice.__init__(self, address, busnum, **kwargs)
        # get which page we are currently on
        self.currentPage = self.readU8(255)

    def pre_write(self):
        """carry out the operations necessary before writing a register map to the device"""
        # Disable all outputs
        self.paged_read_modify_write(230, 0b00010000, 0b00010000)
        # Pause LOL
        self.paged_read_modify_write(241, 0b10000000, 0b10000000)

    def post_write(self, usingDownSpread=False):
        """carry out the operations necessary after writing a register map to the device to load
        the register map

        Args:
            usingDownSpread (bool, optional): extra operations have to be run post-register map
            write if you are using down spread. Defaults to False.
        """
        # Wait for valid input clock status
        while self.paged_read8(218) & 100 == 0b100:
            time.sleep(0.05)  # pragma: no cover
            logging.debug("Checking input clock.")  # pragma: no cover
        # Configure PLL for locking
        self.paged_read_modify_write(49, 0b10000000, 0b00000000)
        # Initiate locking of PLL
        self.paged_read_modify_write(246, 0b00000010, 0b00000010)
        time.sleep(0.05)
        # Restart LOL
        self.paged_read_modify_write(241, 0b11111111, 0x65)
        # Wait to confirm PLL lock
        while self.paged_read8(218) & 10000 == 0b10000:
            time.sleep(0.05)  # pragma: no cover
            logging.debug("Checking PLL lock status.")  # pragma: no cover
        # Copy FCAL values to active registers
        self.paged_read_modify_write(47, 0b00000011, self.paged_read8(237))
        self.paged_write8(46, self.paged_read8(236))
        self.paged_write8(45, self.paged_read8(235))
        self.paged_read_modify_write(47, 0b11111100, 0b00010100)
        # Set PLL to use FCAL values
        self.paged_read_modify_write(49, 0b10000000, 0b10000000)
        # if we are using down spread write the necessary registers
        if usingDownSpread:
            self.paged_read_modify_write(226, 0b00000100, 0b00000100)
            time.sleep(0.02)  # pragma: no cover
            self.paged_read_modify_write(226, 0b00000100, 0b00000000)
        # enable outputs
        self.paged_read_modify_write(230, 0b00010000, 0b00000000)

    def apply_register_map(self, filepath, usingDownSpread=False, verify=False):
        """Apply the necessary pre-register map write operations, write a register map from a given
        file, then apply the necessary post-register map write operations

        Args:
            filepath (string): the path to the register map file, including the extension
            usingDownSpread (bool, optional): extra operations have to be run post-register map
            write if you are using down spread. Defaults to False.
            verify (bool, optional): whether all the writes of the register map should be read back
            to ensure they have all been written correctly. Defaults to False.
        """
        # Do everything necessary before writing a register map
        self.pre_write()
        # write a register map
        self._write_register_map(filepath, verify)
        # do everything necessary after writing a register map
        self.post_write(usingDownSpread)

    def _write_register_map(self, filepath, verify=False):
        """load a register map from the provided fire path and write it to the device

        Args:
            filepath (string): the path to the register map file, including the extension
            verify (bool, optional): whether all the writes of the register map should be read back
            to ensure they have all been written correctly. Defaults to False.
        """
        # open the file at the location provided
        with open(filepath) as file:
            text = file.read()
            # split the file into a list of its lines
            lines = text.split("\n")
            for line in lines:
                # if the line is empty, skip it
                if line == "":
                    continue  # pragma: no cover
                # if the line starts with a #, it is a comment and should be skipped
                if line.strip()[0] == "#":
                    continue  # pragma: no cover

                # if the line does not provide an address and value, skip it
                if len(line.split(",")) != 2:
                    logging.error(
                        "Incorrect line: \n"
                        + line
                        + "\n All lines should be structured *Address*,*Value* or start with a # "
                        + "to indicate they are a comment."
                    )  # pragma: no cover
                    continue  # pragma: no cover
                address = int(line.split(",")[0])
                # Skip address 27, because register 27 controls the I2C configuration and writing
                # to it can cause issues like losing I2C control of this device
                if address == 27:
                    continue
                # get the value we want to write and convert it from hex to decimal
                value = int(line.split(",")[1].replace("h", ""), 16)
                self.paged_write8(address, value)
            if verify:
                for line in lines:
                    # if the line is empty, skip it
                    if line == "":
                        continue
                    # if the line starts with a #, it is a comment and should be skipped
                    if line.strip()[0] == "#":
                        continue
                    # if the line does not provide an address and value, skip it
                    if len(line.split(",")) != 2:
                        continue
                    address = int(line.split(",")[0])
                    # Skip address 27 again because it is skipped in the writing stage
                    if address == 27:
                        continue
                    # get the value and convert it from hex to decimal
                    value = int(line.split(",")[1].replace("h", ""), 16)
                    # read the value from the location
                    result = self.paged_read8(address)
                    mask = 0xFF
                    if address in self.masks.keys():
                        mask = self.masks[address]
                    # check if the expected value an actual value match
                    if result & mask != value & mask:
                        logging.error(
                            "Value "
                            + str(result)
                            + " found at address "
                            + str(address)
                            + " does not match expected value "
                            + str(value)
                        )
                logging.debug("Verification complete.")

    def paged_write8(self, reg, value):
        """Write an 8 bit value to the provided address switching to the appropriate page and
        accounting for that register's mask.

        If the address is greater than 255, automatically write to the paging register to switch to
        page 1, otherwise switch to page 0.
        This function also loads the mask for the provided address, and masks off the given values
        to prevent writes to bits that shouldn't be written too.
        Write the masked value to the address provided,

        Args:
            reg (int): The address of the register you want to write to, between 0 to 347.
            value (int): The value you want written to the register between 0 and 255
        """
        # if the address is 255 or less, it is on the first page so switch to the first page (0)
        if reg < 256:
            self.switch_page(0)
        # if the address is greater than 255 it is on the second page so switch to the second
        # page (1)
        else:
            self.switch_page(1)

        # Each register has a mask provided by the data sheet tot tell you which bits you are
        # allowed to write to. Set this as default to FF (all bits can be written to) and then try
        # to retrieve a mask for the current register from the dictionary of addresses to masks.
        mask = 0xFF
        if reg in self.masks.keys():
            mask = self.masks[reg]

        previousValue = self.paged_read8(reg)
        maskedValue = (value & mask) | (previousValue & ~mask)

        # carry out modulus division on the address so that it is always less than 256
        self.write8(reg % 256, maskedValue)

    def paged_read_modify_write(self, reg, provided_mask, value):
        """read a register, modify it with the provided value leaving the masked bits the same as
        they were before and then write the new value back to the register

        Args:
            reg (int): the address of the register we want to read modify then write
            provided_mask (string): a binary string of zeroes and ones telling us which bits we
            want to write and which should remain as they were read
            value (int): the value we want to write to the register
        """
        # if the address is 255 or less, it is on the first page so switch to the first page (0)
        if reg < 256:
            self.switch_page(0)
        # if the address is greater than 255 it is on the second page so switch to the second
        # page (1)
        else:
            self.switch_page(1)

        # Each register has a mask provided by the data sheet tot tell you which bits you are
        # allowed to write to. Set this as default to FF (all bits can be written to) and then try
        # to retrieve a mask for the current register from the dictionary of addresses to masks.
        system_mask = 0xFF
        if reg in self.masks.keys():
            system_mask = self.masks[reg]

        previousValue = self.paged_read8(reg)
        maskedValue = (value & system_mask & provided_mask) | (
            previousValue & ~(system_mask & provided_mask))

        # carry out modulus division on the address so that it is always less than 256
        self.write8(reg % 256, maskedValue)

    def paged_read8(self, reg):
        """Read the 8 bit value from a provided address, switching pages automatically for
        addresses larger than 255.

        Args:
            reg (int): the address of the register to read

        Returns:
            int: the value read from the address provided. This will be -1 if the read fails
            e.g. due to no i2c connection
        """
        # if the address is 255 or less, it is on the first page so switch to the first page (0)
        if reg < 256:
            self.switch_page(0)
        # if the address is greater than 255 it is on the second page so switch to the second
        # page (1)
        else:
            self.switch_page(1)
        # carry out modulus division on the address so that it is always less than 256
        value = self.readU8(reg % 256)
        return value

    def switch_page(self, page):
        """Write to the page select register to switch whether we are writing to the registers on
        page 0 or page 1.

        Args:
            page (int): The page to switch to, should be either 0 or 1.
        """
        # Check we are not already on the write page
        if self.currentPage != page:
            # if they want to switch to page 0, set the value of
            # the PAGE_SEL register, address 255 to 0 and set currentPage to 0
            if page == 0:
                self.write8(255, 0)
                self.currentPage = 0
            # if they want to switch to page 1, set the value of
            # the PAGE_SEL register, address 255 to 1 and set currentPage to 1
            elif page == 1:
                self.write8(255, 1)
                self.currentPage = 1
            # If they haven't entered 0 or 1, it is not a valid page index so print an err
            else:
                raise IndexError("Invalid page provided: " + str(page) + ". Accepted values are 0 and 1.")

    def export_register_map(self, path_to_export_to):
        """Read back various registers, generate a string from them and write that string to a file
        at the given location

        Args:
            path_to_export_to (string): the path we want to write the new register map file to
            - including extension
        """
        # Add in an appropriate header to the starting text
        text = """# Si5338 Registers Script
#
# Part: Si5338
# Bits 6:0 in addr 27d/0x1B will be 0 always
# Address,Data"""
        # iterate through each address in the registers list and read it back and append it to text
        for address in self.registers:
            text = (
                text
                + "\n"
                + str(address)
                + ","
                + hex(self.paged_read8(address)).replace("0x", "")
                + "h"
            )
        # write the contents of text to a file at the path provided
        with open(path_to_export_to, "w") as file:
            file.write(text)


if __name__ == "__main__":
    clockGen = SI5338(0x70, 3)
    path = input("Enter path: ")
    clockGen.apply_register_map(path, False, True)
