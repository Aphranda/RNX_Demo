# app/core/exceptions/base.py
class RNXError(Exception):
    """所有项目异常的基类"""
    def __init__(self, message: str, code: int = 1000):
        self.code = code  # 错误码体系
        super().__init__(f"[RNX-{code}] {message}")

class DeviceCommunicationError(RNXError):
    """设备通信异常基类"""
    def __init__(self, device: str, message: str):
        super().__init__(f"设备 {device} 通信异常: {message}", 2000)
