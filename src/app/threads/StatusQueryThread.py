from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QStatusBar, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout, 
    QSizePolicy, QMessageBox, QCheckBox, QToolBar, QAction, QFileDialog
)
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QFontMetrics, QTextCursor, QTextCharFormat, QIcon
from PyQt5.QtCore import Qt, QPointF, QThread, pyqtSignal, QMutex, QSize
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtCore import QRegExp
import socket, select
import time




class StatusQueryThread(QThread):
    status_signal = pyqtSignal(dict)

    def __init__(self, ip, port, mutex, parent=None):
        super().__init__(parent)
        self.ip = ip
        self.port = int(port)
        self.mutex = mutex
        self._running = True
        self.current_operation = None
        self.operating_axis = None
        self.socket = None  # 添加socket实例变量

    def run(self):
        axes = ["X", "KU", "K", "KA", "Z"]
        axis_idx = 0
        while self._running:
            status = {"motion": {}, "src": {}}
            self.mutex.lock()
            try:
                # 每次只查一个轴
                axis = axes[axis_idx]
                if axis == "Z":
                    reach = "NO Pa"
                    home = self.query_status("READ:MOTion:HOME? ALL")
                    speed = self.query_status("READ:MOTion:SPEED? Z")
                else:
                    reach = self.query_status(f"READ:MOTion:FEED? {axis}")
                    home = self.query_status(f"READ:MOTion:HOME? {axis}")
                    speed = self.query_status(f"READ:MOTion:SPEED? {axis}")

                status["motion"][axis] = {
                    "reach": reach,
                    "home": home,
                    "speed": speed
                }
                # 每次查一个信号源参数
                if axis_idx == 0:
                    freq = self.query_status("READ:SOURce:FREQuency?")
                    status["src"]["freq"] = freq
                elif axis_idx == 1:
                    power = self.query_status("READ:SOURce:POWer?")
                    status["src"]["power"] = power
                elif axis_idx == 2:
                    rf = self.query_status("READ:SOURce:OUTPut?")
                    status["src"]["rf"] = rf
            except Exception as e:
                self.log(f"查询状态出错: {str(e)}", "ERROR")
            finally:
                self.mutex.unlock()
                
            self.status_signal.emit(status)
            axis_idx = (axis_idx + 1) % len(axes)
            # 细粒度sleep，保证stop及时
            for _ in range(5):
                if not self._running:
                    break
                time.sleep(0.05)

    def query_status(self, cmd, max_retries=3, base_timeout=1.0):
        """带超时重发机制的查询方法"""
        retry_count = 0
        last_exception = None
        
        while retry_count < max_retries:
            sock = None
            try:
                # 动态计算当前超时时间 (指数退避算法)
                current_timeout = min(base_timeout * (2 ** retry_count), 5.0)
                
                # 建立连接并设置超时
                sock = socket.create_connection((self.ip, self.port), timeout=current_timeout)
                sock.settimeout(current_timeout)
                self.socket = sock  # 保存socket引用
                
                # 发送命令
                sock.sendall((cmd + '\n').encode('utf-8'))
                
                # 接收数据（支持分片接收）
                data = b''
                start_time = time.time()
                while self._running:  # 添加运行状态检查
                    try:
                        # 检查是否超时
                        if time.time() - start_time > current_timeout:
                            raise socket.timeout(f"接收超时 ({current_timeout:.1f}s)")
                        
                        # 尝试读取数据
                        chunk = sock.recv(4096)
                        if not chunk:  # 连接关闭
                            break
                        
                        data += chunk
                        
                        # 检查是否收到完整响应（以换行符判断）
                        if b'\r\n' in data or b'\r' in data:
                            break
                            
                    except socket.timeout:
                        # 如果已经收到部分数据，则返回现有数据
                        if data:
                            break
                        raise
                    
                if not data:
                    raise ConnectionError("收到空响应")
                
                # 解码并清理响应
                response = data.decode('utf-8').strip()
                if not response:
                    raise ValueError("响应为空字符串")
                    
                return response
                
            except (socket.timeout, ConnectionError) as e:
                last_exception = e
                retry_count += 1
                time.sleep(0.2 * retry_count)  # 重试等待时间递增
                
                # 最后一次重试前打印警告
                if retry_count == max_retries - 1:
                    print(f"警告: 命令 '{cmd}' 第{retry_count}次重试...")
                    
            except Exception as e:
                last_exception = e
                break  # 非网络错误立即退出
                
            finally:
                if sock:
                    try:
                        sock.close()
                    except:
                        pass
                self.socket = None  # 清除socket引用
        
        # 所有重试失败后的处理
        error_msg = f"命令 '{cmd}' 执行失败(重试{retry_count}次)"
        if last_exception:
            error_msg += f": {str(last_exception)}"
        
        return error_msg

    def stop(self):
        """安全停止线程"""
        self._running = False
        if self.socket:  # 如果socket存在，则关闭它以中断阻塞的recv
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except:
                pass
            self.socket = None
        self.wait(5000)  # 等待线程结束，最多5秒
