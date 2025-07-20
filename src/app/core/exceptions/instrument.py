# app/core/exceptions/instrument.py
from .base import DeviceCommunicationError

class InstrumentCommandError(DeviceCommunicationError):
    """仪器指令执行异常基类"""
    def __init__(self, device: str, message: str, command: str = None):
        full_msg = f"设备 {device} 错误: {message}"
        if command:
            full_msg += f"\n执行指令: {command}"
        super().__init__(device, full_msg)
        self.command = command

class VisaCommandError(InstrumentCommandError):
    """VISA指令执行异常"""
    def __init__(self, visa_address: str, command: str, response: str = None):
        msg = "VISA指令执行失败"
        if response:
            msg += f"，设备返回: {response}"
        super().__init__(visa_address, msg, command)

class PowerSensorRangeError(InstrumentCommandError):
    """功率超量程异常"""
    def __init__(self, device: str, actual_power: float, max_power: float):
        super().__init__(
            device,
            f"输入功率 {actual_power}dBm 超过量程上限 {max_power}dBm"
        )

class SignalSourceError(InstrumentCommandError):
    """信号源专用异常"""
    def __init__(self, device: str, param: str, value: float, valid_range: tuple):
        super().__init__(
            device,
            f"参数 {param} 值 {value} 超出有效范围 ({valid_range[0]}-{valid_range[1]})"
        )
