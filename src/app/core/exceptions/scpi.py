# app/core/exceptions/scpi.py
from .base import DeviceCommunicationError

class SCPIError(DeviceCommunicationError):
    """SCPI命令基础异常类"""
    def __init__(self, device: str, command: str, message: str, response: str = None):
        """
        :param device: 设备名称/地址
        :param command: 执行的SCPI命令
        :param message: 错误描述
        :param response: 设备返回的错误响应(可选)
        """
        full_msg = f"SCPI命令错误: {message}"
        if response:
            full_msg += f"\n设备返回: {response}"
        super().__init__(device, full_msg)
        self.command = command
        self.response = response
        self.code = 2100  # SCPI错误专用代码范围2100-2199

class SCPICommandError(SCPIError):
    """SCPI命令执行错误"""
    def __init__(self, device: str, command: str, response: str = None):
        super().__init__(
            device,
            command,
            "命令执行失败",
            response
        )
        self.code = 2101

class SCPITimeoutError(SCPIError):
    """SCPI命令超时错误"""
    def __init__(self, device: str, command: str, timeout_ms: int):
        super().__init__(
            device,
            command,
            f"响应超时({timeout_ms}ms)"
        )
        self.timeout = timeout_ms
        self.code = 2102

class SCPIResponseError(SCPIError):
    """SCPI响应解析错误"""
    def __init__(self, device: str, command: str, response: str, expected_format: str):
        super().__init__(
            device,
            command,
            f"响应格式无效，预期格式: {expected_format}",
            response
        )
        self.expected_format = expected_format
        self.code = 2103

class SCPIStatusError(SCPIError):
    """SCPI状态寄存器错误"""
    def __init__(self, device: str, status_byte: int, error_queue: list):
        error_codes = ", ".join(str(e) for e in error_queue)
        super().__init__(
            device,
            "*STB?",
            f"设备错误状态: 0x{status_byte:02X} (错误队列: {error_codes})"
        )
        self.status_byte = status_byte
        self.error_queue = error_queue
        self.code = 2104
