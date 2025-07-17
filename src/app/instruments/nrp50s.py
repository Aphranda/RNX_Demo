# app/instruments/nrp50s.py
from .interfaces import PowerSensor

class NRP50S(PowerSensor):
    def __init__(self, visa_address: str):
        super().__init__(visa_address)
        self._inst.write("SENS:FUNC 'POW'")  # 初始化功率测量模式

    def measure_power(self, freq_hz: float = None) -> float:
        if freq_hz:
            self._inst.write(f"SENS:FREQ {freq_hz}Hz")
        return float(self._inst.query("READ?"))

    def reset(self):
        self._inst.write("*RST;*CLS")
