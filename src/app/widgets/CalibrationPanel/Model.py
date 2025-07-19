# app/widgets/CalibrationPanel/Model.py
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime

@dataclass
class InstrumentInfo:
    address: str
    model: str
    connected: bool = False

@dataclass
class CalibrationData:
    frequencies: List[float]  # GHz
    measured_powers: List[float]  # dBm
    reference_power: float  # dBm
    timestamp: str
    instrument_info: Dict[str, str]

class CalibrationModel:
    def __init__(self):
        self._data: Optional[CalibrationData] = None
        self.signal_gen = InstrumentInfo(address="", model="")
        self.power_meter = InstrumentInfo(address="", model="")
        
    @property
    def calibration_data(self) -> Optional[CalibrationData]:
        return self._data
        
    @calibration_data.setter
    def calibration_data(self, data: CalibrationData):
        self._data = data
        
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
