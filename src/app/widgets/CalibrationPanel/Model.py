# app/widgets/CalibrationPanel/Model.py
from dataclasses import dataclass
from typing import Dict, List, Optional, Union
from datetime import datetime
from app.threads.CalibrationThread import CalibrationPoint
from app.instruments.interfaces import SignalSource
from app.instruments.interfaces import PowerSensor
@dataclass
class InstrumentInfo:
    address: str
    model: str
    name: str = ""
    connected: bool = False
    instance: Optional[Union[SignalSource, PowerSensor]] = None  # 新增字段保存实际实例

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
    antenna_gain: Optional[Dict[float, float]] = None  # 新增天线增益数据

class CalibrationModel:
    def __init__(self):
        self._data: Optional[CalibrationData] = None
        self.signal_gen: InstrumentInfo = InstrumentInfo(address="", model="", name="")
        self.power_meter: InstrumentInfo = InstrumentInfo(address="", model="", name="")
        self._freq_list: List[float] = []
        self._calibration_points: List[CalibrationPoint] = []
        self.antenna_gain_data: Optional[List[Dict[str, float]]] = None  # 新增天线增益数据
        
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

    def add_calibration_point(self, point: CalibrationPoint):
        """添加校准点到模型"""
        self._calibration_points.append(point)
        # 更新校准数据
        if not self._data:
            self._data = CalibrationData(
                frequencies=[point.freq_hz / 1e9],  # 转换为GHz
                measured_powers=[point.measured_power],
                reference_power=point.expected_power,
                timestamp=point.timestamp,
                instrument_info={
                    'signal_gen': (self.signal_gen.model, self.signal_gen.address),
                    'power_meter': (self.power_meter.model, self.power_meter.address)
                },
                frequency_mode="range" if not self._freq_list else "list"
            )
        else:
            self._data.frequencies.append(point.freq_hz / 1e9)
            self._data.measured_powers.append(point.measured_power)

    def update_instrument(self, instrument_type: str, address: str, model: str, name: str, connected: bool):
        """更新仪器信息"""
        if instrument_type == 'signal_gen':
            self.signal_gen = InstrumentInfo(
                address=address,
                model=model,
                name=name,
                connected=connected
            )
        elif instrument_type == 'power_meter':
            self.power_meter = InstrumentInfo(
                address=address,
                model=model,
                name=name,
                connected=connected
            )
