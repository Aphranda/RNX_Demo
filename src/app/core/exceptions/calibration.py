# app/core/exceptions/calibration.py
from .base import RNXError

class CalibrationError(RNXError):
    """校准流程异常基类"""
    def __init__(self, step: str, reason: str):
        super().__init__(f"校准步骤 '{step}' 失败: {reason}", 3000)

class FrequencyResponseError(CalibrationError):
    """频响校准异常"""
    def __init__(self, freq_hz: float, deviation: float):
        super().__init__(
            f"频率点 {freq_hz/1e9}GHz",
            f"响应偏差 {deviation}dB 超过阈值"
        )
