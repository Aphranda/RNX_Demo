# app/instruments/factory.py
import pyvisa
from typing import Dict, Optional
from .interfaces import SignalSource, PowerSensor
from .plasg_signal_source import PlasgT8G40G
from .nrp50s import NRP50S

class InstrumentFactory:
    _rm = None  # 类变量共享ResourceManager

    @classmethod
    def _get_resource_manager(cls):
        """获取共享的ResourceManager实例"""
        if cls._rm is None:
            cls._rm = pyvisa.ResourceManager()
        return cls._rm

    @classmethod
    def _identify_instrument(cls, visa_address: str) -> Optional[Dict]:
        """识别仪器类型并返回详细信息"""
        rm = cls._get_resource_manager()
        inst = None
        try:
            inst = rm.open_resource(visa_address)
            inst.timeout = 1000  # 设置较短的超时用于识别
            idn = inst.query("*IDN?").strip().upper()
            
            # R&S NRP功率计的标准IDN格式示例：
            # "ROHDE&SCHWARZ,NRP50S,101636,02.40.22081101"
            if idn.startswith("ROHDE&SCHWARZ,NRP"):
                return {
                    'type': 'power_meter',
                    'model': idn.split(',')[1],
                    'idn': idn
                }
            elif "PLASG" in idn:
                return {
                    'type': 'signal_source',
                    'model': 'PLASG',
                    'idn': idn
                }
            return None
        except Exception as e:
            print(f"仪器识别失败: {str(e)}")
            return None
        finally:
            if inst is not None:
                inst.close()

    @classmethod
    def create_signal_source(cls, visa_address: str, instrument_name: str = None) -> Optional[SignalSource]:
        """创建信号源实例"""
        info = cls._identify_instrument(visa_address)
        if not info or info['type'] != 'signal_source':
            return None
            
        # 优先使用传入的仪表名称判断
        if instrument_name and "PLASG" in instrument_name.upper():
            return PlasgT8G40G(visa_address)
        elif info and "PLASG" in info.get('idn', ''):
            return PlasgT8G40G(visa_address)
        return None

    @classmethod
    def create_power_meter(cls, visa_address: str, instrument_name: str = None) -> Optional[PowerSensor]:
        """创建功率计实例"""
        info = cls._identify_instrument(visa_address)
        if not info or info['type'] != 'power_meter':
            return None
            
        # 优先使用传入的仪表名称判断
        if instrument_name and "NRP" in instrument_name.upper():
            return NRP50S(visa_address)
        elif info and "NRP" in info.get('model', ''):
            return NRP50S(visa_address)
        return None

    @classmethod
    def cleanup(cls):
        """清理资源管理器"""
        if cls._rm is not None:
            cls._rm.close()
            cls._rm = None
