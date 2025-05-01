"""
Test Cases for the SI5338 class from odin_devices
Jack Santiago, STFC Detector Systems Software Group
"""

import sys
import pytest  # type: ignore
import os


if sys.version_info[0] == 3:  # pragma: no cover
    from unittest.mock import Mock, mock_open, patch

    BUILTINS_NAME = "builtins"
else:  # pragma: no cover
    from mock import Mock, mock_open, patch

    BUILTINS_NAME = "__builtin__"

sys.modules["smbus"] = Mock()
sys.modules["logging"] = Mock()  # Track calls to logger.warning

from odin_devices.si5338 import SI5338  # noqa: E402


class si5338TestFixture(object):
    def __init__(self):
        self.si5338 = SI5338(0x70, 3)  # Create with default address

        # Create virtual registers, init to 0x00
        self.registers = dict.fromkeys(
            [
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
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
                43,
                44,
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
                96,
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
                145,
                146,
                147,
                148,
                149,
                150,
                151,
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
                218,
                219,
                220,
                221,
                222,
                223,
                224,
                225,
                226,
                227,
                228,
                229,
                230,
                231,
                232,
                233,
                234,
                235,
                236,
                237,
                238,
                239,
                240,
                241,
                242,
                243,
                244,
                245,
                246,
                247,
                248,
                249,
                250,
                251,
                252,
                253,
                254,
                255,
                256,
                257,
                258,
                259,
                260,
                261,
                262,
                263,
                264,
                265,
                266,
                267,
                268,
                269,
                270,
                271,
                272,
                273,
                274,
                275,
                276,
                277,
                278,
                279,
                280,
                281,
                282,
                283,
                284,
                285,
                286,
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
                300,
                301,
                302,
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
                316,
                317,
                318,
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
                332,
                333,
                334,
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
                348,
                349,
                350
            ],
            0x00,
        )

        self.masks = {
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

    def virtual_registers_en(self, en):
        if en:
            self.si5338.bus.read_byte_data.side_effect = self.read_virtual_regmap
            self.si5338.bus.write_byte_data.side_effect = self.write_virtual_regmap
        else:
            self.si5338.bus.read_byte_data.side_effect = None
            self.si5338.bus.write_byte_data.side_effect = None

    def read_virtual_regmap(self, address, register):
        if (register == 255):
            return self.registers[255]
        elif (self.registers[255] == 0):
            return self.registers[register]
        elif (self.registers[255] == 1):
            return self.registers[register + 256]
        else:
            raise Exception("Register 255 (paging register) should always be either 0 or 1 but is not.")
        
    def read_virtual_regmap_paged(self, address, register):
        return self.registers[register]

    def write_virtual_regmap(self, address, register, value):
        if (register == 255):
            self.registers[255] = value
        elif (self.registers[255] == 0):
            self.registers[register] = value
        elif (self.registers[255] == 1):
            self.registers[register + 256] = value
        else:
            raise Exception("Register 255 (paging register) should always be either 0 or 1 but is not.")


@pytest.fixture(scope="class")
def test_si5338_driver():
    test_driver_fixture = si5338TestFixture()
    yield test_driver_fixture


class TestSI5338:
    def test_read_modify_write(self, test_si5338_driver):
        test_si5338_driver.virtual_registers_en(True)
        value_to_write = 222
        provided_mask = 0b10101010
        test_si5338_driver.si5338.paged_read_modify_write(28, provided_mask,  value_to_write)
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 28) & provided_mask == value_to_write & provided_mask

    def test_page_switching(self, test_si5338_driver):
        test_si5338_driver.virtual_registers_en(True)
        test_value = 2
        with pytest.raises(IndexError, match="Invalid page provided: " + str(test_value) + ". Accepted values are 0 and 1."):
            test_si5338_driver.si5338.switch_page(test_value)

        test_si5338_driver.si5338.switch_page(1)
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 255) == 1
        test_si5338_driver.si5338.switch_page(0)
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 255) == 0

    def test_pre_write(self, test_si5338_driver):
        test_si5338_driver.virtual_registers_en(True)
        test_si5338_driver.si5338.pre_write()
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 230) & 0b00010000 == 0b00010000
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 241) & 0b10000000 == 0b10000000

    def test_post_write(self, test_si5338_driver):
        test_si5338_driver.virtual_registers_en(True)
        test_si5338_driver.si5338.post_write(True)
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 246) & 0b00000010 == 0b00000010
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 241) & 0b11111111 == 0x65
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 47) & 0b00000011 == test_si5338_driver.read_virtual_regmap(0x70, 237) & 0b00000011
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 46) == test_si5338_driver.read_virtual_regmap(0x70, 236) & 0b00000011
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 45) == test_si5338_driver.read_virtual_regmap(0x70, 235) & 0b00000011
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 47) & 0b11111100 == 0b00010100
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 49) & 0b10000000 == 0b10000000
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 226) & 0b00000100 == 0b00000000
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 230) & 0b00010000 == 0b00000000

    def test_export_register_map(self, test_si5338_driver, tmpdir):
        test_si5338_driver.virtual_registers_en(True)
        f = tmpdir.mkdir("sub").join("test_reg_map_file.txt")
        reg_map = r"""# Si5338 Registers Script
# 
# Part: Si5338
# Project File: C:\Users\erc97477\OneDrive - Science and Technology Facilities Council\Documents\Si5338-RevB-Project.slabtimeproj
# Bits 6:0 in addr 27d/0x1B will be 0 always
# Creator: ClockBuilder Pro v4.14 [2024-12-02]
# Created On: 2025-04-03 10:31:25 GMT+01:00
# Address,Data
6,8h
27,0h
28,16h
29,90h
30,B0h
31,C0h
32,C0h
33,E3h
34,E3h
35,Ah
36,6h
37,6h
38,0h
39,0h
40,84h
41,Ch
42,23h
45,0h
46,0h
47,14h
48,32h
49,0h
50,C3h
51,7h
52,10h
53,0h
54,D5h
55,0h
56,0h
57,0h
58,0h
59,1h
60,0h
61,0h
62,0h
63,10h
64,0h
65,12h
66,0h
67,0h
68,0h
69,0h
70,1h
71,0h
72,0h
73,0h
74,10h
75,0h
76,0h
77,0h
78,0h
79,0h
80,0h
81,0h
82,0h
83,0h
84,0h
85,10h
86,0h
87,0h
88,0h
89,0h
90,0h
91,0h
92,0h
93,0h
94,0h
95,0h
97,C0h
98,33h
99,0h
100,0h
101,0h
102,0h
103,2h
104,0h
105,0h
106,80h
107,0h
108,0h
109,0h
110,40h
111,0h
112,0h
113,0h
114,40h
115,0h
116,80h
117,0h
118,40h
119,0h
120,0h
121,0h
122,40h
123,0h
124,0h
125,0h
126,0h
127,0h
128,0h
129,0h
130,0h
131,0h
132,0h
133,0h
134,0h
135,0h
136,0h
137,0h
138,0h
139,0h
140,0h
141,0h
142,0h
143,0h
144,0h
152,0h
153,0h
154,0h
155,0h
156,0h
157,0h
158,0h
159,0h
160,0h
161,0h
162,0h
163,0h
164,0h
165,0h
166,0h
167,0h
168,0h
169,0h
170,0h
171,0h
172,0h
173,0h
174,0h
175,0h
176,0h
177,0h
178,0h
179,0h
180,0h
181,0h
182,0h
183,0h
184,0h
185,0h
186,0h
187,0h
188,0h
189,0h
190,0h
191,0h
192,0h
193,0h
194,0h
195,0h
196,0h
197,0h
198,0h
199,0h
200,0h
201,0h
202,0h
203,0h
204,0h
205,0h
206,0h
207,0h
208,0h
209,0h
210,0h
211,0h
212,0h
213,0h
214,0h
215,0h
216,0h
217,0h
230,Ch
287,0h
288,0h
289,1h
290,0h
291,0h
292,90h
293,31h
294,0h
295,0h
296,1h
297,0h
298,0h
299,0h
303,0h
304,0h
305,1h
306,0h
307,0h
308,90h
309,31h
310,0h
311,0h
312,1h
313,0h
314,0h
315,0h
319,0h
320,0h
321,1h
322,0h
323,0h
324,90h
325,31h
326,0h
327,0h
328,1h
329,0h
330,0h
331,0h
335,0h
336,0h
337,0h
338,0h
339,0h
340,90h
341,31h
342,0h
343,0h
344,1h
345,0h
346,0h
347,0h"""
        f.write(reg_map)
        assert f.read() == reg_map
        test_si5338_driver.si5338._write_register_map(f, True)
        newfile = tmpdir.join("sub/exported_reg_map_file.txt")
        test_si5338_driver.si5338.export_register_map(newfile)
        exported_regmap = newfile.read()
        assert exported_regmap == r"""# Si5338 Registers Script
#
# Part: Si5338
# Bits 6:0 in addr 27d/0x1B will be 0 always
# Address,Data
6,8h
27,0h
28,16h
29,90h
30,B0h
31,C0h
32,C0h
33,E3h
34,E3h
35,Ah
36,6h
37,6h
38,0h
39,0h
40,84h
41,Ch
42,23h
45,0h
46,0h
47,14h
48,32h
49,0h
50,C3h
51,7h
52,10h
53,0h
54,D5h
55,0h
56,0h
57,0h
58,0h
59,1h
60,0h
61,0h
62,0h
63,10h
64,0h
65,12h
66,0h
67,0h
68,0h
69,0h
70,1h
71,0h
72,0h
73,0h
74,10h
75,0h
76,0h
77,0h
78,0h
79,0h
80,0h
81,0h
82,0h
83,0h
84,0h
85,10h
86,0h
87,0h
88,0h
89,0h
90,0h
91,0h
92,0h
93,0h
94,0h
95,0h
97,C0h
98,33h
99,0h
100,0h
101,0h
102,0h
103,2h
104,0h
105,0h
106,80h
107,0h
108,0h
109,0h
110,40h
111,0h
112,0h
113,0h
114,40h
115,0h
116,80h
117,0h
118,40h
119,0h
120,0h
121,0h
122,40h
123,0h
124,0h
125,0h
126,0h
127,0h
128,0h
129,0h
130,0h
131,0h
132,0h
133,0h
134,0h
135,0h
136,0h
137,0h
138,0h
139,0h
140,0h
141,0h
142,0h
143,0h
144,0h
152,0h
153,0h
154,0h
155,0h
156,0h
157,0h
158,0h
159,0h
160,0h
161,0h
162,0h
163,0h
164,0h
165,0h
166,0h
167,0h
168,0h
169,0h
170,0h
171,0h
172,0h
173,0h
174,0h
175,0h
176,0h
177,0h
178,0h
179,0h
180,0h
181,0h
182,0h
183,0h
184,0h
185,0h
186,0h
187,0h
188,0h
189,0h
190,0h
191,0h
192,0h
193,0h
194,0h
195,0h
196,0h
197,0h
198,0h
199,0h
200,0h
201,0h
202,0h
203,0h
204,0h
205,0h
206,0h
207,0h
208,0h
209,0h
210,0h
211,0h
212,0h
213,0h
214,0h
215,0h
216,0h
217,0h
230,Ch
287,0h
288,0h
289,1h
290,0h
291,0h
292,90h
293,31h
294,0h
295,0h
296,1h
297,0h
298,0h
299,0h
303,0h
304,0h
305,1h
306,0h
307,0h
308,90h
309,31h
310,0h
311,0h
312,1h
313,0h
314,0h
315,0h
319,0h
320,0h
321,1h
322,0h
323,0h
324,90h
325,31h
326,0h
327,0h
328,1h
329,0h
330,0h
331,0h
335,0h
336,0h
337,0h
338,0h
339,0h
340,90h
341,31h
342,0h
343,0h
344,1h
345,0h
346,0h
347,0h"""

    def test_write_register_map(self, test_si5338_driver, tmpdir):
        test_si5338_driver.virtual_registers_en(True)
        with pytest.raises(FileNotFoundError, match="No such file or directory: ''"):
            test_si5338_driver.si5338._write_register_map("", False)

        f = tmpdir.mkdir("sub").join("test_reg_map_file.txt")
        reg_map = r"""# Si5338 Registers Script
# 
# Part: Si5338
# Project File: C:\Users\erc97477\OneDrive - Science and Technology Facilities Council\Documents\Si5338-RevB-Project.slabtimeproj
# Bits 6:0 in addr 27d/0x1B will be 0 always
# Creator: ClockBuilder Pro v4.14 [2024-12-02]
# Created On: 2025-04-03 10:31:25 GMT+01:00
# Address,Data
6,08h
27,00h
28,16h
29,90h

30,B0h
31,C0h
32,C0h
33,E3h
34,E3h
35,0Ah
36,06h
37,06h
38,00h
39,00h
40,84h
41,0Ch
42,23h
45,00h
46,00h
47,14h
48,32h
49,00h
50,C3h
51,07h
52,10h
53,00h
54,D5h
55,00h
56,00h
57,00h
58,00h
59,01h
60,00h
61,00h
62,00h
63,10h
64,00h
65,12h
66,00h
67,00h
68,00h
69,00h
70,01h
71,00h
72,00h
73,00h
74,10h
75,00h
76,00h
77,00h
78,00h
79,00h
80,00h
81,00h
82,00h
83,00h
84,00h
85,10h
86,00h
87,00h
88,00h
89,00h
90,00h
91,00h
92,00h
93,00h
94,00h
95,00h
97,C0h
98,33h
99,00h
100,00h
101,00h
102,00h
103,02h
104,00h
105,00h
106,80h
107,00h
108,00h
109,00h
110,40h
111,00h
112,00h
113,00h
114,40h
115,00h
116,80h
117,00h
118,40h
119,00h
120,00h
121,00h
122,40h
123,00h
124,00h
125,00h
126,00h
127,00h
128,00h
129,00h
130,00h
131,00h
132,00h
133,00h
134,00h
135,00h
136,00h
137,00h
138,00h
139,00h
140,00h
141,00h
142,00h
143,00h
144,00h
152,00h
153,00h
154,00h
155,00h
156,00h
157,00h
158,00h
159,00h
160,00h
161,00h
162,00h
163,00h
164,00h
165,00h
166,00h
167,00h
168,00h
169,00h
170,00h
171,00h
172,00h
173,00h
174,00h
175,00h
176,00h
177,00h
178,00h
179,00h
180,00h
181,00h
182,00h
183,00h
184,00h
185,00h
186,00h
187,00h
188,00h
189,00h
190,00h
191,00h
192,00h
193,00h
194,00h
195,00h
196,00h
197,00h
198,00h
199,00h
200,00h
201,00h
202,00h
203,00h
204,00h
205,00h
206,00h
207,00h
208,00h
209,00h
210,00h
211,00h
212,00h
213,00h
214,00h
215,00h
216,00h
217,00h
230,0Ch
287,00h
288,00h
289,01h
290,00h
291,00h
292,90h
293,31h
294,00h
295,00h
296,01h
297,00h
298,00h
299,00h
303,00h
304,00h
305,01h
306,00h
307,00h
308,90h
309,31h
310,00h
311,00h
312,01h
313,00h
314,00h
315,00h
319,00h
320,00h
321,01h
322,00h
323,00h
324,90h
325,31h
326,00h
327,00h
328,01h
329,00h
330,00h
331,00h
335,00h
336,00h
337,00h
338,00h
339,00h
340,90h
341,31h
342,00h
343,00h
344,01h
345,00h
346,00h
347,00h"""
        f.write(reg_map)
        assert f.read() == reg_map
        assert len(tmpdir.listdir()) == 1
        test_si5338_driver.si5338._write_register_map(f, True)

        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 6) & 0x1D == 0x08 & 0x1D
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 27) & 0x80 == 0x00 & 0x80
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 28) == 0x16
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 29) == 0x90
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 30) == 0xB0
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 31) == 0xC0
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 32) == 0xC0
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 33) == 0xE3
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 34) == 0xE3
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 35) == 0x0A
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 36) & 0x1F == 0x06 & 0x1F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 37) & 0x1F == 0x06 & 0x1F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 38) & 0x1F == 0x00 & 0x1F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 39) & 0x1F == 0x00 & 0x1F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 40) == 0x84
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 41) & 0x7F == 0x0C & 0x7F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 42) & 0x3F == 0x23 & 0x3F

        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 48) == 0x32

        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 50) == 0xC3
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 51) == 0x07
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 52) == 0x10
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 53) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 54) == 0xD5
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 55) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 56) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 57) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 58) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 59) == 0x01
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 60) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 61) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 62) & 0x3F == 0x00 & 0x3F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 63) & 0x7F == 0x10 & 0x7F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 64) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 65) == 0x12
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 66) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 67) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 68) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 69) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 70) == 0x01
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 71) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 72) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 73) & 0x3F == 0x00 & 0x3F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 74) & 0x7F == 0x10 & 0x7F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 75) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 76) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 77) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 78) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 79) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 80) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 81) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 82) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 83) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 84) & 0x3F == 0x00 & 0x3F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 85) & 0x7F == 0x10 & 0x7F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 86) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 87) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 88) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 89) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 90) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 91) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 92) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 93) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 94) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 95) & 0x3F == 0x00 & 0x3F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 97) == 0xC0
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 98) == 0x33
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 99) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 100) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 101) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 102) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 103) == 0x02
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 104) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 105) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 106) & 0xBF == 0x80 & 0xBF
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 107) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 108) & 0x7F == 0x00 & 0x7F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 109) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 110) == 0x40
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 111) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 112) & 0x7F == 0x00 & 0x7F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 113) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 114) == 0x40
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 115) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 116) == 0x80
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 117) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 118) == 0x40
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 119) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 120) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 121) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 122) == 0x40
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 123) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 124) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 125) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 126) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 127) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 128) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 129) & 0x0F == 0x00 & 0x0F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 130) & 0x0F == 0x00 & 0x0F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 131) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 132) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 133) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 134) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 135) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 136) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 137) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 138) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 139) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 140) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 141) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 142) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 143) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 144) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 152) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 153) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 154) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 155) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 156) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 157) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 158) & 0x0F == 0x00 & 0x0F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 159) & 0x0F == 0x00 & 0x0F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 160) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 161) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 162) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 163) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 164) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 165) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 166) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 167) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 168) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 169) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 170) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 171) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 172) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 173) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 174) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 175) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 176) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 177) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 178) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 179) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 180) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 181) & 0x0F == 0x00 & 0x0F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 182) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 183) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 184) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 185) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 186) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 187) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 188) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 189) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 190) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 191) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 192) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 193) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 194) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 195) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 196) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 197) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 198) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 199) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 200) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 201) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 202) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 203) & 0x0F == 0x00 & 0x0F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 204) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 205) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 206) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 207) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 208) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 209) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 210) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 211) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 212) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 213) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 214) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 215) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 216) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 217) == 0x00

        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 287) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 288) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 289) == 0x01
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 290) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 291) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 292) == 0x90
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 293) == 0x31
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 294) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 295) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 296) == 0x01
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 297) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 298) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 299) & 0x0F == 0x00 & 0x0F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 303) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 304) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 305) == 0x01
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 306) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 307) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 308) == 0x90
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 309) == 0x31
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 310) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 311) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 312) == 0x01
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 313) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 314) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 315) & 0x0F == 0x00 & 0x0F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 319) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 320) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 321) == 0x01
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 322) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 323) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 324) == 0x90
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 325) == 0x31
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 326) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 327) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 328) == 0x01
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 329) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 330) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 331) & 0x0F == 0x00 & 0x0F
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 335) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 336) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 337) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 338) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 339) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 340) == 0x90
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 341) == 0x31
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 342) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 343) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 344) == 0x01
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 345) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 346) == 0x00
        assert test_si5338_driver.read_virtual_regmap_paged(0x70, 347) & 0x0F == 0x00 & 0x0F
