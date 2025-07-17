# app/core/exceptions/instrument.py
from .base import DeviceCommunicationError

class VisaCommandError(DeviceCommunicationError):
    """VISA指令执行异常"""
    def __init__(self, visa_address: str, command: str, response: str|None):
        msg = f"指令 '{command}' 执行失败"
        if response:
            msg += f"，设备返回: {response}"
        super().__init__(visa_address, msg)

class PowerSensorRangeError(DeviceCommunicationError):
    """功率超量程异常"""
    def __init__(self, device: str, actual_power: float, max_power: float):
        super().__init__(
            device,
            f"输入功率 {actual_power}dBm 超过量程上限 {max_power}dBm"
        )
