# app/widgets/CalibrationPanel/Model.py
from dataclasses import dataclass
from typing import Dict, List, Optional, Union
from datetime import datetime

@dataclass
class InstrumentInfo:
    address: str
    model: str
    connected: bool = False

@dataclass
class FrequencyParams:
    start_ghz: Optional[float] = None
    stop_ghz: Optional[float] = None
    step_ghz: Optional[float] = None
    freq_list: Optional[List[float]] = None

@dataclass
class CalibrationData:
    frequencies: List[float]  # GHz
    measured_powers: List[float]  # dBm
    reference_power: float  # dBm
    timestamp: str
    instrument_info: Dict[str, str]
    frequency_mode: str  # "range" 或 "list"

class CalibrationModel:
    def __init__(self):
        self._data: Optional[CalibrationData] = None
        self.signal_gen = InstrumentInfo(address="", model="")
        self.power_meter = InstrumentInfo(address="", model="")
        self._freq_list: List[float] = []
        
    @property
    def calibration_data(self) -> Optional[CalibrationData]:
        return self._data
        
    @calibration_data.setter
    def calibration_data(self, data: CalibrationData):
        self._data = data
        
    @property
    def freq_list(self) -> List[float]:
        return self._freq_list
        
    @freq_list.setter
    def freq_list(self, freq_list: List[float]):
        self._freq_list = sorted(freq_list)

    def update_instrument(self, instrument_type: str, address: str, model: str, connected: bool):
        """更新仪器信息"""
        if instrument_type == 'signal_gen':
            self.signal_gen.address = address
            self.signal_gen.model = model
            self.signal_gen.connected = connected
        elif instrument_type == 'power_meter':
            self.power_meter.address = address
            self.power_meter.model = model
            self.power_meter.connected = connected
