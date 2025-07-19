# app/instruments/factory.py
import pyvisa
from typing import Dict, Type

# ... 其他导入 ...
from .interfaces import SignalSource, PowerSensor
from .plasg_signal_source import PlasgT8G40G
from .nrp50s import NRP50S

class InstrumentFactory:
    @classmethod
    def create_signal_source(cls, visa_address: str) -> SignalSource:
        """创建信号源实例"""
        try:
            # 尝试识别信号源类型
            rm = pyvisa.ResourceManager()
            inst = rm.open_resource(visa_address)
            idn = inst.query("*IDN?").strip().upper()
            
            if "PLASG" in idn:
                return PlasgT8G40G(visa_address)
            # 可以添加其他信号源类型的识别
            else:
                # 默认返回通用信号源
                return PlasgT8G40G(visa_address)
                
        except Exception as e:
            print(f"创建信号源失败: {str(e)}")
            return None
    
    @classmethod
    def create_power_meter(cls, visa_address: str) -> PowerSensor:
        """创建功率计实例"""
        try:
            # 尝试识别功率计类型
            rm = pyvisa.ResourceManager()
            inst = rm.open_resource(visa_address)
            idn = inst.query("*IDN?").strip().upper()
            
            if "NRP" in idn:
                return NRP50S(visa_address)
            # 可以添加其他功率计类型的识别
            else:
                # 默认返回通用功率计
                return NRP50S(visa_address)
                
        except Exception as e:
            print(f"创建功率计失败: {str(e)}")
            return None
