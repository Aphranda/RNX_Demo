import unittest
import math

import time
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))  # 调整路径层级
print(str(Path(__file__).parent.parent.parent))

from src.app.utils.SignalUnitConverter import SignalUnitConverter

class TestSignalUnitConverter(unittest.TestCase):
    """SignalUnitConverter 单元测试类"""
    
    def setUp(self):
        self.converter = SignalUnitConverter()
    
    def test_safe_float_convert(self):
        """测试安全浮点数转换"""
        self.assertEqual(self.converter.safe_float_convert("10.5"), 10.5)
        self.assertEqual(self.converter.safe_float_convert("-3.14"), -3.14)
        self.assertEqual(self.converter.safe_float_convert("1e3"), 1000.0)
        self.assertEqual(self.converter.safe_float_convert("10MHz"), 10.0)
        self.assertEqual(self.converter.safe_float_convert("abc", 5.0), 5.0)
        self.assertEqual(self.converter.safe_float_convert(42), 42.0)
        self.assertEqual(self.converter.safe_float_convert(None, 1.0), 1.0)
    
    def test_convert_frequency(self):
        """测试频率单位转换"""
        # GHz转换
        self.assertAlmostEqual(self.converter.convert_frequency(1, 'GHz', 'Hz')[0], 1e9)
        self.assertAlmostEqual(self.converter.convert_frequency(1, 'GHz', 'MHz')[0], 1e3)
        # MHz转换
        self.assertAlmostEqual(self.converter.convert_frequency(100, 'MHz', 'GHz')[0], 0.1)
        self.assertAlmostEqual(self.converter.convert_frequency(1, 'MHz', 'kHz')[0], 1e3)
        # kHz转换
        self.assertAlmostEqual(self.converter.convert_frequency(1, 'kHz', 'Hz')[0], 1e3)
        # 边界值测试
        self.assertEqual(self.converter.convert_frequency(0, 'GHz', 'Hz')[0], 0.0)
        # 无效单位测试
        self.assertEqual(self.converter.convert_frequency(10, 'GHz', 'invalid')[0], 10.0)
    
    def test_convert_power(self):
        """测试功率单位转换"""
        # dBm <-> mW
        self.assertAlmostEqual(self.converter.convert_power(0, 'dBm', 'mW')[0], 1.0)
        self.assertAlmostEqual(self.converter.convert_power(10, 'dBm', 'mW')[0], 10.0)
        self.assertAlmostEqual(self.converter.convert_power(1, 'mW', 'dBm')[0], 0.0)
        # dBm <-> W
        self.assertAlmostEqual(self.converter.convert_power(30, 'dBm', 'W')[0], 1.0)
        self.assertAlmostEqual(self.converter.convert_power(1, 'W', 'dBm')[0], 30.0)
        # dBm <-> dBW
        self.assertAlmostEqual(self.converter.convert_power(30, 'dBm', 'dBW')[0], 0.0)
        self.assertAlmostEqual(self.converter.convert_power(0, 'dBW', 'dBm')[0], 30.0)
        # 边界值测试
        self.assertEqual(self.converter.convert_power(-math.inf, 'dBm', 'mW')[0], 0.0)
        self.assertEqual(self.converter.convert_power(0, 'mW', 'dBm')[0], -math.inf)
    
    def test_format_frequency(self):
        """测试频率格式化"""
        # 测试自动格式化
        self.assertEqual(self.converter.format_frequency(1e9), "1.000000 GHz")  # 1.00 而不是 1.000000
        self.assertEqual(self.converter.format_frequency(123.456e6), "123.456 MHz")  # 保留3位小数
        self.assertEqual(self.converter.format_frequency(123456), "123.5 kHz")  # 保留1位小数
        self.assertEqual(self.converter.format_frequency(100), "100 Hz")  # 整数Hz
        
        # 测试指定单位格式化
        self.assertEqual(self.converter.format_frequency(1e9, 'GHz'), "1.000000 GHz")  # 指定单位时保留6位小数
        self.assertEqual(self.converter.format_frequency(123.456e6, 'MHz'), "123.456000 MHz")
        
        # 测试无效输入
        self.assertEqual(self.converter.format_frequency("invalid", 'GHz'), "0.000000 GHz")
 
    def test_format_power(self):
        """测试功率格式化"""
        # 测试指定单位格式化
        self.assertEqual(self.converter.format_power(0, 'dBm'), "0.00 dBm")  # dB单位保留2位小数
        self.assertEqual(self.converter.format_power(1, 'mW'), "1.258925 mW")  # 线性单位保留6位小数
        self.assertEqual(self.converter.format_power(0.001, 'W'), "0.001000 W")
        
        # 测试自动格式化
        self.assertEqual(self.converter.format_power(30, None), "1.000000 W")  # 自动选择最佳单位
        self.assertEqual(self.converter.format_power(0.1, None), "100.000 mW")
        self.assertEqual(self.converter.format_power(0.0001, None), "100.000 µW")
        self.assertEqual(self.converter.format_power(-10, None), "0.10 mW")  # 负dBm值
        
        # 测试边界值
        self.assertEqual(self.converter.format_power(1e-9, 'W'), "0.000000 W")  # 极小值
    
    def test_validate_frequency(self):
        """测试频率验证"""
        valid, val, unit = self.converter.validate_frequency("10GHz")
        self.assertTrue(valid)
        self.assertEqual(val, 10.0)
        self.assertEqual(unit, "GHz")
        
        valid, val, unit = self.converter.validate_frequency("100 MHz")
        self.assertTrue(valid)
        self.assertEqual(val, 100.0)
        self.assertEqual(unit, "MHz")
        
        valid, val, unit = self.converter.validate_frequency("invalid")
        self.assertFalse(valid)
    
    def test_validate_power(self):
        """测试功率验证"""
        valid, val, unit = self.converter.validate_power("10dBm")
        self.assertTrue(valid)
        self.assertEqual(val, 10.0)
        self.assertEqual(unit, "dBm")
        
        valid, val, unit = self.converter.validate_power("-100 mW")
        self.assertTrue(valid)
        self.assertEqual(val, -100.0)
        self.assertEqual(unit, "mW")
        
        valid, val, unit = self.converter.validate_power("invalid")
        self.assertFalse(valid)
    
    def test_convert_efield(self):
        """测试电场强度转换"""
        # V/m <-> mV/m
        self.assertAlmostEqual(self.converter.convert_efield(1, 'V/m', 'mV/m')[0], 1e3)
        self.assertAlmostEqual(self.converter.convert_efield(1000, 'mV/m', 'V/m')[0], 1.0)
        # V/m <-> µV/m
        self.assertAlmostEqual(self.converter.convert_efield(1, 'V/m', 'µV/m')[0], 1e6)
        self.assertAlmostEqual(self.converter.convert_efield(1e6, 'µV/m', 'V/m')[0], 1.0)
        # V/m <-> dBμV/m
        self.assertAlmostEqual(self.converter.convert_efield(1, 'V/m', 'dBμV/m')[0], 120.0)
        self.assertAlmostEqual(self.converter.convert_efield(120, 'dBμV/m', 'V/m')[0], 1.0)
        # 频率相关转换
        freq = 1e9  # 1GHz
        self.assertAlmostEqual(
            self.converter.convert_efield(0, 'dBm', 'dBμV/m', frequency=freq)[0],
            106.75,
            places=2
        )
    
    def test_efield_to_power_density(self):
        """测试电场强度到功率密度转换"""
        # 1 V/m 对应的功率密度
        s, unit = self.converter.efield_to_power_density(1, 'V/m')
        self.assertAlmostEqual(s, 1/(120*math.pi), places=6)
        self.assertEqual(unit, 'W/m²')
        
        # 10 mV/m 对应的功率密度
        s, unit = self.converter.efield_to_power_density(10, 'mV/m')
        self.assertAlmostEqual(s, (0.01)**2/(120*math.pi), places=10)
    
    def test_power_density_to_efield(self):
        """测试功率密度到电场强度转换"""
        # 1 W/m² 对应的电场强度
        e, unit = self.converter.power_density_to_efield(1, 'W/m²')
        self.assertAlmostEqual(e, math.sqrt(120*math.pi), places=6)
        self.assertEqual(unit, 'V/m')
        
        # 1 mW/m² 对应的电场强度
        e, unit = self.converter.power_density_to_efield(1, 'mW/m²')
        self.assertAlmostEqual(e, math.sqrt(120*math.pi*0.001), places=6)
    
    def test_format_efield(self):
        """测试电场强度格式化"""
        # 测试指定单位格式化
        self.assertEqual(self.converter.format_efield(1, 'V/m'), "1.000000 V/m")  # 线性单位保留6位小数
        self.assertEqual(self.converter.format_efield(120, 'dBμV/m'), "120.00 dBμV/m")  # dB单位保留2位小数
        
        # 测试自动格式化
        self.assertEqual(self.converter.format_efield(1, None), "1.000000 V/m")
        self.assertEqual(self.converter.format_efield(0.001, None), "1.000000 mV/m")
        self.assertEqual(self.converter.format_efield(1e-6, None), "1.000000 µV/m")
        
        # 测试边界值
        self.assertEqual(self.converter.format_efield(0, 'V/m'), "0.000000 V/m")
    
    def test_validate_efield(self):
        """测试电场强度验证"""
        valid, val, unit = self.converter.validate_efield("10V/m")
        self.assertTrue(valid)
        self.assertEqual(val, 10.0)
        self.assertEqual(unit, "V/m")
        
        valid, val, unit = self.converter.validate_efield("100 dBμV/m")
        self.assertTrue(valid)
        self.assertEqual(val, 100.0)
        self.assertEqual(unit, "dBμV/m")
        
        valid, val, unit = self.converter.validate_efield("invalid")
        self.assertFalse(valid)
    
    def test_dbm_to_dbuV_m(self):
        """测试dBm到dBμV/m转换"""
        freq = 18.04*1e9  # 1GHz
        # 0 dBm 在1GHz时的电场强度
        self.assertAlmostEqual(
            self.converter.dbm_to_dbuV_m(-17.17, freq),
            106.75,
            places=2
        )
        # 考虑距离
        self.assertAlmostEqual(
            self.converter.dbm_to_dbuV_m(0, freq, distance=10),
            86.75,
            places=2
        )
    
    def test_dbuV_m_to_dbm(self):
        """测试dBμV/m到dBm转换"""
        freq = 1e9  # 1GHz
        # 106.75 dBμV/m 在1GHz时的功率
        self.assertAlmostEqual(
            self.converter.dbuV_m_to_dbm(106.75, freq),
            -30.46358594144145,
            places=2
        )
        # 考虑距离
        self.assertAlmostEqual(
            self.converter.dbuV_m_to_dbm(86.75, freq, distance=1),
            -50.46358594144145,
            places=2
        )
    
    def test_v_m_to_dbuV_m(self):
        """测试V/m到dBμV/m转换"""
        self.assertAlmostEqual(self.converter.v_m_to_dbuV_m(1), 120.0)
        self.assertAlmostEqual(self.converter.v_m_to_dbuV_m(1e-6), 0.0)
        self.assertEqual(self.converter.v_m_to_dbuV_m(0), -math.inf)
    
    def test_dbuV_m_to_v_m(self):
        """测试dBμV/m到V/m转换"""
        self.assertAlmostEqual(self.converter.dbuV_m_to_v_m(120), 1.0)
        self.assertAlmostEqual(self.converter.dbuV_m_to_v_m(0), 1e-6)
        self.assertEqual(self.converter.dbuV_m_to_v_m(-math.inf), 0.0)
    
    def test_normalize_units(self):
        """测试单位规范化"""
        self.assertEqual(self.converter._normalize_freq_unit("ghz"), "GHz")
        self.assertEqual(self.converter._normalize_freq_unit("MHz"), "MHz")
        self.assertEqual(self.converter._normalize_power_unit("dbm"), "dBm")
        self.assertEqual(self.converter._normalize_power_unit("w"), "W")
        self.assertEqual(self.converter._normalize_efield_unit("v/m"), "V/m")
        self.assertEqual(self.converter._normalize_efield_unit("dbuv/m"), "dBμV/m")

if __name__ == '__main__':

    unittest.main()
