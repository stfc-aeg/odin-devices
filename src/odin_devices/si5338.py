from odin_devices.i2c_device import I2CDevice
import logging
import time


class SI5338(I2CDevice):
    # A list of the registers that should be read back when exporting the register map
    registers = [
        6, 27,28,29,30,31,
        32,33,34,35,36,37,
        38,39,40,41,42,45,
        46,47,48,49,50,51,
        52,53,54,55,56,57,
        58,59,60,61,62,63,
        64,65,66,67,68,69,
        70,71,72,73,74,75,
        76,77,78,79,80,81,
        82,83,84,85,86,87,
        88,89,90,91,92,93,
        94,95,97,98,99,100,
        101,102,103,104,105,106,
        107,108,109,110,111,112,
        113,114,115,116,117,118,
        119,120,121,122,123,124,
        125,126,127,128,129,130,
        131,132,133,134,135,136,
        137,138,139,140,141,142,
        143,144,152,153,154,155,
        156,157,158,159,160,161,
        162,163,164,165,166,167,
        168,169,170,171,172,173,
        174,175,176,177,178,179,
        180,181,182,183,184,185,
        186,187,188,189,190,191,
        192,193,194,195,196,197,
        198,199,200,201,202,203,
        204,205,206,207,208,209,
        210,211,212,213,214,215,
        216,217,230,287,288,289,
        290,291,292,293,294,295,
        296,297,298,299,303,304,
        305,306,307,308,309,310,
        311,312,313,314,315,319,
        320,321,322,323,324,325,
        326,327,328,329,330,331,
        335,336,337,338,339,340,
        341,342,343,344,345,346,
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
    }
    
    def __init__(self, address, busnum, **kwargs):
        I2CDevice.__init__(self, address, busnum, **kwargs)
        #get which page we are currently on
        self.currentPage = self.readU8(255)
        
    
    def pre_write(self):
        self.paged_read_modify_write(230, "00010000", 0b00010000)
        self.paged_read_modify_write(241, "10000000", 0b10000000)
        print("Pre-write complete.")
        
    def post_write(self, usingDownSpread):
        while (self.make8bits(str(bin(self.paged_read8(218))).replace("0b", ""))[5] == "1"):
            time.sleep(0.05)
            print("Checking input clock.")
        self.paged_read_modify_write(49, "10000000", 0b00000000)
        self.paged_read_modify_write(246, "00000010", 0b00000010)
        time.sleep(0.05)
        self.paged_read_modify_write(241, "11111111", 0x65)
        while (self.make8bits(str(bin(self.paged_read8(218))).replace("0b", ""))[3] == "1"):
            time.sleep(0.05)
            print("Checking PLL lock status.")
        self.paged_read_modify_write(47, "00000011",  self.paged_read8(237))
        self.paged_write8(46, self.paged_read8(236))
        self.paged_write8(45, self.paged_read8(235))
        self.paged_read_modify_write(47, "11111100",  0b00010100) 
        self.paged_read_modify_write(49, "10000000", 0b10000000)
        if usingDownSpread:
            self.paged_read_modify_write(226, "00000100", 0b00000100)
            time.sleep(0.02)
            self.paged_read_modify_write(226, "00000100", 0b00000000)
        self.paged_read_modify_write(230, "00010000", 0b00000000)
        print("Post-write complete.")
        
    def apply_register_map(self, filepath, usingDownSpread = False, verify=False, debug=False):
        self.pre_write()
        self.write_register_map(filepath, verify, debug)
        self.post_write(usingDownSpread)
        
    
    def write_register_map(self, filepath, verify=False, debug=False):
        """
        Write configuration from a register map generated with ClockBuilder Pro.

        :param file_path: location of register map file to be read
        :param verify: if true, each register written too by the register map will be read back to check it was written correctly
        :param debug: passed on to the page_write8 function, this parameter determines whether it will log what it is writing where
        """
        #open the file at the location provided
        with open(filepath) as file:
            text = file.read()
            #split the file into a list of its lines
            lines = text.split("\n")
            for line in lines:
                #if the line is empty, skip it
                if line == "":
                    continue
                #if the line starts with a #, it is a comment and should be skipped
                if line.strip()[0] == "#":
                    continue
                #if the line does not provide an address and value, skip it
                if len(line.split(",")) != 2:
                    print("Incorrect line: " + line + ". All lines should be structured *Address*,*Value* or start with a # to indicate they are a comment.")
                    logging.error("Incorrect line: " + line + ". All lines should be structured *Address*,*Value* or start with a # to indicate they are a comment.")
                    continue
                address = int(line.split(",")[0])
                #Skip address 27, because register 27 controls the I2C configuration and writing too it can cause issues like 
                #losing I2C control of this device
                if (address == 27):
                    continue
                #get the value we want to write and convert it from hex to decimal 
                value = int(line.split(",")[1].replace("h", ""), 16)
                self.paged_write8(address, value, debug)
            if verify:
                print("Verifying...")
                for line in lines:
                    #if the line is empty, skip it
                    if line == "":
                        continue
                    #if the line starts with a #, it is a comment and should be skipped
                    if line.strip()[0] == "#":
                        continue
                    #if the line does not provide an address and value, skip it
                    if len(line.split(",")) != 2:
                        continue
                    address = int(line.split(",")[0])
                    #Skip address 27 again because it is skipped in the writing stage
                    if (address == 27):
                        continue
                    #get the value and convert it from hex to decimal
                    value = int(line.split(",")[1].replace("h", ""), 16)
                    # read the value from the location
                    result = self.paged_read8(address)
                    #check if the expected value an actual value match
                    if (result != value):
                        print("Value " + str(result) + " found at address " + str(address) + " does not match expected value " + str(value))
                        logging.error("Value " + str(result) + " found at address " + str(address) + " does not match expected value " + str(value))
                print("Verification complete.")
    
    def paged_write8(self, reg, value, debug=False):
        #if the address is 255 or less, it is on the first page so switch to the first page (0)
        if (reg < 256):
            self.switch_page(0)
        #if the address is greater than 255 it is on the second page so switch to the second page (1)
        else:
            self.switch_page(1)
            
        mask = 0xFF
        if (reg in self.masks.keys()):
            mask = self.masks[reg]
            
        mask = self.make8bits(str(bin(mask)).replace("0b", ""))
        binValue = self.make8bits(str(bin(value)).replace("0b", ""))
        previousValue = self.make8bits(str(bin(self.paged_read8(reg))).replace("0b", ""))
        maskedValue=""
        for i in range(8):
            if (mask[i] == "1"):
                maskedValue = maskedValue + binValue[i]
            else:
                maskedValue = maskedValue + previousValue[i]
            
        if (debug and binValue != maskedValue):
            print("Some bits edited are readonly so written value " + binValue + " at address " + str(reg) + " was corrected to " + maskedValue + " due to mask " + mask + " to preserve bits from its original value, " + previousValue)
            logging.debug("Some bits edited are readonly so written value " + binValue + " at address " + str(reg) + " was corrected to " + maskedValue + " due to mask " + mask + " to preserve bits from its original value, " + previousValue)
        if (debug and maskedValue == previousValue):
            print("Value at address " + str(reg) + " is being overwritten with the same value - " + str(maskedValue))
            return
        # carry out modulus division on the address so that it is always less than 256
        self.write8(reg%256, int(maskedValue, 2))
        
        
    def paged_read_modify_write(self, reg, mask, value, debug=False):
        #if the address is 255 or less, it is on the first page so switch to the first page (0)
        if (reg < 256):
            self.switch_page(0)
        #if the address is greater than 255 it is on the second page so switch to the second page (1)
        else:
            self.switch_page(1)
            
        default_mask = 0xFF
        if (reg in self.masks.keys()):
            default_mask = self.masks[reg]
            
        default_mask = self.make8bits(str(bin(default_mask)).replace("0b", ""))
        binValue = self.make8bits(str(bin(value)).replace("0b", ""))
        previousValue = self.make8bits(str(bin(self.paged_read8(reg))).replace("0b", ""))
        maskedValue=""
        for i in range(8):
            if (mask[i] == "1" and default_mask[i] == "1"):
                maskedValue = maskedValue + binValue[i]
            else:
                maskedValue = maskedValue + previousValue[i]
            
        if (debug and binValue != maskedValue):
            print("Some bits edited are readonly so written value " + binValue + " at address " + str(reg) + " was corrected to " + maskedValue + " due to mask " + mask + " to preserve bits from its original value, " + previousValue)
            logging.debug("Some bits edited are readonly so written value " + binValue + " at address " + str(reg) + " was corrected to " + maskedValue + " due to mask " + mask + " to preserve bits from its original value, " + previousValue)
        if (debug and maskedValue == previousValue):
            print("Value at address " + str(reg) + " is being overwritten with the same value - " + str(maskedValue))
            return
        # carry out modulus division on the address so that it is always less than 256
        self.write8(reg%256, int(maskedValue, 2))
            
    def paged_read8(self, reg, debug=False):
        #if the address is 255 or less, it is on the first page so switch to the first page (0)
        if (reg < 256):
            self.switch_page(0)
        #if the address is greater than 255 it is on the second page so switch to the second page (1)
        else:
            self.switch_page(1)
        # carry out modulus division on the address so that it is always less than 256
        value = self.readU8(reg%256)
        if debug:
            print("Read value " + str(hex(value)) + " from address " + str(reg%256) + " (" + str(reg) + ") on page " + str(self.currentPage))
            logging.debug("Read value " + str(value) + " from address " + str(reg%256) + " (" + str(reg) + ") on page " + str(self.currentPage))
        return value
    
    
    def make8bits(self, value):
        while (len(value) < 8):
            value = "0" + value
        return value
    
    def switch_page(self, page):
        if (self.currentPage != page):
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
            #If they haven't entered 0 or 1, it is not a valid page index so print an err
            else:
                print("Invalid page provided: " + str(page))
                logging.error("Invalid page provided: " + str(page))
    
    
    def export_register_map(self, path_to_export_to):
        # Add in an appropriate header to the starting text
        text = """# Si5338 Registers Script
# 
# Part: Si5338
# Bits 6:0 in addr 27d/0x1B will be 0 always
# Address,Data"""
        #iterate through each address in the registers list and read it back and append it to text
        for address in self.registers:
            text = text + "\n" + str(address) + "," + hex(self.paged_read8(address)).replace("0x", "") + "h"
        #write the contents of text to a file at the path provided
        with open(path_to_export_to, "w") as file:
            file.write(text)
                

if __name__ == "__main__":
    clockGen = SI5338(0x70, 3)
    path = input("Enter path: ")
    clockGen.apply_register_map(path, False, True, False)
    #clockGen.export_register_map("./debug-SI5338-reg-map.txt")
    