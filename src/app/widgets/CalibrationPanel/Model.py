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
    instance: Optional[Union[SignalSource, PowerSensor]] = None
    serial_number: str = ""

@dataclass
class FrequencyParams:
    start_ghz: Optional[float] = None
    stop_ghz: Optional[float] = None
    step_ghz: Optional[float] = None
    freq_list: Optional[List[float]] = None

@dataclass
class CalibrationData:
    frequencies: List[float]  # GHz
    measured_theta: List[float]  # dBm
    measured_phi: List[float]  # dBm
    horn_gains: List[float]  # dB
    theta_corrected: List[float]  # dB
    phi_corrected: List[float]  # dB
    theta_corrected_vm: List[float]  # dBμV/m
    phi_corrected_vm: List[float]  # dBμV/m
    reference_power: float  # dBm
    timestamp: str
    instrument_info: Dict[str, str]
    frequency_mode: str  # "range" 或 "list"
    antenna_gain: Optional[Dict[float, float]] = None

class CalibrationModel:
    def __init__(self):
        self._data: Optional[CalibrationData] = None
        self.signal_gen: InstrumentInfo = InstrumentInfo(address="", model="", name="")
        self.power_meter: InstrumentInfo = InstrumentInfo(address="", model="", name="")
        self._freq_list: List[float] = []
        self._calibration_points: List[CalibrationPoint] = []
        self.antenna_gain_data: Optional[List[Dict[str, float]]] = None
        self.antenna_model: str = "DEFAULT_ANT"  # 添加天线型号属性
        self.antenna_sn: str = "SN00000"  # 添加天线序列号属性
        
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
        """添加校准点到模型，包含所有计算字段"""
        self._calibration_points.append(point)
        
        # 如果是第一个点，初始化数据结构
        if not self._data:
            self._data = CalibrationData(
                frequencies=[point.freq_hz / 1e9],
                measured_theta=[point.measured_theta],
                measured_phi=[point.measured_phi],
                horn_gains=[point.horn_gain],
                theta_corrected=[point.measured_theta - point.ref_power],
                phi_corrected=[point.measured_phi - point.ref_power],
                theta_corrected_vm=[point.theta_corrected_vm],
                phi_corrected_vm=[point.phi_corrected_vm],
                reference_power=point.ref_power,
                timestamp=point.timestamp,
                instrument_info={
                    'signal_gen': (self.signal_gen.model, self.signal_gen.serial_number),
                    'power_meter': (self.power_meter.model, self.power_meter.serial_number),
                    'antenna': (self.antenna_model, self.antenna_sn)
                },
                frequency_mode="range" if not self._freq_list else "list",
                antenna_gain=self.antenna_gain_data
            )
        else:
            # 追加数据点
            self._data.frequencies.append(point.freq_hz / 1e9)
            self._data.measured_theta.append(point.measured_theta)
            self._data.measured_phi.append(point.measured_phi)
            self._data.horn_gains.append(point.horn_gain)
            self._data.theta_corrected.append(point.measured_theta - point.ref_power)
            self._data.phi_corrected.append(point.measured_phi - point.ref_power)
            self._data.theta_corrected_vm.append(point.theta_corrected_vm)
            self._data.phi_corrected_vm.append(point.phi_corrected_vm)

    def update_instrument(self, instrument_type: str, address: str, model: str, name: str, connected: bool):
        """更新仪器信息"""
        if instrument_type == 'signal_gen':
            self.signal_gen = InstrumentInfo(
                address=address,
                model=model,
                name=name,
                connected=connected,
                serial_number=self._extract_serial_number(model)
            )
        elif instrument_type == 'power_meter':
            self.power_meter = InstrumentInfo(
                address=address,
                model=model,
                name=name,
                connected=connected,
                serial_number=self._extract_serial_number(model)
            )

    def _extract_serial_number(self, idn_string: str) -> str:
        """从仪器识别字符串中提取序列号"""
        parts = idn_string.split(',')
        return parts[-1].strip() if len(parts) > 2 else "UNKNOWN"
