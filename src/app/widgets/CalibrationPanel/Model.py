# app/widgets/CalibrationPanel/Model.py
from dataclasses import dataclass
from typing import Dict, List, Optional
from app.utils.SignalUnitConverter import SignalUnitConverter

@dataclass
class CalibrationData:
    frequencies: List[float]  # in GHz
    measured_powers: List[float]  # in dBm
    reference_power: float  # in dBm
    timestamp: str
    instrument_info: Dict[str, str]

class CalibrationModel:
    def __init__(self):
        self._calibration_data: Optional[CalibrationData] = None
        self._instrument_status = {
            'signal_gen': {'connected': False, 'info': ''},
            'power_meter': {'connected': False, 'info': ''}
        }
        self._unit_converter = SignalUnitConverter()
        
    @property
    def calibration_data(self) -> Optional[CalibrationData]:
        return self._calibration_data
        
    @calibration_data.setter
    def calibration_data(self, data: CalibrationData):
        self._calibration_data = data
        
    @property
    def instrument_status(self) -> dict:
        return self._instrument_status
        
    def update_instrument_status(self, instrument_type: str, connected: bool, info: str = ''):
        """Update instrument connection status"""
        if instrument_type in self._instrument_status:
            self._instrument_status[instrument_type]['connected'] = connected
            self._instrument_status[instrument_type]['info'] = info
            
    @property
    def unit_converter(self):
        return self._unit_converter
