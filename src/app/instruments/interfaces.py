# app/instruments/interfaces.py
from abc import ABC, abstractmethod
import pyvisa

class VisaInstrument(ABC):
    """所有VISA设备的基类"""
    def __init__(self, visa_address: str):
        self.rm = pyvisa.ResourceManager()
        self._inst = self.rm.open_resource(visa_address)
        self._inst.timeout = 3000  # 默认3秒超时

    @abstractmethod
    def reset(self):
        """设备复位"""
        pass

    @property
    def idn(self) -> str:
        """查询设备标识"""
        return self._inst.query("*IDN?").strip()

class PowerSensor(VisaInstrument):
    @abstractmethod
    def measure_power(self, freq_hz: float = None) -> float:
        """带频率补偿的功率测量"""
        pass

class SignalSource(VisaInstrument):
    @abstractmethod
    def set_cw(self, freq_hz: float, power_dbm: float):
        """设置连续波模式"""
        pass
