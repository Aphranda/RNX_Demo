
import math
from typing import Optional, Tuple, Union

class SignalUnitConverter:
    """
    信号源频率和功率单位安全换算类
    
    功能:
    - 频率单位转换 (Hz, kHz, MHz, GHz)
    - 功率单位转换 (dBm, mW, W, dBW, µW, nW)
    - 电场强度单位转换 (V/m, mV/m, µV/m, dBμV/m)
    - 安全数值转换和范围检查
    - 输入验证和异常处理
    """
    
    # 频率单位转换系数
    FREQ_UNITS = {
        'Hz': 1,
        'kHz': 1e3,
        'MHz': 1e6,
        'GHz': 1e9,
    }
    
    # 功率单位转换系数
    POWER_UNITS = {
        'dBm': 'dBm',
        'mW': 'mW',
        'W': 'W',
        'uW': 'uW',
        'nW': 'nW',
        'dBW': 'dBW',
    }

    # 电场强度单位转换系数
    E_FIELD_UNITS = {
        'V/m': 'V/m',
        'mV/m': 'mV/m',
        'uV/m': 'µV/m',
        'dBuV/m': 'dBμV/m',
    }

    # 自由空间波阻抗 (Ω)
    Z0 = 120 * math.pi  # 约376.73 Ω
    
    def __init__(self):
        # 默认频率单位
        self.default_freq_unit = 'GHz'
        # 默认功率单位
        self.default_power_unit = 'dBm'
        # 默认电场强度单位
        self.default_efield_unit = 'V/m'
        
        # 功率单位颜色映射 (用于UI显示)
        self.power_unit_colors = {
            'dBm': '#0078d7',
            'mW': '#228B22',
            'W': '#d32f2f',
            'dBW': '#e67e22',
            'uW': '#8e44ad',
            'nW': '#16a085'
        }

        self.efield_unit_colors = {
            'V/m': '#9b59b6',
            'mV/m': '#3498db',
            'µV/m': '#2ecc71',
            'dBμV/m': '#e74c3c'
        }

    def safe_float_convert(self, value: Union[str, float, int], 
                         default: float = 0.0) -> float:
        """
        安全转换为浮点数
        
        参数:
            value: 输入值 (可以是字符串或数字)
            default: 转换失败时的默认值
            
        返回:
            转换后的浮点数
        """
        if isinstance(value, (float, int)):
            return float(value)
            
        if not isinstance(value, str):
            return default
            
        try:
            # 移除单位和其他非数字字符
            cleaned = ''.join(c for c in value.replace(',', '') 
                            if c in '0123456789+-.eE')
            return float(cleaned) if cleaned else default
        except (ValueError, TypeError):
            return default

    def convert_frequency(self, value: Union[str, float, int], 
                         from_unit: str, to_unit: str) -> Tuple[float, str]:
        """
        频率单位转换
        
        参数:
            value: 输入频率值
            from_unit: 原单位 (Hz, kHz, MHz, GHz)
            to_unit: 目标单位 (Hz, kHz, MHz, GHz)
            
        返回:
            (转换后的值, 规范化后的单位)
        """
        # 规范化单位
        from_unit = self._normalize_freq_unit(from_unit)
        to_unit = self._normalize_freq_unit(to_unit)
        
        # 安全转换数值
        freq_value = self.safe_float_convert(value)
        
        # 转换为基准单位 (Hz)
        base_value = freq_value * self.FREQ_UNITS.get(from_unit, 1)
        
        # 转换为目标单位
        if to_unit in self.FREQ_UNITS:
            converted = base_value / self.FREQ_UNITS[to_unit]
            # 处理极小值
            if abs(converted) < 1e-12 and converted != 0:
                converted = 0.0
            return (converted, to_unit)
        
        return (freq_value, from_unit)  # 单位无效时返回原值和单位

    def convert_power(self, value: Union[str, float, int], 
                     from_unit: str, to_unit: str) -> Tuple[float, str]:
        """
        功率单位转换
        
        参数:
            value: 输入功率值
            from_unit: 原单位 (dBm, mW, W, dBW, µW, nW)
            to_unit: 目标单位 (dBm, mW, W, dBW, µW, nW)
            
        返回:
            (转换后的值, 规范化后的单位)
        """
        # 规范化单位
        from_unit = self._normalize_power_unit(from_unit)
        to_unit = self._normalize_power_unit(to_unit)
        
        # 安全转换数值
        power_value = self.safe_float_convert(value)
        
        # 相同单位无需转换
        if from_unit == to_unit:
            return (power_value, to_unit)
        
        # 全部转换为mW作为中间单位
        if from_unit == 'dBm':
            mW_value = 10 ** (power_value / 10)
        elif from_unit == 'mW':
            mW_value = power_value
        elif from_unit == 'W':
            mW_value = power_value * 1000
        elif from_unit == 'dBW':
            # 修正：dBW 到 mW 的转换公式
            mW_value = 10 ** ((power_value + 30) / 10)  # dBW + 30 = dBm
        elif from_unit == 'µW':
            mW_value = power_value / 1000
        elif from_unit == 'nW':
            mW_value = power_value / 1e6
        else:
            return (power_value, from_unit)  # 无效单位
        
        # 从mW转换为目标单位
        if to_unit == 'dBm':
            try:
                converted = 10 * math.log10(mW_value) if mW_value > 0 else -math.inf
            except (ValueError, ZeroDivisionError):
                converted = -math.inf
        elif to_unit == 'mW':
            converted = mW_value
        elif to_unit == 'W':
            converted = mW_value / 1000
        elif to_unit == 'dBW':
            try:
                # 修正：mW 到 dBW 的转换公式
                converted = 10 * math.log10(mW_value / 1000) if mW_value > 0 else -math.inf
            except (ValueError, ZeroDivisionError):
                converted = -math.inf
        elif to_unit == 'µW':
            converted = mW_value * 1000
        elif to_unit == 'nW':
            converted = mW_value * 1e6
        else:
            return (power_value, from_unit)  # 无效单位
        
        # 处理极小值
        if abs(converted) < 1e-12 and converted != 0:
            converted = 0.0
            
        return (converted, to_unit)

    def format_frequency(self, value: Union[str, float, int], 
                        unit: Optional[str] = None) -> str:
        """
        格式化频率显示
        
        参数:
            value: 频率值
            unit: 目标单位 (None时自动选择合适单位)
            
        返回:
            格式化后的字符串 (带单位)
        """
        freq_value = self.safe_float_convert(value)
        unit = self._normalize_freq_unit(unit) if unit else None
        
        if unit:
            converted, unit = self.convert_frequency(freq_value, 'Hz', unit)
            return f"{converted:.6f} {unit}"
        
        # 自动选择最佳单位
        abs_value = abs(freq_value)
        if abs_value >= 1e9:
            converted = freq_value / 1e9
            unit = 'GHz'
        elif abs_value >= 1e6:
            converted = freq_value / 1e6
            unit = 'MHz'
        elif abs_value >= 1e3:
            converted = freq_value / 1e3
            unit = 'kHz'
        else:
            converted = freq_value
            unit = 'Hz'
        
        # 确定小数位数
        if unit == 'GHz':
            decimal_places = 6 if abs(converted) < 10 else (4 if abs(converted) < 100 else 2)
        elif unit == 'MHz':
            decimal_places = 3
        elif unit == 'kHz':
            decimal_places = 1
        else:
            decimal_places = 0
            
        return f"{converted:.{decimal_places}f} {unit}"

    def format_power(self, value: Union[str, float, int], 
                    unit: Optional[str] = None) -> str:
        """
        格式化功率显示
        
        参数:
            value: 功率值
            unit: 目标单位 (None时自动选择合适单位)
            
        返回:
            格式化后的字符串 (带单位)
        """
        power_value = self.safe_float_convert(value)
        unit = self._normalize_power_unit(unit) if unit else None
        
        if unit:
            converted, unit = self.convert_power(power_value, 'dBm', unit)
            # 特殊处理对数单位的小数位数
            if unit in ['dBm', 'dBW']:
                return f"{converted:.2f} {unit}"
            return f"{converted:.6f} {unit}"
        
        # 自动选择最佳单位
        if isinstance(power_value, str) and 'dB' in power_value:
            # 如果输入已经是dBm/dBW，保持原样
            return f"{power_value:.2f} dBm" if 'dBm' in power_value else f"{power_value:.2f} dBW"
        
        # 尝试转换为mW以确定最佳单位
        try:
            if power_value <= -1000:  # 极小值处理
                mW_value = 0
            else:
                mW_value = 10 ** (power_value / 10) if power_value > -1000 else 0
        except:
            mW_value = 0
        
        if mW_value >= 1000:
            converted = mW_value / 1000
            unit = 'W'
        elif mW_value >= 1:
            converted = mW_value
            unit = 'mW'
        elif mW_value >= 1e-3:
            converted = mW_value * 1000
            unit = 'µW'
        else:
            converted = mW_value * 1e6
            unit = 'nW'
            
        # 根据数值大小调整小数位数
        if converted > 1000:
            return f"{converted:.2f} {unit}"
        elif converted > 100:
            return f"{converted:.3f} {unit}"
        elif converted > 10:
            return f"{converted:.4f} {unit}"
        else:
            return f"{converted:.6f} {unit}"

    def validate_frequency(self, freq_str: str) -> Tuple[bool, float, str]:
        """
        验证并解析频率字符串
        
        参数:
            freq_str: 频率字符串 (如 "10GHz", "100 MHz")
            
        返回:
            (是否有效, 数值, 单位)
        """
        if not isinstance(freq_str, str):
            return (False, 0.0, 'Hz')
            
        # 提取数值部分
        num_part = []
        unit_part = []
        has_digit = False
        has_decimal = False
        
        for c in freq_str.strip():
            if c in '0123456789':
                num_part.append(c)
                has_digit = True
            elif c in '+-.':
                if c == '.':
                    if has_decimal:
                        break  # 多个小数点无效
                    has_decimal = True
                num_part.append(c)
            else:
                unit_part.append(c)
                
        if not has_digit:
            return (False, 0.0, 'Hz')
            
        try:
            value = float(''.join(num_part))
            unit = ''.join(unit_part).strip()
            unit = self._normalize_freq_unit(unit) if unit else self.default_freq_unit
            
            # 放宽值范围检查
            if not (0 <= value < 1e20):
                return (False, value, unit)
                
            return (True, value, unit)
        except (ValueError, TypeError):
            return (False, 0.0, 'Hz')

    def validate_power(self, power_str: str) -> Tuple[bool, float, str]:
        """
        验证并解析功率字符串
        
        参数:
            power_str: 功率字符串 (如 "10dBm", "-100 mW")
            
        返回:
            (是否有效, 数值, 单位)
        """
        if not isinstance(power_str, str):
            return (False, 0.0, 'dBm')
            
        # 提取数值部分
        num_part = []
        unit_part = []
        has_digit = False
        has_decimal = False
        has_dB = False
        
        for c in power_str.strip():
            if c in '0123456789':
                num_part.append(c)
                has_digit = True
            elif c in '+-.':
                if c == '.':
                    if has_decimal:
                        break  # 多个小数点无效
                    has_decimal = True
                num_part.append(c)
            elif c.lower() == 'd':
                has_dB = True
                unit_part.append(c)
            else:
                unit_part.append(c)
                
        if not has_digit:
            return (False, 0.0, 'dBm')
            
        try:
            value = float(''.join(num_part))
            unit = ''.join(unit_part).strip()
            
            # 特殊处理dB/dBm/dBW
            if has_dB:
                if 'm' in unit.lower():
                    unit = 'dBm'
                elif 'w' in unit.lower():
                    unit = 'dBW'
                else:
                    unit = 'dBm'  # 默认dBm
            else:
                unit = self._normalize_power_unit(unit) if unit else self.default_power_unit
            
            # 放宽值范围检查
            if unit in ('dBm', 'dBW'):
                valid = -300 <= value <= 300  # 扩展范围
            else:
                valid = 0 <= value <= 1e12   # 扩展范围
                
            return (valid, value, unit)
        except (ValueError, TypeError):
            return (False, 0.0, 'dBm')

    def _normalize_freq_unit(self, unit: str) -> str:
        """规范化频率单位"""
        if not unit:
            return self.default_freq_unit
            
        unit = unit.strip().lower()
        if unit.startswith('ghz'):
            return 'GHz'
        elif unit.startswith('mhz'):
            return 'MHz'
        elif unit.startswith('khz'):
            return 'kHz'
        elif unit.startswith('hz'):
            return 'Hz'
        else:
            return self.default_freq_unit

    def _normalize_power_unit(self, unit: str) -> str:
        """规范化功率单位"""
        if not unit:
            return self.default_power_unit
            
        unit = unit.strip().lower()
        if unit.startswith('dbm'):
            return 'dBm'
        elif unit.startswith('dbw'):
            return 'dBW'
        elif unit.startswith('mw') or unit == 'm':
            return 'mW'
        elif unit.startswith('uw') or unit == 'u' or unit == 'μ':
            return 'µW'
        elif unit.startswith('nw') or unit == 'n':
            return 'nW'
        elif unit.startswith('w') or unit == 'v':
            return 'W'
        else:
            return self.default_power_unit

    def get_power_unit_color(self, unit: str) -> str:
        """获取功率单位的显示颜色"""
        norm_unit = self._normalize_power_unit(unit)
        return self.power_unit_colors.get(norm_unit, '#0078d7')
    
    def convert_efield(self, value: Union[str, float, int], 
                     from_unit: str, to_unit: str,
                     distance: float = 1.0,
                     frequency: Optional[float] = None) -> Tuple[float, str]:
        """
        电场强度单位转换（支持距离和频率参数）
        
        参数:
            value: 输入场强值
            from_unit: 原单位 (V/m, mV/m, µV/m, dBμV/m, dBm)
            to_unit: 目标单位 (V/m, mV/m, µV/m, dBμV/m, dBm)
            distance: 测量距离 (米), 默认为1米
            frequency: 频率 (Hz), 用于精确的dBm-dBμV/m转换
            
        返回:
            (转换后的值, 规范化后的单位)
        """
        # 规范化单位
        from_unit = self._normalize_efield_unit(from_unit)
        to_unit = self._normalize_efield_unit(to_unit)
        
        # 安全转换数值
        efield_value = self.safe_float_convert(value)
        
        # 相同单位无需转换
        if from_unit == to_unit:
            return (efield_value, to_unit)
        
        # 如果有频率参数，使用精确转换公式
        if frequency is not None and (from_unit == 'dBm' and to_unit == 'dBμV/m'):
            converted = self.dbm_to_dbuV_m(efield_value, frequency, distance)
            return (converted, to_unit)
            
        if frequency is not None and (from_unit == 'dBμV/m' and to_unit == 'dBm'):
            converted = self.dbuV_m_to_dbm(efield_value, frequency, distance)
            return (converted, to_unit)
        
        # 其余情况使用原有转换逻辑
        return self._convert_efield_inner(efield_value, from_unit, to_unit)

    def _convert_efield_inner(self, value: float,
                            from_unit: str, to_unit: str) -> Tuple[float, str]:
        """
        内部方法：处理纯电场强度单位间的转换
        """
        # 全部转换为V/m作为中间单位
        if from_unit == 'V/m':
            v_m_value = value
        elif from_unit == 'mV/m':
            v_m_value = value * 1e-3
        elif from_unit == 'µV/m':
            v_m_value = value * 1e-6
        elif from_unit == 'dBμV/m':
            v_m_value = self.dbuV_m_to_v_m(value)
        else:
            return (value, from_unit)
        
        # 从V/m转换为目标单位
        if to_unit == 'V/m':
            converted = v_m_value
        elif to_unit == 'mV/m':
            converted = v_m_value * 1e3
        elif to_unit == 'µV/m':
            converted = v_m_value * 1e6
        elif to_unit == 'dBμV/m':
            converted = self.v_m_to_dbuV_m(v_m_value)
        else:
            return (value, from_unit)
        
        return (converted, to_unit)


    def efield_to_power_density(self, efield: Union[str, float, int], 
                               efield_unit: str = 'V/m') -> Tuple[float, str]:
        """
        电场强度转换为功率密度 (W/m²)
        
        参数:
            efield: 电场强度值
            efield_unit: 电场强度单位
            
        返回:
            (功率密度值, 'W/m²')
        """
        # 转换为V/m
        e_v_m, _ = self.convert_efield(efield, efield_unit, 'V/m')
        
        # 计算功率密度 S = E² / Z0
        power_density = (e_v_m ** 2) / self.Z0
        
        return (power_density, 'W/m²')
    
    def power_density_to_efield(self, power_density: Union[str, float, int], 
                              power_unit: str = 'W/m²') -> Tuple[float, str]:
        """
        功率密度转换为电场强度 (V/m)
        
        参数:
            power_density: 功率密度值
            power_unit: 功率密度单位 (支持 W/m², mW/m², µW/m²)
            
        返回:
            (电场强度值, 'V/m')
        """
        # 转换为W/m²
        s_w_m2 = self.safe_float_convert(power_density)
        
        # 处理不同单位
        if power_unit == 'mW/m²':
            s_w_m2 *= 1e-3
        elif power_unit == 'µW/m²':
            s_w_m2 *= 1e-6
        
        # 计算电场强度 E = sqrt(S * Z0)
        if s_w_m2 > 0:
            efield = math.sqrt(s_w_m2 * self.Z0)
        else:
            efield = 0.0
        
        return (efield, 'V/m')
    
    def format_efield(self, value: Union[str, float, int], 
                     unit: Optional[str] = None) -> str:
        """
        格式化电场强度显示
        
        参数:
            value: 场强值
            unit: 目标单位 (None时自动选择合适单位)
            
        返回:
            格式化后的字符串 (带单位)
        """
        efield_value = self.safe_float_convert(value)
        unit = self._normalize_efield_unit(unit) if unit else None
        
        if unit:
            converted, unit = self.convert_efield(efield_value, 'V/m', unit)
            # 特殊处理对数单位的小数位数
            if unit == 'dBμV/m':
                return f"{converted:.2f} {unit}"
            return f"{converted:.6f} {unit}"
        
        # 自动选择最佳单位
        abs_value = abs(efield_value)
        if abs_value >= 1:
            converted = efield_value
            unit = 'V/m'
        elif abs_value >= 1e-3:
            converted = efield_value * 1e3
            unit = 'mV/m'
        else:
            converted = efield_value * 1e6
            unit = 'µV/m'
            
        # 根据数值大小调整小数位数
        if converted > 1000:
            return f"{converted:.2f} {unit}"
        elif converted > 100:
            return f"{converted:.3f} {unit}"
        elif converted > 10:
            return f"{converted:.4f} {unit}"
        else:
            return f"{converted:.6f} {unit}"
    
    def validate_efield(self, efield_str: str) -> Tuple[bool, float, str]:
        """
        验证并解析电场强度字符串
        
        参数:
            efield_str: 场强字符串 (如 "10V/m", "100 dBμV/m")
            
        返回:
            (是否有效, 数值, 单位)
        """
        if not isinstance(efield_str, str):
            return (False, 0.0, 'V/m')
            
        # 提取数值部分
        num_part = []
        unit_part = []
        has_digit = False
        has_decimal = False
        has_dB = False
        
        for c in efield_str.strip():
            if c in '0123456789':
                num_part.append(c)
                has_digit = True
            elif c in '+-.':
                if c == '.':
                    if has_decimal:
                        break  # 多个小数点无效
                    has_decimal = True
                num_part.append(c)
            elif c.lower() == 'd':
                has_dB = True
                unit_part.append(c)
            else:
                unit_part.append(c)
                
        if not has_digit:
            return (False, 0.0, 'V/m')
            
        try:
            value = float(''.join(num_part))
            unit = ''.join(unit_part).strip()
            
            # 特殊处理dBμV/m
            if has_dB:
                if 'v/m' in unit.lower() or 'μv/m' in unit.lower():
                    unit = 'dBμV/m'
                else:
                    unit = 'dBμV/m'  # 默认
            else:
                unit = self._normalize_efield_unit(unit) if unit else self.default_efield_unit
            
            # 放宽值范围检查
            if unit == 'V/m':
                valid = 0 <= value <= 1e6
            elif unit == 'mV/m':
                valid = 0 <= value <= 1e9
            elif unit == 'µV/m':
                valid = 0 <= value <= 1e12
            elif unit == 'dBμV/m':
                valid = 0 <= value <= 240  # 约1MV/m
            else:
                valid = False
                
            return (valid, value, unit)
        except (ValueError, TypeError):
            return (False, 0.0, 'V/m')
        
    def _normalize_efield_unit(self, unit: str) -> str:
        """规范化电场强度单位"""
        if not unit:
            return self.default_efield_unit
            
        unit = unit.strip().lower()
        if unit.startswith('v/m'):
            return 'V/m'
        elif unit.startswith('mv/m'):
            return 'mV/m'
        elif unit.startswith('µv/m') or unit.startswith('uv/m'):
            return 'µV/m'
        elif unit.startswith('dbμv/m') or unit.startswith('dbuv/m') or unit.startswith('dbu'):
            return 'dBμV/m'
        else:
            return self.default_efield_unit
        
    def get_efield_unit_color(self, unit: str) -> str:
        """获取电场强度单位的显示颜色"""
        norm_unit = self._normalize_efield_unit(unit)
        return self.efield_unit_colors.get(norm_unit, '#9b59b6')

    def dbuV_m_to_dbm(self, dbuV_m: float, frequency: float, distance: float = 1.0, antenna_gain: float = 1.0) -> float:
        """
        将dBμV/m转换为dBm (公式逆运算)
        
        参数:
            dbuV_m: 电场强度 (dBμV/m)
            frequency: 频率 (Hz)
            distance: 距离 (米), 默认为1米
            antenna_gain: 天线增益 (无量纲), 默认为1
        
        返回:
            发射功率 (dBm)
        """
        # 计算波长 (米)
        wavelength = 299792458 / frequency  # 光速 / 频率
        
        # 应用逆公式
        dbm = dbuV_m + 20 * math.log10(wavelength) - 126.75
        
        # 考虑距离和天线增益的影响
        if distance != 1.0:
            dbm += 20 * math.log10(distance)
        if antenna_gain != 1.0:
            dbm -= 10 * math.log10(antenna_gain)
            
        return dbm
    
    def dbm_to_dbuV_m(self, dbm: float, frequency: float, distance: float = 1.0, antenna_gain: float = 1.0) -> float:
        """
        将dBm转换为dBμV/m (根据公式: EdBuV/m = Pr,dBm - 20*log10(波长) + 126.75)
        
        参数:
            dbm: 发射功率 (dBm)
            frequency: 频率 (Hz)
            distance: 距离 (米), 默认为1米
            antenna_gain: 天线增益 (无量纲), 默认为1 (各向同性天线)
        
        返回:
            电场强度 (dBμV/m)
        """
        # 计算波长 (米)
        wavelength = 299792458 / frequency  # 光速 / 频率
        
        # 应用公式
        dbuV_m = dbm - 20 * math.log10(wavelength) + 126.75
        
        # 考虑距离和天线增益的影响
        if distance != 1.0:
            dbuV_m -= 20 * math.log10(distance)
        if antenna_gain != 1.0:
            dbuV_m += 10 * math.log10(antenna_gain)
            
        return dbuV_m
    
    def v_m_to_dbuV_m(self, v_m: float) -> float:
        """
        将 V/m 转换为 dBμV/m
        
        参数:
            v_m: 电场强度 (V/m)
        
        返回:
            电场强度 (dBμV/m)
        
        公式:
            E,dBuV/m = 20*log10(E,V/m × 10^6)
        """
        try:
            return 20 * math.log10(v_m * 1e6) if v_m > 0 else -math.inf
        except (ValueError, ZeroDivisionError):
            return -math.inf
    
    def dbuV_m_to_v_m(self, dbuV_m: float) -> float:
        """
        将 dBμV/m 转换为 V/m
        
        参数:
            dbuV_m: 电场强度 (dBμV/m)
        
        返回:
            电场强度 (V/m)
        
        公式:
            E,V/m = 10^(E,dBuV/m / 20) / 10^6
        """
        try:
            return 10 ** (dbuV_m / 20) * 1e-6 if dbuV_m > -math.inf else 0.0
        except (ValueError, ZeroDivisionError):
            return 0.0
