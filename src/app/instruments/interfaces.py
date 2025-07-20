# app/instruments/interfaces.py
from abc import ABC, abstractmethod
from typing import Optional
import pyvisa

class VisaInstrument(ABC):
    """所有VISA设备的基类"""
    def __init__(self, visa_address: str):
        self.rm = pyvisa.ResourceManager()
        self._inst = self.rm.open_resource(visa_address)
        self._inst.timeout = 3000  # 默认3秒超时

    @property
    @abstractmethod
    def model(self) -> str:
        """设备型号"""
        pass
        
    @property
    @abstractmethod
    def serial_number(self) -> str:
        """设备序列号"""
        pass

    @abstractmethod
    def reset(self):
        """设备复位"""
        pass

    @property
    def idn(self) -> str:
        """查询设备标识"""
        return self._inst.query("*IDN?").strip()

    def close(self):
        """关闭设备连接"""
        if hasattr(self, '_inst') and self._inst:
            self._inst.close()

class PowerSensor(VisaInstrument):
    @abstractmethod
    def measure_power(self, freq_hz: Optional[float] = None) -> float:
        """带频率补偿的功率测量"""
        pass

    @abstractmethod
    def set_frequency_correction(self, offset_db: float):
        """设置频率校正值"""
        pass

    @abstractmethod
    def set_averaging(self, count: int):
        """设置平均次数"""
        pass

class SignalSource(VisaInstrument):
    @abstractmethod
    def set_cw(self, freq_hz: float, power_dbm: float):
        """设置连续波模式"""
        pass

    @abstractmethod
    def set_frequency(self, freq_hz: float):
        """设置频率"""
        pass

    @abstractmethod
    def set_power(self, power_dbm: float):
        """设置功率"""
        pass

    @abstractmethod
    def set_output(self, state: bool):
        """设置输出状态"""
        pass
