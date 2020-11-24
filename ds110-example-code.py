import smbus
from bine import bine
import time

class sm_wrapper:

    def __init__(self, bus=1, addr=0x18):
        self.sm = smbus.SMBus(bus)
        self.addr = addr

    def write_data(self, reg, data):
        self.sm.write_byte_data(self.addr, reg, data)
        print hex(reg), hex(self.read_data(reg, silent=True))

    def read_data(self, reg, silent=False):
        tmp = self.sm.read_byte_data(self.addr, reg)
        if not silent:
            print hex(tmp)
        return tmp

    def write_databit(self, reg, index, data):
        tmp = self.sm.read_byte_data(self.addr, reg)
        # print hex(tmp)
        tmp = bine(tmp, 8, reverse=True)
        tmp = list(tmp)
        tmp[index] = str(data)
        tmp = "".join(tmp)
        tmp = tmp[::-1]
        # print tmp
        tmp = int(tmp, 2)
        # print tmp
        self.sm.write_byte_data(self.addr, reg, tmp)
        print hex(reg), hex(self.read_data(reg, silent=True))

    def select_channel_reg(self, val=0x05):                     # Channel settings enable and select which channel to write (can be all)
        self.write_data(0xff, val)

    def start_EOM(self, write_to_file=False):
        self.select_channel_reg(val=0x05)                       # Enable channel edit and select channel 1 only for write
        self.write_data(0x18, 0x00)                             # Divide by 1
        self.write_data(0x64, 0xff)                             # PPM delta tolerance for counter lock check group 1 = group 0 = 0xF
        self.write_databit(0x09, 2, 1)                          # Enable override divsel with register 0x18[6:4] value
        self.write_databit(0x36, 5, 1)                          # 0b11 = Fast lock all, cap dac ref clock enabled (is default setting)
        self.write_databit(0x36, 6, 1)                          # Above ^
        self.write_databit(0x00, 0, 1)                          # Reset VCO div clock domain
        self.write_databit(0x00, 1, 1)                          # Reset reference clock domain
        self.write_databit(0x00, 3, 1)                          # Reset core state machine
        self.write_data(0x00, 0)                                # !!! Reset all above, plus channel registers to restore default values...
        import time                         # Stop this madness
        time.sleep(5)
        print 'outputting debug info'
        self.read_data(0x02)                                    # Read CDR Status register
        time.sleep(2)

        self.write_databit(0x31, 5, 0)                          # 0b00 = Set no adaptation for CLTE, DFE (Default enables for CLTE only)
        self.write_databit(0x31, 6, 0)                          # Above ^

        # # Set EOM voltage range to +/- 100mv
        # self.write_databit(0x11, 7, 0)
        # self.write_databit(0x11, 6, 1)
        # # Enable eye monitor circuitry
        # self.write_databit(0x11, 5, 0)
        # # Eye monitor overide bit
        self.write_data(0x2a, 0xff)                             # EOM Sample time set to 0xFF*32 = 8160
        self.write_databit(0x3e, 7, 0)                          # Disable HEO/VEO lock monitoring
        self.write_databit(0x11, 7, 1)                          # 0b11 = +-400mV EOM Vertical range
        self.write_databit(0x11, 6, 1)                          # Above ^
        self.write_databit(0x11, 5, 0)                          # Disable EOM PD normal operation
        self.write_databit(0x23, 7, 0)                          # Override enable for EOM manual control of HEO/VEO trigger
        # Enable fast eye monitor
        self.write_databit(0x24, 7, 1)
        # Enable automatic fast eye monitor measurement. Doesn't work?
        self.write_databit(0x24, 0, 1)
        # exit(0)
        results = []
        for i in range(0, (64*64)+4):
            tmp = self.read_data(0x25, silent=True)
            tmp = (tmp, self.read_data(0x26, silent=True))
            results.append(tmp)

        # return back to normal operation
        self.write_databit(0x24, 7, 0)                          # Disable fast EOM
        self.write_databit(0x11, 5, 1)                          # Enable EOM PD normal operation
        self.write_databit(0x3e, 7, 1)                          # Enable HEO/VEO lock monitoring
        self.write_databit(0x00, 3, 1)                          # Reset core state machine
        self.write_databit(0x00, 3, 0)                          # Normal operation
        print 'outputting debug info'
        self.read_data(0x02)                                    # CDR status register
        # self.write_databit(0x11, 5, 1)
        # self.write_databit(0x3e, 7, 1)
        if write_to_file:
            with open('EOMResults.txt', 'w') as filer:
                for i in range(0, len(results)):
                    filer.write(str(results[i]) + "\n")
                filer.flush()
                filer.close()
        return results

    def config_pll_39M_200M(self):
        self.write_data(0, 0x40)                                # RESERVED??????
        self.write_data(1, 0x04)                                # RESERVED??????
        self.write_data(3, 0x10)                                # EQ boost setting, in conjunction with reg 0x2D[3]
        self.write_data(2, 0x10)                                # WRITE TO READ ONLY REGISTER?????
        self.write_data(4, 0x92)
        self.write_data(5, 0xc0)
        self.write_data(6, 0x2d)
        self.write_data(7, 0x02)
        self.write_data(8, 0)
        self.write_data(9, 0xc0)
        self.write_data(10, 0x08)
        self.write_data(11, 0x00)
        self.write_data(16, 0x00)
        self.write_data(17, 0x80)
        self.write_data(19, 0x2c)
        self.write_data(20, 0x0e)
        self.write_data(21, 0x83)
        self.write_data(22, 0x0f)
        self.write_data(23, 0x07)
        self.write_data(24, 0x07)
        self.write_data(25, 0x80)
        self.write_data(31, 0x00)
        self.write_data(32, 0x00)
        self.write_data(33, 0x03)
        self.write_data(34, 0x00)
        self.write_data(35, 0x00)
        self.write_data(36, 0x03)
        self.write_data(40, 0xC3)
        self.write_data(41, 0x0D)
        self.write_data(42, 0x3F)
        self.write_data(43, 0x00)
        self.write_data(44, 0x3D)
        self.write_data(45, 0x08)
        self.write_data(46, 0x00)
        self.write_data(47, 0xB2)
        self.write_data(48, 0x91)
        self.write_data(55, 0x00)
        self.write_data(128, 0x00)
        self.write_data(129, 0x06)
        self.write_data(130, 0x01)
        self.write_data(131, 0x07)
        self.write_data(132, 0x02)
        self.write_data(136, 0x40)
        self.write_data(138, 0x03)
        self.write_data(139, 0x33)


    def standard_config(self, div=True, adapt=1, fasteye=True, threshold=1):
        self.write_data(0xff, 0x05)
        self.write_data(0, 0xff)
        self.write_data(0, 0x00)
        if div:
            self.write_data(0x18, 0)
            self.write_databit(0x09, 2, 1)
        self.write_data(0x2A, 0xff)
        self.write_data(0x31, adapt*32)
        self.write_databit(0x1E, 3, 0)
        # disable low power mode
        self.write_databit(0x34, 6, 1)
        # max ppm_delta multiplier
        self.write_databit(0x35, 6, 1)
        self.write_databit(0x35, 7, 1)
        # write max ppm tolerence.
        self.write_data(0x64, 0xff)
        self.write_databit(0x67, 6, 1)
        self.write_databit(0x67, 7, 1)
        if fasteye:
            self.write_databit(0x39, 5, 1)
            self.write_databit(0x39, 6, 1)
        # writes veo and heo theshold for lock
        self.write_data(0x6a, (threshold*16)+threshold)

    def exp_config(self,  div=False, adapt=1, fasteye=True, threshold=3, vclamp_10g=False):
        self.write_data(0xff, 0x07)                             # Set register target to channel 3 only
        self.write_data(0, 0xff)                                # Reset core state machine, channel regs, ref clock domain, VCO div clock
        self.write_data(0, 0x00)                                # Normal operation
        if div:
            self.write_data(0x18, 0)                            # Set divide by 1
            # self.write_databit(0x18, 4, 1)
            self.write_databit(0x09, 2, 1)                      # Override enable for divesel in reg 0x18
        self.write_data(0x2A, 0xff)                             # EOM Sample time set to 0xFF*32 = 8160
        self.write_data(0x31, adapt*32)                         # Set adapt mode (1 = CTLE only, the default)
        self.write_databit(0x1E, 3, 0)                          # Enable DFE
        # disable low power mode
        # self.write_databit(0x34, 6, 1)
        # set VOD levels to 1.2V
        self.write_databit(0x2d, 1, 1)
        self.write_databit(0x2d, 2, 1)
        self.write_databit(0x2d, 0, 1)
        # set DEM to -0.9db
        self.write_databit(0x15, 0, 1)
        self.write_databit(0x15, 1, 0)
        self.write_databit(0x15, 2, 0)
        self.write_databit(0x15, 6, 1)
        # max ppm_delta multiplier
        self.write_databit(0x35, 6, 0)
        self.write_databit(0x35, 7, 0)
        # write max ppm tolerence.
        self.write_data(0x64, 0xff)
        # self.write_databit(0x67, 6, 0)
        # self.write_databit(0x67, 7, 0)
        if fasteye:
            self.write_databit(0x39, 5, 1)                      # 0b11 = EOM rate set to full rate, fastest
            self.write_databit(0x39, 6, 1)                      # Above ^
        # writes veo and heo theshold for lock
        self.write_data(0x6a, (threshold*16)+threshold)         # Set VEO and HEO threshold to same value = threshold

        # set rates
        self.write_data(0x60, 133)                              # Group 0 count LSB
        self.write_data(0x61, 51)                               # Group 0 count MSB (excluding bit 7)
        self.write_databit(0x61, 7, 0)                          # Override DISABLE for group 0 manual data rate selection????????????????????????????????????????????????
        self.write_data(0x62, 133)                              # Group 1 count LSB
        self.write_data(0x63, 51)                               # Group 1 count MSB
        self.write_databit(0x63, 7, 1)                          # Override enable for group 1 manual data rate selection
        self.write_data(0x64, 0xFF)                             # PPM delata tolarance for counter lock check for both groups = 0xF
        if vclamp_10g:
            self.write_data(0x60, 39)
            self.write_data(0x61, 49)
            self.write_databit(0x61, 7, 1)                      # This time, group 0 manual data rate is enabled
            self.write_data(0x62, 39)
            self.write_data(0x63, 49)
        # sets subrate
        # 5G =  4'b1010
        # 10G = 4'b1000
        self.write_databit(0x2f, 7, 0)
        self.write_databit(0x2f, 5, 0)
        self.write_databit(0x2f, 1, 0)                          # FLD check disabled
        self.write_databit(0x18, 2, 0)                          # DRV_SEL_SLOW = 0?
        #
        # reset sm
        self.write_databit(0, 0, 1)
        self.write_databit(0, 1, 1)
        self.write_databit(0, 3, 1)
        self.write_data(0, 0x00)


    def standard_calib(self, eom_vrange=0, write_to_file=True):
        # permently powers eyemonitor
        self.write_databit(0x11, 5, 0)
        self.write_databit(0x11, 7, int('{0:02b}'.format(eom_vrange)[0]))  # str is in reverse
        self.write_databit(0x11, 6, int('{0:02b}'.format(eom_vrange)[1]))

        # disables cdr
        self.write_databit(0x3e, 7, 0)
        self.write_databit(0x24, 0, 1)
        self.write_databit(0x23, 7, 1)
        self.write_databit(0x24, 7, 1)

        results = []
        for i in range(0, (64*64)+4):
            tmp = self.read_data(0x26, silent=True)
            tmp = int(self.read_data(0x25, silent=True) * 256) + int(tmp)
            # tmp = (self.read_data(0x25, silent=True), tmp)
            results.append(tmp)

        heo = self.read_data(0x27, silent=True)
        veo = self.read_data(0x28, silent=True)

        # back to normal operation
        self.write_databit(0x24, 0, 0)
        self.write_databit(0x24, 7, 0)
        self.write_databit(0x11, 5, 1)
        self.write_databit(0x23, 7, 0)
        self.write_databit(0x3e, 7, 1)

        if write_to_file:
            with open('EOMResults.txt', 'w') as filer:
                filer.write('VEO ' + str(veo) + "\n")
                filer.write('HEO ' + str(heo) + "\n")
                for i in range(0, len(results)):
                    filer.write(str(results[i]) + "\n")
                filer.flush()
                filer.close()
        return results

    def get_status(self):
        print 'Reset Reg: ' + hex(int(self.read_data(0x00, silent=True)))
        tmp = self.read_data(0x01, silent=True)
        tmp = '{0:08b}'.format(int(tmp))[::-1]

        print 'CDR LOCK LOSS INT: ' + str(tmp[4])
        print 'SIG LOCK LOSS INT: ' + str(tmp[0])
        tmp = self.read_data(0x30, silent=True)
        tmp = '{0:08b}'.format(int(tmp))[::-1]
        print 'EOM VRANGE LIMIT ERROR: ' + str(tmp[5])
        print 'HEO VEO INT: ' + str(tmp[4])
        tmp = self.read_data(0x02, silent=True)
        print hex(int(tmp))
        tmp = '{0:08b}'.format(int(tmp))[::-1]
        for i in range(0, 8):
            if i == 0 and tmp[i] == '1':
                print 'Comp LPF Low ' + str(tmp[i])
            if i == 1 and tmp[i] == '1':
                print 'Comp LPF High ' + str(tmp[i])
            if i == 2 and tmp[i] == '1':
                print 'Single Bit Limit Reached ' + str(tmp[i])
            if i == 3 and tmp[i] == '1':
                print 'CDR Lock ' + str(tmp[i])
            if i == 4 and tmp[i] == '1':
                print 'LOCK ' + str(tmp[i])
            if i == 5 and tmp[i] == '1':
                print 'Fail Lock Check ' + str(tmp[i])
            if i == 6 and tmp[i] == '1':
                print 'Auto Adapt Complete ' + str(tmp[i])
            if i == 7 and tmp[i] == '1':
                print 'PPM Count Met ' + str(tmp[i])
        status_arr = []  # as status reg seems buggy...
        for i in range(0, 20):
            status_arr.append(hex(int(self.read_data(0x02, silent=True))))
        print 'Status Reg Reads: ' + str(status_arr)

        heo = self.read_data(0x27, silent=True)
        veo = self.read_data(0x28, silent=True)
        print 'HEO ' + str(heo)
        print 'VEO ' + str(veo)

    def select_output(self, output='default'):
        if output == 'default':
            self.write_databit(0x09, 5, 0)
            self.write_databit(0x30, 3, 0)
            self.write_databit(0x1E, 7, 1)
            self.write_databit(0x1E, 6, 1)
            self.write_databit(0x1E, 5, 1)

        else:
            self.write_databit(0x09, 5, 1)

        if output == 'raw':
            self.write_databit(0x1E, 7, 0)
            self.write_databit(0x1E, 6, 0)
            self.write_databit(0x1E, 5, 0)
            self.write_databit(0x30, 3, 0)
        elif output == 'force':
            self.write_databit(0x1E, 7, 0)
            self.write_databit(0x1E, 6, 0)
            self.write_databit(0x1E, 5, 1)
            self.write_databit(0x30, 3, 0)
        elif output == 'prbs':
            self.write_databit(0x1E, 7, 1)
            self.write_databit(0x1E, 6, 0)
            self.write_databit(0x1E, 5, 0)
            self.write_databit(0x1E, 4, 1)
            self.write_databit(0x30, 3, 1)


    def main_run(self):
		# Configs the retimer, leave vclamp_10g=False
        self.exp_config(vclamp_10g=False)
		# Calibrates eom range, not nessessary for normal operation
        self.standard_calib(eom_vrange=3)
        time.sleep(5)
		# Probe retimer debug registers
        self.get_status()
		time.sleep(10)
        self.exp_config(vclamp_10g=False)
		# Measures eye and reads out.
		start_EOM(write_to_file=False):
		# Switches retimer output 'type'.
        self.select_output(output='raw')
