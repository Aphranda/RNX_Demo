"""
IEEE 488.2标准SCPI指令封装
"""
import time
from app.core.exceptions.scpi import SCPIError
from app.core.exceptions.scpi import SCPICommandError
from app.core.exceptions.scpi import SCPIResponseError
from app.core.exceptions.scpi import SCPITimeoutError
from app.core.exceptions.scpi import SCPIStatusError
from app.core.tcp_client import TcpClient
from PyQt5.QtCore import QMutex, QObject, pyqtSignal

class SCPICommands(QObject):
    """IEEE 488.2标准SCPI指令封装类"""
    command_executed = pyqtSignal(str, str)  # 信号：命令执行结果 (命令, 结果/错误)
    
    def __init__(self, tcp_client: TcpClient, mutex: QMutex):
        super().__init__()
        self._tcp = tcp_client
        self._mutex = mutex
    
    def send_command(self, cmd: str, expect_response: bool = True, timeout: int = 1000):
        """增强版命令发送方法"""
        self._mutex.lock()
        try:
            # 发送命令
            success, msg = self._tcp.send(cmd + '\n')
            if not success:
                raise SCPICommandError(
                    device=self._tcp.address,
                    command=cmd,
                    message=msg
                )
            
            if not expect_response:
                return True, ""
 
            # 接收响应
            start_time = time.time()
            while (time.time() - start_time) * 1000 < timeout:
                success, resp = self._tcp.receive(timeout=100)  # 分块检查
                if success:
                    return True, resp.strip()
                elif resp != "":  # 非空响应但解析失败
                    raise SCPIResponseError(
                        device=self._tcp.address,
                        command=cmd,
                        response=resp,
                        expected_format="ASCII文本"
                    )
            
            # 超时处理
            raise SCPITimeoutError(
                device=self._tcp.address,
                command=cmd,
                timeout_ms=timeout
            )
        finally:
            self._mutex.unlock()

    # --- IEEE 488.2 标准命令 ---
    def reset(self):
        """*RST - 复位设备到默认状态"""
        try:
            success, _ = self.send_command("*RST", expect_response=False)
            self.command_executed.emit("*RST", "设备复位成功" if success else "设备复位失败")
            return success
        except SCPIError as e:
            self.command_executed.emit("*RST", str(e))
            return False
    
    def identify(self):
        """*IDN? - 查询设备标识"""
        try:
            success, resp = self.send_command("*IDN?")
            self.command_executed.emit("*IDN?", resp if success else "查询失败")
            return success, resp
        except SCPIError as e:
            self.command_executed.emit("*IDN?", str(e))
            return False, str(e)
    
    def clear_status(self):
        """*CLS - 清除状态寄存器"""
        try:
            success, _ = self.send_command("*CLS", expect_response=False)
            self.command_executed.emit("*CLS", "状态已清除" if success else "清除失败")
            return success
        except SCPIError as e:
            self.command_executed.emit("*CLS", str(e))
            return False
    
    def read_status_byte(self):
        """增强版状态字节读取"""
        try:
            success, resp = self.send_command("*STB?")
            if not success:
                raise SCPICommandError(
                    device=self._tcp.address,
                    command="*STB?",
                    message="状态查询失败"
                )
            
            try:
                status = int(resp)
                if status & 0x20:  # 检查错误位(bit5)
                    errors = self.query_errors()  # 查询错误队列
                    raise SCPIStatusError(
                        device=self._tcp.address,
                        status_byte=status,
                        error_queue=errors
                    )
                return True, status
            except ValueError:
                raise SCPIResponseError(
                    device=self._tcp.address,
                    command="*STB?",
                    response=resp,
                    expected_format="十进制整数"
                )
        except SCPIError as e:
            self.command_executed.emit("*STB?", str(e))
            return False, -1

    def query_errors(self, max_errors=10):
        """查询错误队列(SYST:ERR?)"""
        errors = []
        for _ in range(max_errors):
            success, err = self.send_command("SYST:ERR?")
            if success and err != '0,"No error"':
                errors.append(err)
            else:
                break
        return errors
    
    def wait_complete(self):
        """*WAI - 等待所有操作完成"""
        try:
            success, _ = self.send_command("*WAI", expect_response=False)
            self.command_executed.emit("*WAI", "操作已完成" if success else "等待失败")
            return success
        except SCPIError as e:
            self.command_executed.emit("*WAI", str(e))
            return False
    
    def operation_complete_query(self):
        """*OPC? - 查询操作是否完成"""
        try:
            success, resp = self.send_command("*OPC?")
            completed = (resp == "1") if success else False
            self.command_executed.emit("*OPC?", "操作已完成" if completed else "操作未完成")
            return success, completed
        except SCPIError as e:
            self.command_executed.emit("*OPC?", str(e))
            return False, False
    
    # --- 组合命令 ---
    def reset_and_wait(self):
        """复位并等待完成 (*RST + *WAI)"""
        if not self.reset():
            return False
        return self.wait_complete()
