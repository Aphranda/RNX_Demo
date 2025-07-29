from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QStatusBar, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout, 
    QSizePolicy, QMessageBox, QCheckBox, QToolBar, QAction, QFileDialog
)
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QFontMetrics, QTextCursor, QTextCharFormat, QIcon
from PyQt5.QtCore import Qt, QPointF, QThread, pyqtSignal, QMutex, QSize
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtCore import QRegExp
import sys, os, psutil
import socket, select
import datetime
import time
import atexit
import hashlib
import shutil
import json, struct
import math
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone


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

class TcpClient:
    """带超时重发机制的TCP客户端"""
    def __init__(self):
        self.sock = None
        self.connected = False
        self.last_error = None  # 记录最后一次错误

    def connect(self, ip, port, timeout=3):
        self.close()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        try:
            self.sock.connect((ip, int(port)))
            self.connected = True
            self.last_error = None
            return True, "连接成功"
        except Exception as e:
            self.last_error = str(e)
            self.connected = False
            self.sock = None
            return False, f"连接失败: {e}"

    def send(self, msg, max_retries=3, base_timeout=1.0):
        """
        带超时重发机制的发送方法
        参数:
            msg: 要发送的消息字符串
            max_retries: 最大重试次数 (默认3次)
            base_timeout: 基础超时时间(秒)，会随重试次数增加 (默认1秒)
        返回:
            (是否成功, 状态信息)
        """
        if not self.connected or not self.sock:
            return False, "未连接"

        retry_count = 0
        last_exception = None
        
        while retry_count < max_retries:
            try:
                # 动态计算当前超时时间 (指数退避算法)
                current_timeout = min(base_timeout * (2 ** retry_count), 5.0)  # 最大不超过5秒
                self.sock.settimeout(current_timeout)
                
                # 发送数据
                self.sock.sendall(msg.encode('utf-8'))
                self.last_error = None
                return True, "发送成功"
                
            except (socket.timeout, ConnectionError) as e:
                last_exception = e
                retry_count += 1
                time.sleep(0.2 * retry_count)  # 重试等待时间递增
                
                # 尝试重建连接
                if isinstance(e, ConnectionError):
                    try:
                        ip, port = self.sock.getpeername()
                        self.connect(ip, port, current_timeout)
                    except:
                        pass
                
            except Exception as e:
                last_exception = e
                break  # 非网络错误立即退出
        
        # 所有重试失败后的处理
        self.last_error = str(last_exception) if last_exception else "未知错误"
        error_msg = f"发送失败(重试{retry_count}次)"
        if last_exception:
            error_msg += f": {str(last_exception)}"
        return False, error_msg

    def receive(self, bufsize=4096, max_retries=3, base_timeout=1.0):
        """
        带超时重发机制的接收方法
        参数:
            bufsize: 每次接收的缓冲区大小 (默认4096)
            max_retries: 最大重试次数 (默认3次)
            base_timeout: 基础超时时间(秒)，会随重试次数增加 (默认1秒)
        返回:
            (是否成功, 接收到的数据或错误信息)
        """
        if not self.connected or not self.sock:
            return False, "未连接"

        retry_count = 0
        last_exception = None
        
        while retry_count < max_retries:
            try:
                # 动态计算当前超时时间
                current_timeout = min(base_timeout * (2 ** retry_count), 5.0)
                self.sock.settimeout(current_timeout)
                
                chunks = []
                start_time = time.time()
                remaining_time = current_timeout
                
                while True:
                    try:
                        # 使用select检查可读性
                        ready = select.select([self.sock], [], [], min(0.1, remaining_time))
                        if not ready[0]:  # 超时
                            raise socket.timeout(f"接收超时 ({remaining_time:.1f}s)")
                        
                        data = self.sock.recv(bufsize)
                        if not data:  # 连接关闭
                            break
                            
                        chunks.append(data)
                        
                        # 检查是否收到完整消息（以换行符判断）
                        if b'\r\n' in data or b'\r' in data:
                            break
                            
                        # 更新剩余时间
                        remaining_time = current_timeout - (time.time() - start_time)
                        if remaining_time <= 0:
                            raise socket.timeout("总接收超时")
                            
                    except socket.timeout:
                        if chunks:  # 已有部分数据则返回
                            break
                        raise
                
                if not chunks:
                    raise ValueError("收到空响应")
                
                result = b''.join(chunks).decode('utf-8', errors='ignore').strip()
                self.last_error = None
                return True, result
                
            except (socket.timeout, ConnectionError) as e:
                last_exception = e
                retry_count += 1
                time.sleep(0.2 * retry_count)
                
                # 尝试重建连接
                if isinstance(e, ConnectionError):
                    try:
                        ip, port = self.sock.getpeername()
                        self.connect(ip, port, current_timeout)
                    except:
                        pass
                
            except Exception as e:
                last_exception = e
                break  # 非网络错误立即退出
        
        # 所有重试失败后的处理
        self.last_error = str(last_exception) if last_exception else "未知错误"
        error_msg = f"接收失败(重试{retry_count}次)"
        if last_exception:
            error_msg += f": {str(last_exception)}"
        return False, error_msg

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None
        self.connected = False
        self.last_error = None

class SimpleLinkDiagram(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(600)   # 原600，放大1.2倍
        self.setMinimumWidth(500)    # 原500，放大1.2倍
        self.current_link = "FEED_X_THETA"

    def set_link(self, link_mode):
        # 确保链路模式与类中定义的名称一致
        normalized_link = link_mode.upper().replace("__", "_")  # 处理可能的双下划线
        self.current_link = normalized_link
        self.update()


    def paintEvent(self, a0):
        super().paintEvent(a0)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # Fluent风格配色
        node_color = QColor("#0078d7")
        node_border = QColor("#005fa1")
        node_text = QColor("#222222")
        line_color = QColor("#b0b0b0")
        highlight_color = QColor("#ff4b1f")
        highlight_text = QColor("#ff4b1f")
        shadow_color = QColor(0, 0, 0, 30)

        font = QFont("Segoe UI", 13)  # 原11，放大1.2倍
        painter.setFont(font)

        # 参数（全部放大1.2倍）
        start_x = int(100)
        start_y = int(20)
        node_w = int(48)
        node_h = int(28)
        gap_y = int(44)

        # 八个节点
        node_list = [
            ("X_THETA", "FEED_X_THETA"),
            ("X_PHI", "FEED_X_PHI"),
            ("KU_THETA", "FEED_KU_THETA"),
            ("KU_PHI", "FEED_KU_PHI"),
            ("K_THETA", "FEED_K_THETA"),
            ("K_PHI", "FEED_K_PHI"),
            ("KA_THETA", "FEED_KA_THETA"),
            ("KA_PHI", "FEED_KA_PHI"),
        ]

        # 画COM节点阴影
        com_cx = start_x
        com_cy = start_y + (len(node_list) * (node_h + gap_y) - gap_y) // 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow_color)
        painter.drawEllipse(com_cx - node_w // 2 + 3, com_cy - node_h // 2 + 3, node_w, node_h)

        # 画COM节点
        painter.setPen(QPen(node_border, 2))
        painter.setBrush(node_color)
        painter.drawEllipse(com_cx - node_w // 2, com_cy - node_h // 2, node_w, node_h)
        painter.setPen(QPen(node_text, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawText(com_cx - node_w // 2 - int(60 * 1.2), com_cy - node_h // 2, int(56 * 1.2), node_h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "COM")

        # 画竖直排列的8个节点及连线
        node_x = com_cx + int(220 * 1.2)
        for i, (name, link_key) in enumerate(node_list):
            ny = start_y + i * (node_h + gap_y)
            # 连线
            if self.current_link == link_key:
                painter.setPen(QPen(highlight_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            else:
                painter.setPen(QPen(line_color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            # Fluent风格曲线
            ctrl1_x = com_cx + int(60 * 1.2)
            ctrl2_x = node_x - int(60 * 1.2)
            painter.drawPolyline(
                *[
                    QPointF(com_cx + node_w // 2, com_cy),
                    QPointF(ctrl1_x, com_cy),
                    QPointF(ctrl2_x, ny + node_h // 2),
                    QPointF(node_x - node_w // 2, ny + node_h // 2)
                ]
            )
            # 节点阴影
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow_color)
            painter.drawEllipse(node_x - node_w // 2 + 3, ny + 3, node_w, node_h)
            # 节点
            if self.current_link == link_key:
                painter.setPen(QPen(highlight_color, 2))
                painter.setBrush(QColor("white"))
            else:
                painter.setPen(QPen(node_border, 1))
                painter.setBrush(QColor("white"))
            painter.drawEllipse(node_x - node_w // 2, ny, node_w, node_h)
            # 文字
            if self.current_link == link_key:
                painter.setPen(QPen(highlight_text, 2))
            else:
                painter.setPen(QPen(node_text, 1))
            painter.drawText(node_x + node_w // 2 + 8, ny, int(100 * 1.2), node_h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)

        painter.end()

class AutoFontSizeLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._min_font_size = 6
        self._max_font_size = 72  # 增大最大值
        self._content_margin = 10  # 增加边距
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setProperty("class", "AutoFontSizeLabel")
        
        # 初始调整
        self.adjust_font_size()
 
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_font_size()
 
    def setText(self, text):
        super().setText(text)
        self.adjust_font_size()
 
    def adjust_font_size(self):
        text = self.text()
        if not text or self.width() <= 10:
            return
 
        # 计算可用空间（考虑边距和样式表padding）
        available_width = self.width() - 2 * self._content_margin
        available_height = self.height() - 2 * self._content_margin
        
        # 动态计算基准大小（基于控件高度）
        base_size = min(self._max_font_size, 
                      max(self._min_font_size, 
                          int(self.height() * 0.5)))  # 高度50%作为基准
 
        # 二进制搜索最佳大小
        low, high = self._min_font_size, self._max_font_size
        best_size = base_size
        font = QFont(self.font())
        
        while low <= high:
            mid = (low + high) // 2
            font.setPointSize(mid)
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(text)
            text_height = metrics.height()
            
            if text_width <= available_width and text_height <= available_height:
                best_size = mid
                low = mid + 1
            else:
                high = mid - 1
 
        # 应用新字体（同时设置font和样式表）
        font.setPointSize(best_size)
        self.setFont(font)
        
        # 关键步骤：通过样式表叠加修改（不影响其他样式）
        self.setStyleSheet(f"""
            AutoFontSizeLabel {{
                font-size: {best_size}pt;
                border: 2px solid #42a5f5;
                border-radius: 8px;
                background: #f5faff;
                background: {self.palette().color(self.backgroundRole()).name()};
                padding: 4px 10px;
                min-width: 60px;
                min-height: 24px;
                font-weight: bold;
                color: #42a5f5;
                color: {self.palette().color(self.foregroundRole()).name()};
            }}
        """)

class AutoFontSizeComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._min_font_size = 8
        self._max_font_size = 14
        self._content_margin = 5
        
    def showPopup(self):
        # 在显示下拉菜单前调整字体大小
        self.adjust_popup_font()
        super().showPopup()
        
    def adjust_popup_font(self):
        # 获取下拉视图
        view = self.view()
        if not view:
            return
            
        # 计算最大文本宽度
        metrics = QFontMetrics(view.font())
        max_width = max(metrics.horizontalAdvance(self.itemText(i)) 
                      for i in range(self.count()))
        
        # 计算可用宽度
        available_width = view.width() - 2 * self._content_margin
        
        if max_width > available_width and available_width > 0:
            # 计算合适的字体大小
            ratio = available_width / max_width
            new_size = max(self._min_font_size,
                          min(self._max_font_size,
                              int(view.font().pointSize() * ratio)))
            
            font = view.font()
            font.setPointSize(new_size)
            view.setFont(font)
            
    def resizeEvent(self, event):
        # 主控件也调整字体
        self.adjust_main_font()
        super().resizeEvent(event)
        
    def adjust_main_font(self):
        metrics = QFontMetrics(self.font())
        text_width = metrics.horizontalAdvance(self.currentText())
        available_width = self.width() - 2 * self._content_margin
        
        if text_width > available_width and available_width > 0:
            ratio = available_width / text_width
            new_size = max(self._min_font_size,
                          min(self._max_font_size,
                              int(self.font().pointSize() * ratio)))
            
            font = self.font()
            font.setPointSize(new_size)
            self.setFont(font)

class SignalUnitConverter:
    """
    信号源频率和功率单位安全换算类
    
    功能:
    - 频率单位转换 (Hz, kHz, MHz, GHz)
    - 功率单位转换 (dBm, mW, W, dBW, µW, nW)
    - 电场强度单位转换 (V/m, mV/m, µV/m, dBμV/m)
    - 安全数值转换和范围检查
    - 输入验证和异常处理
    """
    
    # 频率单位转换系数
    FREQ_UNITS = {
        'Hz': 1,
        'kHz': 1e3,
        'MHz': 1e6,
        'GHz': 1e9,
    }
    
    # 功率单位转换系数
    POWER_UNITS = {
        'dBm': 'dBm',
        'mW': 'mW',
        'W': 'W',
        'uW': 'uW',
        'nW': 'nW',
        'dBW': 'dBW',
    }

    # 电场强度单位转换系数
    E_FIELD_UNITS = {
        'V/m': 'V/m',
        'mV/m': 'mV/m',
        'uV/m': 'µV/m',
        'dBV/m': 'dBV/m',
    }

    # 自由空间波阻抗 (Ω)
    Z0 = 120 * math.pi  # 约376.73 Ω
    
    def __init__(self):
        # 默认频率单位
        self.default_freq_unit = 'GHz'
        # 默认功率单位
        self.default_power_unit = 'dBm'
        # 默认电场强度单位
        self.default_efield_unit = 'V/m'
        
        # 功率单位颜色映射 (用于UI显示)
        self.power_unit_colors = {
            'dBm': '#0078d7',
            'mW': '#228B22',
            'W': '#d32f2f',
            'dBW': '#e67e22',
            'uW': '#8e44ad',
            'nW': '#16a085'
        }

        self.efield_unit_colors = {
            'V/m': '#9b59b6',
            'mV/m': '#3498db',
            'µV/m': '#2ecc71',
            'dBμV/m': '#e74c3c'
        }

    def safe_float_convert(self, value: Union[str, float, int], 
                         default: float = 0.0) -> float:
        """
        安全转换为浮点数
        
        参数:
            value: 输入值 (可以是字符串或数字)
            default: 转换失败时的默认值
            
        返回:
            转换后的浮点数
        """
        if isinstance(value, (float, int)):
            return float(value)
            
        if not isinstance(value, str):
            return default
            
        try:
            # 移除单位和其他非数字字符
            cleaned = ''.join(c for c in value.replace(',', '') 
                            if c in '0123456789+-.eE')
            return float(cleaned) if cleaned else default
        except (ValueError, TypeError):
            return default

    def convert_frequency(self, value: Union[str, float, int], 
                         from_unit: str, to_unit: str) -> Tuple[float, str]:
        """
        频率单位转换
        
        参数:
            value: 输入频率值
            from_unit: 原单位 (Hz, kHz, MHz, GHz)
            to_unit: 目标单位 (Hz, kHz, MHz, GHz)
            
        返回:
            (转换后的值, 规范化后的单位)
        """
        # 规范化单位
        from_unit = self._normalize_freq_unit(from_unit)
        to_unit = self._normalize_freq_unit(to_unit)
        
        # 安全转换数值
        freq_value = self.safe_float_convert(value)
        
        # 转换为基准单位 (Hz)
        base_value = freq_value * self.FREQ_UNITS.get(from_unit, 1)
        
        # 转换为目标单位
        if to_unit in self.FREQ_UNITS:
            converted = base_value / self.FREQ_UNITS[to_unit]
            # 处理极小值
            if abs(converted) < 1e-12 and converted != 0:
                converted = 0.0
            return (converted, to_unit)
        
        return (freq_value, from_unit)  # 单位无效时返回原值和单位

    def convert_power(self, value: Union[str, float, int], 
                     from_unit: str, to_unit: str) -> Tuple[float, str]:
        """
        功率单位转换
        
        参数:
            value: 输入功率值
            from_unit: 原单位 (dBm, mW, W, dBW, µW, nW)
            to_unit: 目标单位 (dBm, mW, W, dBW, µW, nW)
            
        返回:
            (转换后的值, 规范化后的单位)
        """
        # 规范化单位
        from_unit = self._normalize_power_unit(from_unit)
        to_unit = self._normalize_power_unit(to_unit)
        
        # 安全转换数值
        power_value = self.safe_float_convert(value)
        
        # 相同单位无需转换
        if from_unit == to_unit:
            return (power_value, to_unit)
        
        # 全部转换为mW作为中间单位
        if from_unit == 'dBm':
            mW_value = 10 ** (power_value / 10)
        elif from_unit == 'mW':
            mW_value = power_value
        elif from_unit == 'W':
            mW_value = power_value * 1000
        elif from_unit == 'dBW':
            # 修正：dBW 到 mW 的转换公式
            mW_value = 10 ** ((power_value + 30) / 10)  # dBW + 30 = dBm
        elif from_unit == 'µW':
            mW_value = power_value / 1000
        elif from_unit == 'nW':
            mW_value = power_value / 1e6
        else:
            return (power_value, from_unit)  # 无效单位
        
        # 从mW转换为目标单位
        if to_unit == 'dBm':
            try:
                converted = 10 * math.log10(mW_value) if mW_value > 0 else -math.inf
            except (ValueError, ZeroDivisionError):
                converted = -math.inf
        elif to_unit == 'mW':
            converted = mW_value
        elif to_unit == 'W':
            converted = mW_value / 1000
        elif to_unit == 'dBW':
            try:
                # 修正：mW 到 dBW 的转换公式
                converted = 10 * math.log10(mW_value / 1000) if mW_value > 0 else -math.inf
            except (ValueError, ZeroDivisionError):
                converted = -math.inf
        elif to_unit == 'µW':
            converted = mW_value * 1000
        elif to_unit == 'nW':
            converted = mW_value * 1e6
        else:
            return (power_value, from_unit)  # 无效单位
        
        # 处理极小值
        if abs(converted) < 1e-12 and converted != 0:
            converted = 0.0
            
        return (converted, to_unit)

    def format_frequency(self, value: Union[str, float, int], 
                        unit: Optional[str] = None) -> str:
        """
        格式化频率显示
        
        参数:
            value: 频率值
            unit: 目标单位 (None时自动选择合适单位)
            
        返回:
            格式化后的字符串 (带单位)
        """
        freq_value = self.safe_float_convert(value)
        unit = self._normalize_freq_unit(unit) if unit else None
        
        if unit:
            converted, unit = self.convert_frequency(freq_value, 'Hz', unit)
            return f"{converted:.6f} {unit}"
        
        # 自动选择最佳单位
        abs_value = abs(freq_value)
        if abs_value >= 1e9:
            converted = freq_value / 1e9
            unit = 'GHz'
        elif abs_value >= 1e6:
            converted = freq_value / 1e6
            unit = 'MHz'
        elif abs_value >= 1e3:
            converted = freq_value / 1e3
            unit = 'kHz'
        else:
            converted = freq_value
            unit = 'Hz'
        
        # 确定小数位数
        if unit == 'GHz':
            decimal_places = 6 if abs(converted) < 10 else (4 if abs(converted) < 100 else 2)
        elif unit == 'MHz':
            decimal_places = 3
        elif unit == 'kHz':
            decimal_places = 1
        else:
            decimal_places = 0
            
        return f"{converted:.{decimal_places}f} {unit}"

    def format_power(self, value: Union[str, float, int], 
                    unit: Optional[str] = None) -> str:
        """
        格式化功率显示
        
        参数:
            value: 功率值
            unit: 目标单位 (None时自动选择合适单位)
            
        返回:
            格式化后的字符串 (带单位)
        """
        power_value = self.safe_float_convert(value)
        unit = self._normalize_power_unit(unit) if unit else None
        
        if unit:
            converted, unit = self.convert_power(power_value, 'dBm', unit)
            # 特殊处理对数单位的小数位数
            if unit in ['dBm', 'dBW']:
                return f"{converted:.2f} {unit}"
            return f"{converted:.6f} {unit}"
        
        # 自动选择最佳单位
        if isinstance(power_value, str) and 'dB' in power_value:
            # 如果输入已经是dBm/dBW，保持原样
            return f"{power_value:.2f} dBm" if 'dBm' in power_value else f"{power_value:.2f} dBW"
        
        # 尝试转换为mW以确定最佳单位
        try:
            if power_value <= -1000:  # 极小值处理
                mW_value = 0
            else:
                mW_value = 10 ** (power_value / 10) if power_value > -1000 else 0
        except:
            mW_value = 0
        
        if mW_value >= 1000:
            converted = mW_value / 1000
            unit = 'W'
        elif mW_value >= 1:
            converted = mW_value
            unit = 'mW'
        elif mW_value >= 1e-3:
            converted = mW_value * 1000
            unit = 'µW'
        else:
            converted = mW_value * 1e6
            unit = 'nW'
            
        # 根据数值大小调整小数位数
        if converted > 1000:
            return f"{converted:.2f} {unit}"
        elif converted > 100:
            return f"{converted:.3f} {unit}"
        elif converted > 10:
            return f"{converted:.4f} {unit}"
        else:
            return f"{converted:.6f} {unit}"

    def validate_frequency(self, freq_str: str) -> Tuple[bool, float, str]:
        """
        验证并解析频率字符串
        
        参数:
            freq_str: 频率字符串 (如 "10GHz", "100 MHz")
            
        返回:
            (是否有效, 数值, 单位)
        """
        if not isinstance(freq_str, str):
            return (False, 0.0, 'Hz')
            
        # 提取数值部分
        num_part = []
        unit_part = []
        has_digit = False
        has_decimal = False
        
        for c in freq_str.strip():
            if c in '0123456789':
                num_part.append(c)
                has_digit = True
            elif c in '+-.':
                if c == '.':
                    if has_decimal:
                        break  # 多个小数点无效
                    has_decimal = True
                num_part.append(c)
            else:
                unit_part.append(c)
                
        if not has_digit:
            return (False, 0.0, 'Hz')
            
        try:
            value = float(''.join(num_part))
            unit = ''.join(unit_part).strip()
            unit = self._normalize_freq_unit(unit) if unit else self.default_freq_unit
            
            # 放宽值范围检查
            if not (0 <= value < 1e20):
                return (False, value, unit)
                
            return (True, value, unit)
        except (ValueError, TypeError):
            return (False, 0.0, 'Hz')

    def validate_power(self, power_str: str) -> Tuple[bool, float, str]:
        """
        验证并解析功率字符串
        
        参数:
            power_str: 功率字符串 (如 "10dBm", "-100 mW")
            
        返回:
            (是否有效, 数值, 单位)
        """
        if not isinstance(power_str, str):
            return (False, 0.0, 'dBm')
            
        # 提取数值部分
        num_part = []
        unit_part = []
        has_digit = False
        has_decimal = False
        has_dB = False
        
        for c in power_str.strip():
            if c in '0123456789':
                num_part.append(c)
                has_digit = True
            elif c in '+-.':
                if c == '.':
                    if has_decimal:
                        break  # 多个小数点无效
                    has_decimal = True
                num_part.append(c)
            elif c.lower() == 'd':
                has_dB = True
                unit_part.append(c)
            else:
                unit_part.append(c)
                
        if not has_digit:
            return (False, 0.0, 'dBm')
            
        try:
            value = float(''.join(num_part))
            unit = ''.join(unit_part).strip()
            
            # 特殊处理dB/dBm/dBW
            if has_dB:
                if 'm' in unit.lower():
                    unit = 'dBm'
                elif 'w' in unit.lower():
                    unit = 'dBW'
                else:
                    unit = 'dBm'  # 默认dBm
            else:
                unit = self._normalize_power_unit(unit) if unit else self.default_power_unit
            
            # 放宽值范围检查
            if unit in ('dBm', 'dBW'):
                valid = -300 <= value <= 300  # 扩展范围
            else:
                valid = 0 <= value <= 1e12   # 扩展范围
                
            return (valid, value, unit)
        except (ValueError, TypeError):
            return (False, 0.0, 'dBm')

    def _normalize_freq_unit(self, unit: str) -> str:
        """规范化频率单位"""
        if not unit:
            return self.default_freq_unit
            
        unit = unit.strip().lower()
        if unit.startswith('ghz'):
            return 'GHz'
        elif unit.startswith('mhz'):
            return 'MHz'
        elif unit.startswith('khz'):
            return 'kHz'
        elif unit.startswith('hz'):
            return 'Hz'
        else:
            return self.default_freq_unit

    def _normalize_power_unit(self, unit: str) -> str:
        """规范化功率单位"""
        if not unit:
            return self.default_power_unit
            
        unit = unit.strip().lower()
        if unit.startswith('dbm'):
            return 'dBm'
        elif unit.startswith('dbw'):
            return 'dBW'
        elif unit.startswith('mw') or unit == 'm':
            return 'mW'
        elif unit.startswith('uw') or unit == 'u' or unit == 'μ':
            return 'µW'
        elif unit.startswith('nw') or unit == 'n':
            return 'nW'
        elif unit.startswith('w') or unit == 'v':
            return 'W'
        else:
            return self.default_power_unit

    def get_power_unit_color(self, unit: str) -> str:
        """获取功率单位的显示颜色"""
        norm_unit = self._normalize_power_unit(unit)
        return self.power_unit_colors.get(norm_unit, '#0078d7')
    
    def convert_efield(self, value: Union[str, float, int], 
                    from_unit: str, to_unit: str,
                    distance: float = 1.0) -> Tuple[float, str]:
        """
        电场强度单位转换（支持距离参数）
        
        参数:
            value: 输入场强值
            from_unit: 原单位 (V/m, mV/m, µV/m, dBμV/m, dBm)
            to_unit: 目标单位 (V/m, mV/m, µV/m, dBμV/m, dBm)
            distance: 测量距离 (米), 默认为1米
            
        返回:
            (转换后的值, 规范化后的单位)
        """
        # 规范化单位
        from_unit = self._normalize_efield_unit(from_unit)
        to_unit = self._normalize_efield_unit(to_unit)
        
        # 安全转换数值
        efield_value = self.safe_float_convert(value)
        
        # 相同单位无需转换
        if from_unit == to_unit:
            return (efield_value, to_unit)
        
        # 处理功率单位 (dBm/mW等) → 电场强度的转换
        if from_unit in self.POWER_UNITS:
            # 先将功率转换为dBm
            power_dbm, _ = self.convert_power(efield_value, from_unit, 'dBm')
            # 然后通过距离计算电场强度
            efield_v_m = self.dbm_to_efield(power_dbm, distance)
            # 最后转换到目标单位
            print()
            return self._convert_efield_inner(efield_v_m, 'V/m', to_unit)
        
        # 处理电场强度 → 功率单位的转换
        if to_unit in self.POWER_UNITS:
            # 先统一转换为V/m
            efield_v_m, _ = self._convert_efield_inner(efield_value, from_unit, 'V/m')
            # 然后通过距离计算功率
            power_dbm = self.efield_to_dbm(efield_v_m, distance)
            # 最后转换到目标功率单位
            return self.convert_power(power_dbm, 'dBm', to_unit)
        
        # 纯电场强度单位间的转换
        return self._convert_efield_inner(efield_value, from_unit, to_unit)

    def _convert_efield_inner(self, value: float,
                            from_unit: str, to_unit: str) -> Tuple[float, str]:
        """
        内部方法：处理纯电场强度单位间的转换
        """
        # 全部转换为µV/m作为中间单位
        if from_unit == 'V/m':
            uV_m_value = value * 1e6
        elif from_unit == 'mV/m':
            uV_m_value = value * 1e3
        elif from_unit == 'µV/m':
            uV_m_value = value
        elif from_unit == 'dBμV/m':
            uV_m_value = 10 ** (value / 20)
        else:
            return (value, from_unit)
        
        # 从µV/m转换为目标单位
        if to_unit == 'V/m':
            converted = uV_m_value / 1e6
        elif to_unit == 'mV/m':
            converted = uV_m_value / 1e3
        elif to_unit == 'µV/m':
            converted = uV_m_value
        elif to_unit == 'dBμV/m':
            try:
                converted = 20 * math.log10(uV_m_value) if uV_m_value > 0 else -math.inf
            except (ValueError, ZeroDivisionError):
                converted = -math.inf
        else:
            return (value, from_unit)
        
        return (converted, to_unit)

    def efield_to_power_density(self, efield: Union[str, float, int], 
                               efield_unit: str = 'V/m') -> Tuple[float, str]:
        """
        电场强度转换为功率密度 (W/m²)
        
        参数:
            efield: 电场强度值
            efield_unit: 电场强度单位
            
        返回:
            (功率密度值, 'W/m²')
        """
        # 转换为V/m
        e_v_m, _ = self.convert_efield(efield, efield_unit, 'V/m')
        
        # 计算功率密度 S = E² / Z0
        power_density = (e_v_m ** 2) / self.Z0
        
        return (power_density, 'W/m²')
    
    def power_density_to_efield(self, power_density: Union[str, float, int], 
                              power_unit: str = 'W/m²') -> Tuple[float, str]:
        """
        功率密度转换为电场强度 (V/m)
        
        参数:
            power_density: 功率密度值
            power_unit: 功率密度单位 (支持 W/m², mW/m², µW/m²)
            
        返回:
            (电场强度值, 'V/m')
        """
        # 转换为W/m²
        s_w_m2 = self.safe_float_convert(power_density)
        
        # 处理不同单位
        if power_unit == 'mW/m²':
            s_w_m2 *= 1e-3
        elif power_unit == 'µW/m²':
            s_w_m2 *= 1e-6
        
        # 计算电场强度 E = sqrt(S * Z0)
        if s_w_m2 > 0:
            efield = math.sqrt(s_w_m2 * self.Z0)
        else:
            efield = 0.0
        
        return (efield, 'V/m')
    
    def format_efield(self, value: Union[str, float, int], 
                     unit: Optional[str] = None) -> str:
        """
        格式化电场强度显示
        
        参数:
            value: 场强值
            unit: 目标单位 (None时自动选择合适单位)
            
        返回:
            格式化后的字符串 (带单位)
        """
        efield_value = self.safe_float_convert(value)
        unit = self._normalize_efield_unit(unit) if unit else None
        
        if unit:
            converted, unit = self.convert_efield(efield_value, 'V/m', unit)
            # 特殊处理对数单位的小数位数
            if unit == 'dBμV/m':
                return f"{converted:.2f} {unit}"
            return f"{converted:.6f} {unit}"
        
        # 自动选择最佳单位
        abs_value = abs(efield_value)
        if abs_value >= 1:
            converted = efield_value
            unit = 'V/m'
        elif abs_value >= 1e-3:
            converted = efield_value * 1e3
            unit = 'mV/m'
        else:
            converted = efield_value * 1e6
            unit = 'µV/m'
            
        # 根据数值大小调整小数位数
        if converted > 1000:
            return f"{converted:.2f} {unit}"
        elif converted > 100:
            return f"{converted:.3f} {unit}"
        elif converted > 10:
            return f"{converted:.4f} {unit}"
        else:
            return f"{converted:.6f} {unit}"
    
    def validate_efield(self, efield_str: str) -> Tuple[bool, float, str]:
        """
        验证并解析电场强度字符串
        
        参数:
            efield_str: 场强字符串 (如 "10V/m", "100 dBμV/m")
            
        返回:
            (是否有效, 数值, 单位)
        """
        if not isinstance(efield_str, str):
            return (False, 0.0, 'V/m')
            
        # 提取数值部分
        num_part = []
        unit_part = []
        has_digit = False
        has_decimal = False
        has_dB = False
        
        for c in efield_str.strip():
            if c in '0123456789':
                num_part.append(c)
                has_digit = True
            elif c in '+-.':
                if c == '.':
                    if has_decimal:
                        break  # 多个小数点无效
                    has_decimal = True
                num_part.append(c)
            elif c.lower() == 'd':
                has_dB = True
                unit_part.append(c)
            else:
                unit_part.append(c)
                
        if not has_digit:
            return (False, 0.0, 'V/m')
            
        try:
            value = float(''.join(num_part))
            unit = ''.join(unit_part).strip()
            
            # 特殊处理dBμV/m
            if has_dB:
                if 'v/m' in unit.lower() or 'μv/m' in unit.lower():
                    unit = 'dBμV/m'
                else:
                    unit = 'dBμV/m'  # 默认
            else:
                unit = self._normalize_efield_unit(unit) if unit else self.default_efield_unit
            
            # 放宽值范围检查
            if unit == 'V/m':
                valid = 0 <= value <= 1e6
            elif unit == 'mV/m':
                valid = 0 <= value <= 1e9
            elif unit == 'µV/m':
                valid = 0 <= value <= 1e12
            elif unit == 'dBμV/m':
                valid = 0 <= value <= 240  # 约1MV/m
            else:
                valid = False
                
            return (valid, value, unit)
        except (ValueError, TypeError):
            return (False, 0.0, 'V/m')
        
    def _normalize_efield_unit(self, unit: str) -> str:
        """规范化电场强度单位"""
        if not unit:
            return self.default_efield_unit
            
        unit = unit.strip().lower()
        if unit.startswith('v/m'):
            return 'V/m'
        elif unit.startswith('mv/m'):
            return 'mV/m'
        elif unit.startswith('µv/m') or unit.startswith('uv/m'):
            return 'µV/m'
        elif unit.startswith('dbμv/m') or unit.startswith('dbuv/m') or unit.startswith('dbu'):
            return 'dBμV/m'
        else:
            return self.default_efield_unit
        
    def get_efield_unit_color(self, unit: str) -> str:
        """获取电场强度单位的显示颜色"""
        norm_unit = self._normalize_efield_unit(unit)
        return self.efield_unit_colors.get(norm_unit, '#9b59b6')

    def dbm_to_efield(self, dbm: float, distance: float = 1.0, antenna_gain: float = 1.0) -> float:
        """
        将dBm转换为电场强度 (V/m)
        
        参数:
            dbm: 发射功率 (dBm)
            distance: 距离 (米), 默认为1米
            antenna_gain: 天线增益 (无量纲), 默认为1 (各向同性天线)
        
        返回:
            电场强度 (V/m)
        """
        # dBm → 功率 (W)
        power_w = 10 ** (dbm / 10) * 1e-3
        
        # 功率密度 (W/m²)
        power_density = (power_w * antenna_gain) / (4 * math.pi * distance ** 2)
        
        # 电场强度 (V/m)
        efield = math.sqrt(power_density * self.Z0)
        
        return efield
    
    def efield_to_dbm(self, efield: float, distance: float = 1.0, antenna_gain: float = 1.0) -> float:
        """
        将电场强度 (V/m) 转换为 dBm
        
        参数:
            efield: 电场强度 (V/m)
            distance: 距离 (米), 默认为1米
            antenna_gain: 天线增益 (无量纲), 默认为1
        
        返回:
            发射功率 (dBm)
        """
        # 功率密度 (W/m²)
        power_density = (efield ** 2) / self.Z0
        
        # 功率 (W)
        power_w = power_density * (4 * math.pi * distance ** 2) / antenna_gain
        
        # W → dBm
        dbm = 10 * math.log10(power_w * 1e3) if power_w > 0 else -math.inf
        
        return dbm
    def convert_power_with_distance(self, value: Union[str, float, int], 
                                  from_unit: str, to_unit: str,
                                  distance: float = 1.0) -> Tuple[float, str]:
        """
        支持距离参数的功率单位转换
        
        参数:
            value: 输入值
            from_unit: 原单位
            to_unit: 目标单位
            distance: 距离 (米)
            
        返回:
            (转换后的值, 单位)
        """
        # 处理电场强度单位转换
        if (from_unit in self.E_FIELD_UNITS and to_unit in self.POWER_UNITS) or \
           (from_unit in self.POWER_UNITS and to_unit in self.E_FIELD_UNITS):
            
            # 功率 → 电场强度
            if from_unit in self.POWER_UNITS:
                power_dbm, _ = self.convert_power(value, from_unit, 'dBm')
                efield = self.dbm_to_efield(power_dbm, distance)
                return self.convert_efield(efield, 'V/m', to_unit)
            
            # 电场强度 → 功率
            else:
                efield_v_m, _ = self.convert_efield(value, from_unit, 'V/m')
                dbm = self.efield_to_dbm(efield_v_m, distance)
                return self.convert_power(dbm, 'dBm', to_unit)
        
        # 普通功率单位转换
        return self.convert_power(value, from_unit, to_unit)

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QToolBar, QTextEdit, QComboBox, 
    QLabel, QAction, QLineEdit, QMenu, QFileDialog
)
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor, QFont, QIcon
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from datetime import datetime
import sys

class LogWidget(QWidget):
    """
    综合日志控件，支持：
    - 多级日志显示（不同颜色）
    - 工具栏控制（字体、过滤、换行等）
    - 日志搜索与高亮
    - 右键菜单操作
    - 日志导出
    - 自动滚动控制
    """
    
    # 定义日志级别
    LEVELS = {
        "DEBUG":    ("#666666", "Debug"),
        "INFO":     ("#000000", "Info"),
        "SUCCESS":  ("#228B22", "Success"),
        "WARNING":  ("#FF8C00", "Warning"),
        "ERROR":    ("#FF0000", "Error"),
        "CRITICAL": ("#8B0000", "Critical"),
        "SEND":     ("#0078D7", "Send"),
        "RECV":     ("#8E44AD", "Receive")
    }

    # 信号：当日志级别超过阈值时触发
    errorLogged = pyqtSignal(str)  # (error_message)

    def __init__(self, parent=None, max_lines=5000, default_level="INFO"):
        super().__init__(parent)
        self.max_lines = max_lines
        self._auto_scroll = True
        self._setup_ui()
        self._init_settings(default_level)
        self._connect_signals()

    def _setup_ui(self):
        """初始化UI组件"""
        # 主布局
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)

        # 工具栏
        self._setup_toolbar()
        
        # 文本编辑区域
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QTextEdit.NoWrap)
        self.text_edit.setFont(QFont("Consolas", 10))
        self.text_edit.setContextMenuPolicy(Qt.CustomContextMenu)
        
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.text_edit)

    def _setup_toolbar(self):
        """初始化工具栏"""
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)

        # 日志级别过滤
        self.level_combo = QComboBox()
        self.level_combo.addItem("ALL", "ALL")
        for level, (_, display_name) in self.LEVELS.items():
            self.level_combo.addItem(display_name, level)
        self.toolbar.addWidget(QLabel("级别:"))
        self.toolbar.addWidget(self.level_combo)

        # 字体大小
        self.font_combo = QComboBox()
        self.font_combo.addItems(map(str, range(8, 16)))
        self.font_combo.setCurrentText("10")
        self.toolbar.addWidget(QLabel("字体:"))
        self.toolbar.addWidget(self.font_combo)

        # 自动换行
        self.wrap_action = QAction(QIcon.fromTheme("format-justify-fill"), "自动换行", self)
        self.wrap_action.setCheckable(True)
        self.toolbar.addAction(self.wrap_action)

        # 时间戳
        self.timestamp_action = QAction(QIcon.fromTheme("clock"), "时间戳", self)
        self.timestamp_action.setCheckable(True)
        self.timestamp_action.setChecked(True)
        self.toolbar.addAction(self.timestamp_action)

        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索...")
        self.search_edit.setMaximumWidth(200)
        self.toolbar.addWidget(self.search_edit)
        self.search_action = QAction(QIcon.fromTheme("edit-find"), "搜索", self)
        self.toolbar.addAction(self.search_action)

        # 清空按钮
        self.clear_action = QAction(QIcon.fromTheme("edit-clear"), "清空", self)
        self.toolbar.addAction(self.clear_action)

    def _init_settings(self, default_level):
        """初始化默认设置"""
        self.current_level = default_level
        self.enabled_levels = set(self.LEVELS.keys())
        self._highlight_format = QTextCharFormat()
        self._highlight_format.setBackground(QColor("#FFFF00"))

    def _connect_signals(self):
        """连接信号与槽"""
        # 工具栏信号
        self.level_combo.currentTextChanged.connect(self._update_log_level)
        self.font_combo.currentTextChanged.connect(self._update_font_size)
        self.wrap_action.toggled.connect(self._toggle_word_wrap)
        self.timestamp_action.toggled.connect(lambda x: setattr(self, "_show_timestamps", x))
        self.search_action.triggered.connect(self._search_text)
        self.search_edit.returnPressed.connect(self._search_text)
        self.clear_action.triggered.connect(self.clear)

        # 文本编辑区域信号
        self.text_edit.customContextMenuRequested.connect(self._show_context_menu)
        self.text_edit.verticalScrollBar().valueChanged.connect(
            lambda: setattr(self, "_auto_scroll", 
            self.text_edit.verticalScrollBar().value() == self.text_edit.verticalScrollBar().maximum())
        )

    # -------------------- 核心功能 --------------------
    def log(self, message, level="INFO"):
        """
        记录日志
        :param message: 日志消息
        :param level: 日志级别 (DEBUG/INFO/SUCCESS/WARNING/ERROR/CRITICAL/SEND/RECV)
        """
        if level not in self.LEVELS or level not in self.enabled_levels:
            return

        color, _ = self.LEVELS[level]
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        html = []
        if hasattr(self, "_show_timestamps") and self._show_timestamps:
            html.append(f'<span style="color:gray;">[{timestamp}]</span>')
        html.append(f'<span style="color:{color};font-weight:bold;">[{level}]</span>')
        html.append(f'<span style="color:{color};">{message}</span>')
        
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(" ".join(html) + "<br>")
        
        # 自动滚动
        if self._auto_scroll:
            self.text_edit.ensureCursorVisible()
        
        # 限制最大行数
        if self.text_edit.document().blockCount() > self.max_lines:
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
        
        # 触发错误信号
        if level in ("ERROR", "CRITICAL"):
            self.errorLogged.emit(message)

    def clear(self):
        """清空日志"""
        self.text_edit.clear()

    # -------------------- 工具栏功能 --------------------
    def _update_log_level(self):
        """更新显示的日志级别"""
        level = self.level_combo.currentData()
        if level == "ALL":
            self.enabled_levels = set(self.LEVELS.keys())
        else:
            self.enabled_levels = {level}

    def _update_font_size(self, size):
        """更新字体大小"""
        font = self.text_edit.font()
        font.setPointSize(int(size))
        self.text_edit.setFont(font)

    def _toggle_word_wrap(self, enabled):
        """切换自动换行"""
        self.text_edit.setLineWrapMode(QTextEdit.WidgetWidth if enabled else QTextEdit.NoWrap)

    def _search_text(self):
        """搜索文本并高亮"""
        text = self.search_edit.text().strip()
        if not text:
            return
        
        # 清除旧的高亮
        self._clear_highlights()
        
        # 搜索并高亮
        cursor = self.text_edit.document().find(text)
        while not cursor.isNull():
            cursor.mergeCharFormat(self._highlight_format)
            cursor = self.text_edit.document().find(text, cursor)

    def _clear_highlights(self):
        """清除所有高亮"""
        cursor = self.text_edit.textCursor()
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(QTextCharFormat())

    # -------------------- 右键菜单 --------------------
    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        
        # 标准操作
        copy_action = menu.addAction("复制")
        copy_action.triggered.connect(self._copy_selected)
        
        select_all_action = menu.addAction("全选")
        select_all_action.triggered.connect(self.text_edit.selectAll)
        
        menu.addSeparator()
        
        # 导出操作
        export_action = menu.addAction("导出日志...")
        export_action.triggered.connect(self._export_log)
        
        menu.exec_(self.text_edit.mapToGlobal(pos))

    def _copy_selected(self):
        """复制选中文本"""
        self.text_edit.copy()

    def _export_log(self):
        """导出日志到文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", "", "文本文件 (*.txt);;HTML文件 (*.html)"
        )
        if not file_path:
            return
        
        try:
            if file_path.endswith(".html"):
                content = self.text_edit.toHtml()
            else:
                content = self.text_edit.toPlainText()
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            self.log(f"日志已导出到: {file_path}", "SUCCESS")
        except Exception as e:
            self.log(f"导出失败: {str(e)}", "ERROR")

    # -------------------- 实用方法 --------------------
    def set_max_lines(self, max_lines):
        """设置最大日志行数"""
        self.max_lines = max(100, int(max_lines))

    def set_auto_scroll(self, enabled):
        """设置是否自动滚动到底部"""
        self._auto_scroll = bool(enabled)
        if enabled:
            self.text_edit.ensureCursorVisible()


class StatusPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(240)
        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(18, 5, 18, 5)
        h_layout.setSpacing(10)



        # 单位换算实例化
        self.unit_converter = SignalUnitConverter()

        # 运动模组状态（独立外框）
        motion_group = QGroupBox("运动模组状态")
        motion_layout = QVBoxLayout(motion_group)
        self.motion_label = QLabel("")
        self.motion_label.setProperty("panelTitle", True)
        motion_layout.addWidget(self.motion_label)

        self.motion_grid = QGridLayout()
        self.motion_grid.setSpacing(6)
        self.motion_grid.setVerticalSpacing(6)  # 增大竖向间距
        motion_layout.addLayout(self.motion_grid)
        axes = ["X", "KU", "K", "KA", "Z"]
        self.motion_reach = {}
        self.motion_home = {}
        self.motion_speed = {}
        self.motion_grid.addWidget(QLabel("轴"), 0, 0)
        self.motion_grid.addWidget(QLabel("达位"), 0, 1)
        self.motion_grid.addWidget(QLabel("复位"), 0, 2)
        self.motion_grid.addWidget(QLabel("速度"), 0, 3)
        for i, axis in enumerate(axes):
            self.motion_grid.addWidget(QLabel(axis), i+1, 0)
            self.motion_reach[axis] = QLabel("-")
            self.motion_reach[axis].setProperty("statusValue", True)
            self.motion_reach[axis].setMinimumHeight(20)  # 增高
            self.motion_grid.addWidget(self.motion_reach[axis], i+1, 1)
            self.motion_home[axis] = QLabel("-")
            self.motion_home[axis].setProperty("statusValue", True)
            self.motion_home[axis].setMinimumHeight(20)
            self.motion_grid.addWidget(self.motion_home[axis], i+1, 2)
            self.motion_speed[axis] = QLabel("-")
            self.motion_speed[axis].setProperty("statusValue", True)
            self.motion_speed[axis].setMinimumHeight(20)
            self.motion_grid.addWidget(self.motion_speed[axis], i+1, 3)
        motion_layout.addStretch()
    


        # 信号源状态（独立外框）
        src_group = QGroupBox("信号源状态")
        src_layout = QVBoxLayout(src_group)
        self.src_label = QLabel("")
        self.src_label.setProperty("panelTitle", True)
        src_layout.addWidget(self.src_label)


        self.src_grid = QGridLayout()
        self.src_grid.setSpacing(6)
        src_layout.addLayout(self.src_grid)

        # 信号源频率信息
        self.src_grid.addWidget(QLabel("信号频率:"), 0, 0)
        self.src_freq = AutoFontSizeLabel()
        self.src_freq.setProperty("statusValue", True)
        self.src_grid.addWidget(self.src_freq, 0, 1)

        # 频率单位下拉框
        self.freq_unit_combo = AutoFontSizeComboBox()
        self.freq_unit_combo.addItems(list(self.unit_converter.FREQ_UNITS.keys()))
        self.freq_unit_combo.setCurrentText(self.unit_converter.default_freq_unit)
        self.src_grid.addWidget(self.freq_unit_combo, 0, 2)

        # 信号源功率信息
        self.src_grid.addWidget(QLabel("信号功率:"), 1, 0)
        self.src_raw_power = AutoFontSizeLabel()
        self.src_raw_power.setProperty("statusValue", True)
        self.src_grid.addWidget(self.src_raw_power, 1, 1)

        # 功率单位下拉框
        self.raw_power_unit_combo = AutoFontSizeComboBox()
        self.raw_power_unit_combo.addItems(list(self.unit_converter.POWER_UNITS.keys()))
        self.raw_power_unit_combo.addItems(list(self.unit_converter.E_FIELD_UNITS.keys()))
        self.raw_power_unit_combo.setCurrentText(self.unit_converter.default_power_unit)
        self.src_grid.addWidget(self.raw_power_unit_combo, 1, 2)

        self.src_grid.addWidget(QLabel("馈源功率:"), 2, 0)
        self.src_power = AutoFontSizeLabel()
        self.src_power.setProperty("statusValue", True)
        self.src_grid.addWidget(self.src_power, 2, 1)

        # 馈源功率单位下拉框
        self.power_unit_combo = AutoFontSizeComboBox()
        self.power_unit_combo.addItems(list(self.unit_converter.POWER_UNITS.keys()))
        self.power_unit_combo.addItems(list(self.unit_converter.E_FIELD_UNITS.keys()))
        self.power_unit_combo.setCurrentText(self.unit_converter.default_power_unit)
        self.src_grid.addWidget(self.power_unit_combo, 2, 2)

        self.src_grid.addWidget(QLabel("RF输出:"), 3, 0)
        self.src_rf = QLabel("-")
        self.src_rf.setProperty("statusValue", True)
        self.src_grid.addWidget(self.src_rf, 3, 1)


        # 新增：校准文件状态
        # self.src_grid.addWidget(QLabel("校准文件:"), 4, 0)
        self.cal_file_status = AutoFontSizeLabel("Calib Miss")
        self.cal_file_status.setProperty("AutoScale", True)
        self.cal_file_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.src_grid.addWidget(self.cal_file_status, 3, 2)
        
        # 新增：校准文件路径输入和加载按钮
        self.src_grid.addWidget(QLabel("校准路径:"), 5, 0)
        self.cal_file_input = QLineEdit()

        self.cal_file_input.setPlaceholderText("选择校准文件...")
        self.src_grid.addWidget(self.cal_file_input, 5, 1)
        
        self.load_cal_btn = QPushButton("加载")
        # self.load_cal_btn.setFixedWidth(80)  # 设置固定宽度
        self.src_grid.addWidget(self.load_cal_btn, 5, 2)

        src_layout.addStretch()

        motion_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        src_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        h_layout.addWidget(motion_group, stretch=1)
        h_layout.addWidget(src_group, stretch=1)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RNX Quantum Antenna Test System - Demo")
        self.setGeometry(50, 40, 1800, 1100)
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.apply_flat_style()  # 应用Fluent样式
        self.tcp_client = TcpClient()
        self.comm_mutex = QMutex()
        self.status_thread = None

        self.cal_manager = None  # 添加这行初始化
        self.compensation_enabled = False  # 同时初始化补偿标志
        self.calibration_data = None  # 初始化校准数据

        self.status_cache = {
            "motion": {axis: {"reach": "-", "home": "-", "speed": "-"} for axis in ["X", "KU", "K", "KA", "Z"]},
            "src": {"freq": "-", "power": "-", "rf": "-"}
        }

        self.init_ui()  # 只调用一次
    
    def apply_flat_style(self):
        # Fluent Design风格主色，适配宽屏，控件高度和间距缩小
        self.setStyleSheet("""
            QMainWindow {
                background: #f7f7f7;
            }
            /* 新增QCheckBox样式 */
            QCheckBox {
                spacing: 8px;
                font-size: 24px;
                font-weight: bold;
                color: #222;
            }
            QCheckBox::indicator {
                width: 24px;
                height: 24px;
                border: 2px solid #b0b0b0;
                border-radius: 4px;
                background: #f9f9f9;
            }
            QCheckBox::indicator:checked {
                background: #1976d2;
                border: 2px solid #1976d2;
                image: url(:/qss_icons/rc/checkbox_checked.png);
            }
            QCheckBox::indicator:unchecked:hover {
                border: 2px solid #64b5f6;
            }
            QCheckBox::indicator:checked:hover {
                background: #1565c0;
                border: 2px solid #1565c0;
            }
            QGroupBox {
                border: 2px solid #e0e0e0;
                border-radius: 14px;
                margin-top: 15px;
                background: #ffffff;
                font-weight: bold;
                font-size: 24px;
                color: #222;
                padding: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                top: 6px;
                padding: 0 8px 0 8px;
                color: #42a5f5;
                font-size: 20px;
                font-weight: bold;
            }
            QLabel[panelTitle="true"] {
                color: #42a5f5;
                font-size: 24px;
                font-weight: bold;
            }
            QLabel {
                font-size: 24px;
                color: #222;
                font-weight: bold;
            }
            QLabel[statusValue="true"] {
                border: 2px solid #42a5f5;
                border-radius: 8px;
                background: #f5faff;
                padding: 4px 10px;
                min-width: 60px;
                min-height: 24px;
                font-size: 24px;
                font-weight: bold;
                color: #42a5f5;
            }
            QLabel[AutoScale="true"]:not(AutoFontSizeLabel) {
                border: 2px solid #42a5f5;
                border-radius: 8px;
                background: #f5faff;
                padding: 4px 10px;
                min-width: 60px;
                min-height: 24px;
                font-weight: bold;
                color: #42a5f5;
            }
            QLineEdit, QTextEdit {
                border: 2px solid #b0b0b0;
                border-radius: 8px;
                padding: 6px 10px;
                background: #f9f9f9;
                font-size: 24px;
                min-height: 28px;
                font-weight: bold;
            }
            QComboBox {
                border: 2px solid #b0b0b0;
                border-radius: 8px;
                padding: 4px 8px 4px 8px;
                background: #f9f9f9;
                font-size: 24px;
                min-height: 28px;
                font-weight: bold;
            }
            QPushButton {
                background: #1976d2;
                color: #fff;
                border: none;
                border-radius: 8px;
                padding: 6px 18px;
                font-size: 24px;
                font-weight: bold;
                min-height: 32px;
            }
            QPushButton:hover {
                background: #1565c0;
            }
            QPushButton:pressed {
                background: #0d47a1;
            }
            QPushButton:hover {
                background: #64b5f6;
            }
            QPushButton:pressed {
                background: #42a5f5;
            }
            QStatusBar {
                background: #f1f1f1;
                color: #42a5f5;
                font-size: 24px;
                font-weight: bold;
            }
            /* 禁用状态样式 */
            QGroupBox:disabled {
                border: 2px solid #b0b0b0;
                background: #f0f0f0;
                color: #a0a0a0;
            }
            QGroupBox:disabled::title {
                color: #a0a0a0;
            }
            QPushButton:disabled {
                background: #e0e0e0;
                color: #a0a0a0;
            }
            QComboBox:disabled {
                background: #e0e0e0;
                color: #a0a0a0;
            }
            QLabel:disabled {
                color: #a0a0a0;
            }
        """)

    def init_ui(self):
        # --- 主体横向分区 ---
        main_layout = QHBoxLayout()  # ← 这里新增

        # ===== 左侧：链路图 + 日志 =====
        left_panel = QVBoxLayout()
        # 链路图区域
        link_group = QGroupBox("链路图")
        link_layout = QVBoxLayout()
        link_group.setLayout(link_layout)
        self.link_diagram = SimpleLinkDiagram()
        center_layout = QHBoxLayout()
        center_layout.addStretch()
        center_layout.addWidget(self.link_diagram)
        center_layout.addStretch()
        link_layout.addLayout(center_layout)
        left_panel.addWidget(link_group, stretch=3)

        # 日志区域
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout()
        log_group.setLayout(log_layout)
        self.log_output = LogWidget()  # 使用自定义日志控件
        log_layout.addWidget(self.log_output)
        left_panel.addWidget(log_group, stretch=2)

        main_layout.addLayout(left_panel, stretch=2)

        # ===== 右侧：状态 + 控制 =====
        right_panel = QVBoxLayout()

        # 状态显示
        status_group = QGroupBox("状态显示")
        status_layout = QVBoxLayout()
        status_group.setLayout(status_layout)
        self.status_panel = StatusPanel()
        status_layout.addWidget(self.status_panel)
        right_panel.addWidget(status_group)

        right_panel.addSpacing(-15)  # 减少标题与内容间距
        # ETH设置
        eth_group = QGroupBox()
        eth_layout = QHBoxLayout()
        eth_group.setLayout(eth_layout)
        eth_layout.addWidget(QLabel("ETH IP:"))
        self.eth_ip_input = QLineEdit()
        self.eth_ip_input.setPlaceholderText("192.168.1.11")
        eth_layout.addWidget(self.eth_ip_input)
        eth_layout.addWidget(QLabel("Port:"))
        self.eth_port_input = QLineEdit()
        self.eth_port_input.setPlaceholderText("7")
        eth_layout.addWidget(self.eth_port_input)
        self.eth_connect_btn = QPushButton("连接")
        self.eth_connect_btn.clicked.connect(self.connect_eth)
        eth_layout.addWidget(self.eth_connect_btn)
        # 新增断开连接按钮
        self.eth_disconnect_btn = QPushButton("断开连接")
        self.eth_disconnect_btn.clicked.connect(self.disconnect_eth)
        eth_layout.addWidget(self.eth_disconnect_btn)

        # 新增频率与馈源联动单选框
        self.freq_feed_link_check = QCheckBox("频率联动")
        self.freq_feed_link_check.setChecked(False)  # 默认不选中
        eth_layout.addWidget(self.freq_feed_link_check)

        self.freq_feed_link_check.stateChanged.connect(self._on_freq_link_state_changed)
        self.current_feed_mode = None
        self._is_freq_link_connected = False

        eth_layout.addStretch()
        right_panel.addWidget(eth_group)
        
        # 链路控制
        link_ctrl_group = QGroupBox("链路控制")
        link_ctrl_layout = QHBoxLayout()
        link_ctrl_group.setLayout(link_ctrl_layout)
        self.link_mode_combo = QComboBox()
        self.link_mode_combo.addItems([
            "FEED_X_THETA", "FEED_X_PHI", "FEED_KU_THETA", "FEED_KU_PHI",
            "FEED_K_THETA", "FEED_K_PHI", "FEED_KA_THETA", "FEED_KA_PHI"
        ])
        link_ctrl_layout.addWidget(QLabel("链路模式:"))
        link_ctrl_layout.addWidget(self.link_mode_combo)
        self.link_set_btn = QPushButton("设置链路")
        self.link_set_btn.clicked.connect(self.send_link_cmd)
        link_ctrl_layout.addWidget(self.link_set_btn)
        self.link_query_btn = QPushButton("查询链路")
        self.link_query_btn.clicked.connect(self.query_link_cmd)
        link_ctrl_layout.addWidget(self.link_query_btn)
        right_panel.addWidget(link_ctrl_group)

        # 新增：校准文件加载
        self.status_panel.load_cal_btn.clicked.connect(self.load_calibration_file)


        # 信号源控制
        src_group = QGroupBox("信号源控制")
        src_layout = QGridLayout()
        src_group.setLayout(src_layout)

        src_layout.addWidget(QLabel("信号频率:"), 0, 0)
        self.freq_input = QLineEdit()
        self.freq_input.setPlaceholderText("如 8GHz")
        src_layout.addWidget(self.freq_input, 0, 1,1,2)
        self.freq_btn = QPushButton("设置频率")
        self.freq_btn.clicked.connect(self.send_freq_cmd)
        src_layout.addWidget(self.freq_btn, 0, 3)
        self.freq_query_btn = QPushButton("查询频率")
        self.freq_query_btn.clicked.connect(self.query_freq_cmd)
        src_layout.addWidget(self.freq_query_btn, 0, 4)

        src_layout.addWidget(QLabel("馈源功率:"), 1, 0)
        self.power_input = QLineEdit()
        self.power_input.setPlaceholderText("如 -40dBm")
        src_layout.addWidget(self.power_input, 1, 1)

        self.raw_power_input = QLineEdit()
        self.raw_power_input.setPlaceholderText("信号源实际输出")
        src_layout.addWidget(self.raw_power_input,1,2)

        self.power_btn = QPushButton("设置功率")
        self.power_btn.clicked.connect(self.send_power_cmd)
        src_layout.addWidget(self.power_btn, 1, 3)
        self.power_query_btn = QPushButton("查询功率")
        self.power_query_btn.clicked.connect(self.query_power_cmd)
        src_layout.addWidget(self.power_query_btn, 1, 4)

        src_layout.addWidget(QLabel("RF输出:"), 2, 0)
        self.output_combo = QComboBox()
        self.output_combo.addItems(["ON", "OFF"])
        src_layout.addWidget(self.output_combo, 2, 1,0,2)
        self.output_btn = QPushButton("设置输出")
        self.output_btn.clicked.connect(self.send_output_cmd)
        src_layout.addWidget(self.output_btn, 2, 3)
        self.output_query_btn = QPushButton("查询输出")
        self.output_query_btn.clicked.connect(self.query_output_cmd)
        src_layout.addWidget(self.output_query_btn, 2, 4)

        right_panel.addWidget(src_group)

        # 连接信号槽（使用textChanged而不是textEdited以获得实时响应）
        self.power_input.textChanged.connect(self.on_power_input_changed)
        self.raw_power_input.textChanged.connect(self.on_raw_power_input_changed)

        # 添加输入验证器
        self.power_validator = QRegExpValidator(QRegExp(r"^-?\d+\.?\d*\s*(dBm)?$"), self.power_input)
        self.raw_power_validator = QRegExpValidator(QRegExp(r"^-?\d+\.?\d*\s*(dBm)?$"), self.raw_power_input)
        self.power_input.setValidator(self.power_validator)
        self.raw_power_input.setValidator(self.raw_power_validator)

        # 运动控制
        self.motion_group = QGroupBox("运动控制")
        motion_layout = QGridLayout()
        self.motion_group.setLayout(motion_layout)
        motion_layout.addWidget(QLabel("复位:"), 0, 0)
        self.home_combo = QComboBox()
        self.home_combo.addItems(["X", "KU", "K", "KA", "ALL"])
        motion_layout.addWidget(self.home_combo, 0, 1)
        self.home_btn = QPushButton("执行复位")
        self.home_btn.clicked.connect(self.send_home_cmd)
        motion_layout.addWidget(self.home_btn, 0, 2)
        self.home_query_btn = QPushButton("查询复位")
        self.home_query_btn.clicked.connect(self.query_home_cmd)
        motion_layout.addWidget(self.home_query_btn, 0, 3)
        motion_layout.addWidget(QLabel("达位:"), 1, 0)
        self.feed_combo = QComboBox()
        self.feed_combo.addItems(["X", "KU", "K", "KA"])
        motion_layout.addWidget(self.feed_combo, 1, 1)
        self.feed_btn = QPushButton("执行达位")
        self.feed_btn.clicked.connect(self.send_feed_cmd)
        motion_layout.addWidget(self.feed_btn, 1, 2)
        self.feed_query_btn = QPushButton("查询达位")
        self.feed_query_btn.clicked.connect(self.query_feed_cmd)
        motion_layout.addWidget(self.feed_query_btn, 1, 3)
        motion_layout.addWidget(QLabel("速度:"), 2, 0)
        # 交换顺序：先模组名称，再挡位
        self.speed_mod_combo = QComboBox()
        self.speed_mod_combo.addItems(["X", "KU", "K", "KA","Z"])
        motion_layout.addWidget(self.speed_mod_combo, 2, 1)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["LOW", "MID1", "MID2", "MID3", "HIGH"])
        motion_layout.addWidget(self.speed_combo, 2, 2)
        self.speed_btn = QPushButton("设置速度")
        self.speed_btn.clicked.connect(self.send_speed_cmd)
        motion_layout.addWidget(self.speed_btn, 2, 3)
        self.speed_query_btn = QPushButton("查询速度")
        self.speed_query_btn.clicked.connect(self.query_speed_cmd)
        motion_layout.addWidget(self.speed_query_btn, 2, 4)
        right_panel.addWidget(self.motion_group)

        main_layout.addLayout(right_panel, stretch=3)

        # # --- 标题 ---
        # title = QLabel("RNX量子天线测试系统控制Demo", self)
        # title.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        # title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 用一个总的垂直布局包裹标题和主布局
        layout = QVBoxLayout()
        # layout.addWidget(title)
        layout.addLayout(main_layout)
        self.central_widget.setLayout(layout)  # ← 这里设置布局

        # 状态栏初始信息
        self.show_status("系统就绪。")
        self.log("系统启动。", "INFO")

    # --- 日志方法 ---
    def log(self, message, level="INFO"):
        self.log_output.log(message, level)

    # --- 链路映射 ---
    def parse_link_response(self, response):
        """解析链路查询结果"""
        link_mapping = {
            "LF_PORT1,RF_COM": "FEED_X_THETA",
            "LF_PORT2,RF_COM": "FEED_X_PHI",
            "LF_PORT3,RF_COM": "FEED_KU_THETA",
            "LF_PORT4,RF_COM": "FEED_KU_PHI",
            "HF_PORT1,RF_COM": "FEED_K_THETA",
            "HF_PORT2,RF_COM": "FEED_K_PHI",
            "HF_PORT3,RF_COM": "FEED_KA_THETA",
            "HF_PORT4,RF_COM": "FEED_KA_PHI"
        }
        return link_mapping.get(response.strip(), "FEED_X_THETA")  # 默认返回X_THETA
    


    # --- ETH连接 ---
    def connect_eth(self):
        ip = self.eth_ip_input.text().strip()
        port = self.eth_port_input.text().strip()
        # 如果未输入，则用PlaceholderText
        if not ip:
            ip = self.eth_ip_input.placeholderText()
        if not port:
            port = self.eth_port_input.placeholderText()
        self.show_status(f"正在连接：IP={ip}，Port={port}")
        self.log(f"尝试连接到 IP={ip}，Port={port}", "INFO")
        success, message = self.tcp_client.connect(ip, port)
        self.show_status(message)
        if success:
            self.log(f"已连接到 {ip}:{port}", "SUCCESS")
            # 启动状态线程
            if self.status_thread:
                self.status_thread.stop()
            self.status_thread = StatusQueryThread(ip, port, self.comm_mutex)
            self.status_thread.status_signal.connect(self.update_status_panel)
            self.status_thread.start()
            # 连接成功后自动查询一次链路状态
            self.query_link_cmd()

            # 连接成功后，自动进入频率联动模式
            self.freq_feed_link_check.setChecked(True)
            
            # 添加连接成功的视觉反馈
            self.eth_ip_input.setStyleSheet("border: 2px solid #4CAF50;")  # 绿色边框表示连接成功
            self.eth_port_input.setStyleSheet("border: 2px solid #4CAF50;")
            self.eth_connect_btn.setStyleSheet("background: #4CAF50; color: white;")  # 绿色按钮表示已连接
        else:
            self.log(f"连接失败: {message}", "ERROR")
            # 连接失败的视觉反馈
            self.eth_ip_input.setStyleSheet("border: 2px solid #F44336;")  # 红色边框表示连接失败
            self.eth_port_input.setStyleSheet("border: 2px solid #F44336;")
            self.eth_connect_btn.setStyleSheet("background: #F44336; color: white;")  # 红色按钮表示连接失败

    def disconnect_eth(self):
        if self.tcp_client.connected:
            self.tcp_client.close()
            self.show_status("已断开连接。")
            self.log("已断开连接。", "INFO")
            # 停止状态线程
            if self.status_thread:
                self.status_thread.stop()
                self.status_thread.wait()
                self.status_thread = None
                
            # 添加断开连接的视觉反馈
            self.eth_ip_input.setStyleSheet("")  # 恢复默认样式
            self.eth_port_input.setStyleSheet("")
            self.eth_connect_btn.setStyleSheet("")  # 恢复默认按钮样式
        else:
            self.show_status("未连接到设备。")
            self.log("未连接到设备。", "WARNING")


    def _on_freq_link_state_changed(self, state):
        """处理频率联动复选框状态变化"""
        if state == Qt.Checked and not self._is_freq_link_connected:
            # 启用联动
            self.link_mode_combo.currentTextChanged.connect(self._update_feed_for_freq)
            self._is_freq_link_connected = True
            self.log("频率与馈源联动已启用", "WARNING")
            
            # 禁用运动控制区域
            self.motion_group.setTitle("运动控制 (频率联动模式下禁用)")
            self.motion_group.setEnabled(False)  # 这会自动禁用所有子控件
            
        elif state != Qt.Checked and self._is_freq_link_connected:
            # 禁用联动
            try:
                self.link_mode_combo.currentTextChanged.disconnect(self._update_feed_for_freq)
            except TypeError:
                pass
            self._is_freq_link_connected = False
            self.log("频率与馈源联动已禁用", "WARNING")
            
            # 启用运动控制区域
            self.motion_group.setTitle("运动控制")
            self.motion_group.setEnabled(True)  # 这会自动启用所有子控件
    
    def _update_feed_for_freq(self, mode):
        """根据频率更新馈源设置"""
        if not self.tcp_client.connected:
            return
        
        # 解析频率范围
        freq_ranges = {
            "FEED_X_THETA": (8.0, 12.0),
            "FEED_X_PHI": (8.0, 12.0),
            "FEED_KU_THETA": (12.0, 18.0),
            "FEED_KU_PHI": (12.0, 18.0),
            "FEED_K_THETA": (18.0, 26.5),
            "FEED_K_PHI": (18.0, 26.5),
            "FEED_KA_THETA": (26.5, 40.0),
            "FEED_KA_PHI": (26.5, 40.0)
        }
        
        if mode in freq_ranges:
            self.current_feed_mode = mode
            min_freq, max_freq = freq_ranges[mode]
            center_freq = (min_freq + max_freq) / 2
            self.freq_input.setText(f"{center_freq:.3f}GHz")
            self.send_freq_cmd()
            self.log(f"频率联动: 自动设置为{center_freq}GHz ({mode})", "INFO")


    def is_valid_frequency(self, freq_str):
        """验证频率值是否有效"""
        if not freq_str or freq_str == "-":
            return False
        try:
            float(freq_str.replace("GHz", "").strip())
            return True
        except ValueError:
            return False

    def is_valid_power(self, text):
        """验证功率输入是否有效"""
        if not text.strip():
            return False
        try:
            float(text.replace("dBm", "").strip())
            return True
        except ValueError:
            return False

    def should_process_input(self, text):
        """判断是否应该处理输入"""
        text = text.strip()
        
        # 条件1: 长度不超过2时不处理
        if len(text) <= 2:
            return False
        
        # 条件2: 如果最后输入的是符号(+/-)不处理
        if text[-1] in ('+', '-'):
            return False
        
        # 条件3: 检查是否为有效数字格式
        try:
            # 临时移除单位检查纯数字有效性
            num_part = text.replace("dBm", "").strip()
            if not num_part:  # 空字符串
                return False
            float(num_part)
            return True
        except ValueError:
            return False

    def on_power_input_changed(self, text):
        """补偿后功率输入框变化时的处理"""
        if not self.is_valid_power(text):
            return
        
        if not self.should_process_input(text):
            return
        
        # 防止递归触发
        if self.raw_power_input.signalsBlocked():
            return
        
        try:
            power_dbm = float(text.replace("dBm", "").strip())
            
            # 获取当前频率
            freq_str = self.status_cache["src"].get("freq", "0")
            if not self.is_valid_frequency(freq_str):
                self.show_status("当前频率无效，无法计算补偿", timeout=3000)
                return
                
            freq_ghz = float(freq_str.replace("GHz", "").strip()) if "GHz" in freq_str else float(freq_str)/1e9
            
            # 计算补偿值
            compensation = self.get_compensation_value(freq_ghz) if self.compensation_enabled else 0.0
            raw_power = power_dbm - compensation
            
            # 更新原始功率输入框（不触发信号）
            self.raw_power_input.blockSignals(True)
            self.raw_power_input.setText(f"{raw_power:.2f} dBm")
            self.raw_power_input.blockSignals(False)
            
        except ValueError as e:
            self.log(f"功率转换错误: {str(e)}", "WARNING")

    def on_raw_power_input_changed(self, text):
        """原始功率输入框变化时的处理"""
        if not self.is_valid_power(text):
            return
    
        if not self.should_process_input(text):
            return
        
        # 防止递归触发
        if self.power_input.signalsBlocked():
            return
        
        try:
            raw_power = float(text.replace("dBm", "").strip())
            
            # 获取当前频率
            freq_str = self.status_cache["src"].get("freq", "0")
            if not self.is_valid_frequency(freq_str):
                self.show_status("当前频率无效，无法计算补偿", timeout=3000)
                return
                
            freq_ghz = float(freq_str.replace("GHz", "").strip()) if "GHz" in freq_str else float(freq_str)/1e9
            
            # 计算补偿值
            compensation = self.get_compensation_value(freq_ghz) if self.compensation_enabled else 0.0
            power_dbm = raw_power + compensation
            
            # 更新补偿后功率输入框（不触发信号）
            self.power_input.blockSignals(True)
            self.power_input.setText(f"{power_dbm:.2f} dBm")
            self.power_input.blockSignals(False)
            
        except ValueError as e:
            self.log(f"原始功率转换错误: {str(e)}", "WARNING")

    def load_calibration_file(self, filepath: str):
        """加载校准文件"""
        from PyQt5.QtWidgets import QFileDialog
    
        # 确保cal_manager已初始化
        if self.cal_manager is None:
            self.cal_manager = CalibrationFileManager(log_callback=self.log)
    
        # 获取最近校准文件目录
        cal_dir = "calibrations"  # 默认目录
        if hasattr(self, 'cal_manager'):
            cal_dir = self.cal_manager.base_dir
        
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择校准文件", 
            cal_dir, 
            "校准文件 (*.csv *.bin);;所有文件 (*)"
        )
    
        if file_path:
            self.status_panel.cal_file_input.setText(file_path)
            self.log(f"已选择校准文件: {file_path}", "INFO")
    
            # 使用CalibrationFileManager加载文件
            result = self.cal_manager.load_calibration_file(file_path)
    
            # 打印文件内容验证（不重新加载文件）
            self._print_cal_file_contents(file_path, loaded_data=result)
    
            if result:
                self.calibration_data = result['data']
                self.compensation_enabled = True
                self.status_panel.cal_file_status.setText("Calib Load")
                self.status_panel.cal_file_status.setStyleSheet(
                    "background:#b6f5c6; color:#0078d7;"
                )
                self.log("校准文件加载成功，补偿功能已启用", "SUCCESS")
            else:
                self.compensation_enabled = False
                self.status_panel.cal_file_status.setText("Calib Invalid")
                self.status_panel.cal_file_status.setStyleSheet(
                    "background:#ffcdd2; color:#d32f2f;"
                )
                self.log("校准文件加载失败", "ERROR")

    def _print_cal_file_contents(self, filepath: str, loaded_data=None):
        """打印校准文件内容用于验证数据正确性"""
        # 直接使用已加载的数据或self.cal_manager中的数据
        if loaded_data is not None:
            meta = loaded_data.get('meta', {})
            data_points = loaded_data.get('data', [])
        elif hasattr(self, 'cal_manager') and self.cal_manager:
            meta = self.cal_manager.current_meta
            data_points = self.cal_manager.data_points
        else:
            self.log("校准管理器未初始化", "ERROR")
            return
        
        # 显示文件格式信息
        self.log("\n=== 文件信息 ===", "INFO")
        try:
            file_size = os.path.getsize(filepath)
            self.log(f"文件大小: {file_size/1024:.2f} KB", "INFO")
            
            if filepath.lower().endswith('.bin'):
                self.log("文件格式: 二进制校准文件 (RNXC格式)", "INFO")
                self.log("数据编码: 每个数据点36字节(频率:4字节float + 8个参数:32字节)", "INFO")
            elif filepath.lower().endswith('.csv'):
                self.log("文件格式: CSV文本文件 (UTF-8编码)", "INFO")
                self.log("数据格式: 逗号分隔值,每行9个字段(频率+8个参数)", "INFO")
                
            # 显示文件完整路径
            self.log(f"文件路径: {os.path.abspath(filepath)}", "INFO")
        except Exception as e:
            self.log(f"获取文件信息失败: {str(e)}", "WARNING")
          
        self.log("\n=== 文件元数据 ===", "INFO")
        # 打印元数据
        if isinstance(meta, dict):
            self.log(f"创建时间: {meta.get('created', '未知')}", "INFO")
            self.log(f"操作员: {meta.get('operator', '未知')}", "INFO")
            if 'signal_gen' in meta:
                sg_info = meta['signal_gen']
                self.log(f"信号源: {sg_info[0]} (SN: {sg_info[1]})", "INFO")
            if 'spec_analyzer' in meta:
                sa_info = meta['spec_analyzer']
                self.log(f"频谱分析仪: {sa_info[0]} (SN: {sa_info[1]})", "INFO")
            if 'antenna' in meta:
                ant_info = meta['antenna']
                self.log(f"天线: {ant_info[0]} (SN: {ant_info[1]})", "INFO")
            if 'environment' in meta:
                env_info = meta['environment']
                self.log(f"环境: {env_info[0]}°C, {env_info[1]}%RH", "INFO")
            
            if 'freq_params' in meta:
                freq_params = meta['freq_params']
                self.log("\n=== 频率参数 ===", "INFO")
                self.log(f"起始频率: {freq_params.get('start_ghz', '未知')} GHz", "INFO")
                self.log(f"终止频率: {freq_params.get('stop_ghz', '未知')} GHz", "INFO")
                self.log(f"步进: {freq_params.get('step_ghz', '未知')} GHz", "INFO")
                self.log(f"点数: {meta.get('points', '未知')}", "INFO")
        
        # # 打印校准数据
        # self.log("\n=== 数据点示例 ===", "INFO")
        # if data_points:
        #     # 打印前5个点
        #     self.log("前5个数据点:", "INFO")
        #     for i, point in enumerate(data_points[:5]):
        #         self.log(
        #             f"点 {i}: 频率={point['freq']:.3f}GHz, "
        #             f"Xθ={point['x_theta']:.2f}, Xφ={point['x_phi']:.2f}, "
        #             f"KUθ={point['ku_theta']:.2f}, KUφ={point['ku_phi']:.2f}, "
        #             f"Kθ={point['k_theta']:.2f}, Kφ={point['k_phi']:.2f}, "
        #             f"KAθ={point['ka_theta']:.2f}, KAφ={point['ka_phi']:.2f}", 
        #             "INFO"
        #         )
            
        #     # 打印后5个点（如果存在）
        #     if len(data_points) > 5:
        #         self.log("\n最后5个数据点:", "INFO")
        #         for i, point in enumerate(data_points[-5:], len(data_points)-5):
        #             self.log(
        #                 f"点 {i}: 频率={point['freq']:.3f}GHz, "
        #                 f"Xθ={point['x_theta']:.2f}, Xφ={point['x_phi']:.2f}, "
        #                 f"KUθ={point['ku_theta']:.2f}, KUφ={point['ku_phi']:.2f}, "
        #                 f"Kθ={point['k_theta']:.2f}, Kφ={point['k_phi']:.2f}, "
        #                 f"KAθ={point['ka_theta']:.2f}, KAφ={point['ka_phi']:.2f}", 
        #                 "INFO"
        #             )
        
        self.log("\n=== 总结 ===", "INFO")
        self.log(f"总数据点数: {len(data_points)}", "INFO")
        if isinstance(meta, dict) and 'points' in meta:
            self.log(f"预期点数: {meta['points']}", "INFO")
            if len(data_points) == meta['points']:
                self.log("数据点数匹配", "SUCCESS")
            else:
                self.log("数据点数不匹配", "WARNING")
        
    def get_compensation_value(self, freq_ghz: float) -> float:
        """
        根据频率获取补偿值
        :param freq_ghz: 频率(GHz)
        :return: 补偿值(dB)
        """
        if not self.compensation_enabled or not self.calibration_data:
            return 0.0
        
        # 找到最接近的频率点
        closest_point = min(self.calibration_data,key=lambda x: abs(x['freq'] - freq_ghz))
        
        # 这里假设使用X_Theta的补偿值，可以根据实际需求修改
        return closest_point.get('x_theta', 0.0)

    # --- 指令组合与发送 ---
    def send_link_cmd(self):
        mode = self.link_mode_combo.currentText()
        cmd = f"CONFigure:LINK {mode}"
        self.link_diagram.set_link(mode)  # 动态刷新链路图
        self.send_and_log(cmd)

    # --- 链路查询 ---
    def query_link_cmd(self):
        cmd = "READ:LINK:STATe?"
        # 优先暂停状态线程，防止抢占
        if self.status_thread and self.status_thread.isRunning():
            self.status_thread._running = False
            self.status_thread.wait()
        
        self.comm_mutex.lock()
        try:
            self.log(cmd, "SEND")
            success, msg = self.tcp_client.send(cmd + '\n')
            if not success:
                self.log(f"发送失败: {msg}", "ERROR")
                self.show_status(msg)
                return
            
            success, resp = self.tcp_client.receive()
            if success:
                self.log(resp, "RECV")
                # 解析响应并更新链路图
                current_link = self.parse_link_response(resp)
                self.link_diagram.set_link(current_link)
                self.show_status(f"当前链路: {current_link}")
            else:
                self.log(f"接收失败: {resp}", "ERROR")
                self.show_status(resp)
        finally:
            self.comm_mutex.unlock()
            # 手动指令完成后重启状态线程
            if self.status_thread:
                self.status_thread._running = True
                self.status_thread.start()

    def send_freq_cmd(self):
        val = self.freq_input.text().strip()
        if not val:
            self.show_status("请输入频率参数")
            return
        cmd = f"SOURce:FREQuency {val}"
        self.send_and_log(cmd)

    def query_freq_cmd(self):
        cmd = "READ:SOURce:FREQuency?"
        self.send_and_log(cmd)

    def send_power_cmd(self):
        val = self.power_input.text().strip()
        if not val:
            self.show_status("请输入功率参数")
            return
        
        try:
            # 解析输入的功率值
            power_dbm = float(val.replace("dBm", "").strip())
            
            # 获取当前频率
            freq_str = self.status_cache["src"].get("freq", "0")
            freq_ghz = float(freq_str.replace("GHz", "").strip()) if "GHz" in freq_str else float(freq_str)/1e9
            
            # 计算补偿值
            compensation = self.get_compensation_value(freq_ghz) if self.compensation_enabled else 0.0
            compensated_power = power_dbm - compensation
            
            # 存储原始功率值
            self.current_power = power_dbm
            
            cmd = f"SOURce:POWer {compensated_power:.2f}"
            self.send_and_log(cmd)
            
            self.log(f"功率补偿: 设置值={power_dbm:.2f}dBm, 补偿值={compensation:.2f}dB, 实际设置={compensated_power:.2f}dBm", "INFO")
        except ValueError:
            self.show_status("无效的功率参数")
            self.log("无效的功率参数", "ERROR")

    def query_power_cmd(self):
        cmd = "READ:SOURce:POWer?"
        if self.compensation_enabled:
            # 优先暂停状态线程，防止抢占
            if self.status_thread and self.status_thread.isRunning():
                self.status_thread._running = False
                self.status_thread.wait()
            
            self.comm_mutex.lock()
            try:
                self.log(cmd, "SEND")
                success, msg = self.tcp_client.send(cmd + '\n')
                if not success:
                    self.log(f"发送失败: {msg}", "ERROR")
                    self.show_status(msg)
                    return
                
                success, resp = self.tcp_client.receive()
                if success:
                    try:
                        # 解析查询到的功率值
                        measured_power = float(resp.replace("dBm", "").strip())
                        
                        # 获取当前频率
                        freq_str = self.status_cache["src"].get("freq", "0")
                        freq_ghz = float(freq_str.replace("GHz", "").strip()) if "GHz" in freq_str else float(freq_str)/1e9
                        
                        # 计算补偿值
                        compensation = self.get_compensation_value(freq_ghz)
                        actual_power = measured_power + compensation
                        
                        self.log(f"{resp} (补偿后: {actual_power:.2f}dBm)", "RECV")
                        self.show_status(f"查询功率: {actual_power:.2f}dBm (补偿值: {compensation:.2f}dB)")
                    except ValueError:
                        self.log(resp, "RECV")
                        self.show_status("查询功率")
                else:
                    self.log(f"接收失败: {resp}", "ERROR")
                    self.show_status(resp)
            finally:
                self.comm_mutex.unlock()
                # 手动指令完成后重启状态线程
                if self.status_thread:
                    self.status_thread._running = True
                    self.status_thread.start()
        else:
            self.send_and_log(cmd)

    def send_output_cmd(self):
        val = self.output_combo.currentText()
        cmd = f"SOURce:OUTPut {val}"
        self.send_and_log(cmd)

    def query_output_cmd(self):
        cmd = "READ:SOURce:OUTPut?"
        self.send_and_log(cmd)

    def send_home_cmd(self):
        val = self.home_combo.currentText()
        cmd = f"MOTion:HOME {val}"
        # 设置操作状态
        if self.status_thread:
            self.status_thread.current_operation = "HOMING"
            self.status_thread.operating_axis = val
        self.send_and_log(cmd)

    def query_home_cmd(self):
        val = self.home_combo.currentText()
        cmd = f"READ:MOTion:HOME? {val}"
        self.send_and_log(cmd)

    def send_feed_cmd(self):
        val = self.feed_combo.currentText()
        cmd = f"MOTion:FEED {val}"
        # 设置操作状态
        if self.status_thread:
            self.status_thread.current_operation = "FEEDING"
            self.status_thread.operating_axis = val
        self.send_and_log(cmd)

    def query_feed_cmd(self):
        val = self.feed_combo.currentText()
        cmd = f"READ:MOTion:FEED? {val}"
        self.send_and_log(cmd)

    def send_speed_cmd(self):
        mod = self.speed_mod_combo.currentText()
        speed = self.speed_combo.currentText()
        cmd = f"MOTion:SPEED {mod},{speed}"
        self.send_and_log(cmd)

    def query_speed_cmd(self):
        mod = self.speed_mod_combo.currentText()
        cmd = f"READ:MOTion:SPEED? {mod}"
        self.send_and_log(cmd)

    def send_and_log(self, cmd):
        # 优先暂停状态线程，防止抢占
        if self.status_thread and self.status_thread.isRunning():
            self.status_thread._running = False
            self.status_thread.wait()
        self.comm_mutex.lock()
        try:
            self.log(cmd, "SEND")
            # 判断是否为无返回值指令
            if cmd.strip().upper().startswith("CONFIGURE:LINK") or cmd.strip().upper().startswith("CONFIG:LINK"):
                success, msg = self.tcp_client.send(cmd + '\n')
                if success:
                    self.show_status("链路设置指令已发送。")
                else:
                    self.log(f"发送失败: {msg}", "ERROR")
                    self.show_status(msg)
                return
            # 其它指令正常收发
            success, msg = self.tcp_client.send(cmd + '\n')
            if not success:
                self.log(f"发送失败: {msg}", "ERROR")
                self.show_status(msg)
                return
            success, resp = self.tcp_client.receive()
            
            if success:
                self.log(resp, "RECV")
                self.show_status("指令已发送。")
            else:
                self.log(f"接收失败: {resp}", "ERROR")
                self.show_status(resp)
        finally:
            self.comm_mutex.unlock()
            # 手动指令完成后重启状态线程
            if self.status_thread:
                self.status_thread._running = True
                self.status_thread.start()

    def show_status(self, message):
        self.status_bar.showMessage(message)

    def update_status_panel(self, status):
        """Main method to update the status panel"""
        self._update_status_cache(status)
        self._refresh_motion_display()
        self._refresh_source_display()

    def _update_status_cache(self, status):
        """Update the internal status cache"""
        # Update motion status
        axes = ["X", "KU", "K", "KA", "Z"]
        for axis in axes:
            if axis in status.get("motion", {}):
                for key in ["reach", "home", "speed"]:
                    val = status["motion"][axis].get(key)
                    if val is not None:
                        self.status_cache["motion"][axis][key] = val
        
        # Update source status
        for key in ["freq", "power", "rf"]:
            val = status.get("src", {}).get(key)
            if val is not None:
                self.status_cache["src"][key] = val

    def _refresh_motion_display(self):
        """Refresh all motion-related UI elements"""
        axes = ["X", "KU", "K", "KA", "Z"]
        
        for axis in axes:
            axis_status = self.status_cache["motion"][axis]
            
            # Update reach status
            reach_text = "NO Pa" if axis == "Z" else axis_status.get("reach", "-")
            self._update_status_label(
                self.status_panel.motion_reach[axis],
                reach_text
            )
            
            # Update home status
            self._update_status_label(
                self.status_panel.motion_home[axis],
                axis_status.get("home", "-")
            )
            
            # Update speed status with special coloring
            speed_text = axis_status.get("speed", "-")
            self.status_panel.motion_speed[axis].setText(speed_text)
            self._set_speed_background(axis, speed_text)
        
        # Update operation status
        self._update_operation_status()

    def _refresh_source_display(self):
        """Refresh source display with precise 9-character formatting"""
        src = self.status_cache["src"]
        
        # Frequency display (9 chars)
        freq_text = self._format_quantity(src.get("freq", "-"), "frequency")
        self._update_status_label(self.status_panel.src_freq, freq_text)
        
        # Raw power display (9 chars)
        raw_power_text = self._format_quantity(
            src.get("power", "-"), 
            "power",
            target_widget="src_raw_power"
        )
        self._update_status_label(self.status_panel.src_raw_power, raw_power_text)
        
        # Feed power display with compensation (9 chars)
        feed_power_text = self._format_quantity(
            src.get("power", "-"), 
            "power",
            target_widget="src_power"
        )
        
        if feed_power_text != "-" and self.compensation_enabled:
            try:
                # Extract numeric value (handling different unit formats)
                parts = feed_power_text.split()
                if len(parts) == 2:
                    power_value = float(parts[0])
                    unit = parts[1]
                else:  # Handle cases like "123.45dBm"
                    for i, c in enumerate(feed_power_text):
                        if c.isalpha():
                            power_value = float(feed_power_text[:i])
                            unit = feed_power_text[i:]
                            break
                
                # Apply compensation
                freq_str = src.get("freq", "0")
                freq_ghz = float(freq_str.replace("GHz", "").strip()) if "GHz" in freq_str else float(freq_str)/1e9
                compensation = self.get_compensation_value(freq_ghz)
                actual_power = power_value + compensation
                
                # Reformat with same unit (ensure 9 chars)
                if unit in ["dBμV/m", "dBuV/m"]:
                    feed_power_text = f"{actual_power:>6.2f}{unit}"
                elif unit == "dBm":
                    feed_power_text = f"{actual_power:>6.3f} {unit}"
                else:
                    feed_power_text = f"{actual_power:>6.4f}{unit}"
                    
            except (ValueError, IndexError):
                pass
        
        self._update_status_label(self.status_panel.src_power, feed_power_text)
        
        # RF status (fixed width)
        rf_status = src.get("rf", "-")
        self._update_status_label(
            self.status_panel.src_rf, 
            rf_status,
            custom_style="ON" if rf_status.strip().upper() == "ON" else None
        )
        
        # Update unit colors
        self._update_unit_combo_colors()



    def _update_operation_status(self):
        """Update the current operation status display"""
        if self.status_thread and self.status_thread.current_operation:
            operation = self.status_thread.current_operation
            axis = self.status_thread.operating_axis
            
            label = self.status_panel.motion_label
            if operation == "HOMING":
                label.setText(f"{axis}轴复位中...")
                label.setStyleSheet("color: #ff8f00;")
            elif operation == "FEEDING":
                label.setText(f"{axis}轴达位中...")
                label.setStyleSheet("color: #ff8f00;")
            
            # Check if operation completed
            axis_status = self.status_cache["motion"].get(axis, {})
            if (operation == "HOMING" and "OK" in axis_status.get("home", "")) or \
            (operation == "FEEDING" and "OK" in axis_status.get("reach", "")):
                self.status_thread.current_operation = None
                self.status_thread.operating_axis = None
                label.setText("运动状态: 就绪")
                label.setStyleSheet("color: #228B22;")
        else:
            self.status_panel.motion_label.setText("运动状态: 就绪")
            self.status_panel.motion_label.setStyleSheet("color: #228B22;")

    def _update_status_label(self, label, text, custom_style=None):
        """Update status label with fixed-width formatting"""
        # Ensure text is exactly 9 characters wide
        display_text = str(text).strip()
        label.setText(display_text)
        
        # Set font to monospace for perfect alignment
        # font = QFont("Courier New", 24)  # Monospaced font
        # font.setBold(True)
        # label.setFont(font)
        
        # Apply styling
        if custom_style == "ON":
            label.setStyleSheet(
                "background:#b6f5c6; color:#0078d7; border:2px solid #0078d7; border-radius:8px;"
            )
        else:
            self._set_status_color(label, display_text)


    def _set_status_color(self, label, text):
        """Set the color scheme based on status text"""
        if any(x in text.upper() for x in ["NO", "FAIL"]):
            style = "background:#fff9c4; color:#0078d7; border:2px solid #0078d7; border-radius:8px;"
        elif any(x in text.upper() for x in ["OK", "PASS"]):
            style = "background:#b6f5c6; color:#0078d7; border:2px solid #0078d7; border-radius:8px;"
        elif any(x in text for x in ["超时", "timeout", "连接失败"]):
            style = "background:#ffcdd2; color:#d32f2f; border:2px solid #0078d7; border-radius:8px;"
        else:
            style = "background:#f5faff; color:#0078d7; border:2px solid #0078d7; border-radius:8px;"
        
        label.setStyleSheet(style)

    def _update_unit_combo_colors(self):
        """Update the colors of unit combo boxes based on current selection"""
        # Power unit combo
        power_unit = self.status_panel.power_unit_combo.currentText()
        power_color = self.status_panel.unit_converter.get_power_unit_color(power_unit)
        self.status_panel.power_unit_combo.setStyleSheet(
            f"background: {power_color}; color: white;"
        )
        
        # Raw power unit combo
        raw_power_unit = self.status_panel.raw_power_unit_combo.currentText()
        raw_power_color = self.status_panel.unit_converter.get_power_unit_color(raw_power_unit)
        self.status_panel.raw_power_unit_combo.setStyleSheet(
            f"background: {raw_power_color}; color: white;"
        )
        
        # Frequency unit combo (optional)
        freq_color = "#0078d7"  # Default blue
        self.status_panel.freq_unit_combo.setStyleSheet(
            f"background: {freq_color}; color: white;"
        )


    def _set_speed_background(self, axis, speed_text):
        """Set the background color for speed labels"""
        speed_color = {
            "LOW": "#ffe082",
            "MID1": "#ffd54f",
            "MID2": "#ffb300",
            "MID3": "#ff8f00",
            "HIGH": "#ff6f00"
        }
        bg = speed_color.get(speed_text.upper(), "#f5faff")
        self.status_panel.motion_speed[axis].setStyleSheet(
            f"background:{bg}; color:#0078d7; border:2px solid #0078d7; border-radius:8px;"
        )


    def _format_quantity(self, value, quantity_type, target_widget=None):
        """Format numeric values with optimal precision for different unit types
        - Uses scientific notation for very large/small values
        - Maintains unit-specific formatting
        - Handles all defined unit types (frequency, power, E-field)
        - Special formatting for dB units
        """
        
        if value == "-" or value is None:
            return "-"
        
        try:
            # Convert to float first to handle string inputs
            num = float(str(value).strip())
            
            if quantity_type == "frequency":
                current_unit = self.status_panel.freq_unit_combo.currentText()
                converted_value, unit = self.status_panel.unit_converter.convert_frequency(
                    num, "Hz", current_unit
                )
                
                # Frequency formatting rules
                if unit == "GHz":
                    if abs(converted_value) >= 1000:
                        return f"{converted_value:.6e} {unit}".replace('e+0', 'e+')
                    return f"{converted_value:.6f} {unit}"
                elif unit == "MHz":
                    return f"{converted_value:.3f} {unit}"
                elif unit == "kHz":
                    return f"{converted_value:.1f} {unit}"
                else:  # Hz
                    return f"{int(converted_value)} {unit}"
                    
            elif quantity_type == "power":
                if target_widget == "src_power":
                    current_unit = self.status_panel.power_unit_combo.currentText()
                else:
                    current_unit = self.status_panel.raw_power_unit_combo.currentText()
                
                # Handle E-field units (1m distance assumed)
                if current_unit in self.status_panel.unit_converter.E_FIELD_UNITS:
                    converted_value, unit = self.status_panel.unit_converter.power_density_to_efield(num, "dBm")
                    converted_value, unit = self.status_panel.unit_converter.convert_efield(converted_value, "V/m", current_unit)
                    
                    # E-field formatting
                    if unit in ["dBμV/m", "dBuV/m"]:
                        return f"{converted_value:.2f}{unit}"
                    elif unit == "V/m":
                        return f"{converted_value:.6f} {unit}"
                    else:  # mV/m, µV/m
                        return f"{converted_value:.3f} {unit}"
                        
                else:  # Regular power units
                    converted_value, unit = self.status_panel.unit_converter.convert_power(num, "dBm", current_unit)
                    
                    # Power unit formatting
                    if unit in ["dBm", "dBW"]:
                        return f"{converted_value:.2f} {unit}"
                    elif unit == "W":
                        if abs(converted_value) >= 1000 or abs(converted_value) < 0.001:
                            return f"{converted_value:.6e} {unit}".replace('e+0', 'e+')
                        return f"{converted_value:.6f} {unit}"
                    else:  # mW, µW, nW
                        if abs(converted_value) >= 1e6 or abs(converted_value) < 0.001:
                            return f"{converted_value:.6e}{unit}".replace('e+0', 'e+')
                        return f"{converted_value:.3f}{unit}"

        except (ValueError, TypeError):
            return str(value)
        
        return str(value)

class CalibrationFileManager:
    """
    校准文件全生命周期管理类
    功能涵盖：创建、写入、验证、版本控制、自动归档、数据完整性检查
    """
    
    def __init__(self, base_dir: str = "calibrations", log_callback: Optional[callable] = None):
        """
        初始化校准文件管理器
        
        :param base_dir: 校准文件存储根目录
        :param log_callback: 日志回调函数，格式为 func(msg: str, level: str)
        """
        self.base_dir = os.path.abspath(base_dir)
        self.active_file: Optional[str] = None
        self.current_meta: Dict = {}
        self.data_points: List = []
        self._file_lock = threading.Lock()
        
        os.makedirs(self.base_dir, exist_ok=True)
        
        # 初始化日志系统
        self.log = log_callback if callable(log_callback) else self._default_logger
        
        # 创建必要的子目录
        for subdir in ["archive", "backup"]:
            os.makedirs(os.path.join(self.base_dir, subdir), exist_ok=True)

    def _default_logger(self, msg: str, level: str = "INFO"):
        """默认日志记录器"""
        print(f"[CAL {level}] {msg}")

    def _generate_bin_filename(self, csv_path: str) -> str:
        """根据CSV路径生成对应的BIN文件名"""
        base, ext = os.path.splitext(csv_path)
        return base + ".bin"
    
    def _write_bin_file(self, csv_path: str):
        """将CSV数据写入BIN文件"""
        bin_path = self._generate_bin_filename(csv_path)
        
        # 二进制文件结构：
        # 头部: 4字节幻数(0x524E5843 'RNXC') + 1字节版本(1)
        # 元数据: JSON格式的字符串(UTF-8编码)
        # 数据: 每个数据点9个float32(频率 + 8个参数)
        
        try:
            with open(bin_path, 'wb') as f:
                # 写入头部
                f.write(b'RNXC')  # 幻数
                f.write(bytes([1]))  # 版本号
                
                # 写入元数据
                meta_json = json.dumps(self.current_meta).encode('utf-8')
                f.write(len(meta_json).to_bytes(4, 'little'))  # 元数据长度
                f.write(meta_json)  # 元数据内容
                
                # 写入数据点
                for point in self._data_points:
                    freq = point['freq']
                    data = [
                        point['x_theta'], point['x_phi'],
                        point['ku_theta'], point['ku_phi'],
                        point['k_theta'], point['k_phi'],
                        point['ka_theta'], point['ka_phi']
                    ]
                    # 写入频率(1个float32)和8个参数(8个float32)
                    f.write(struct.pack('f', freq))
                    f.write(struct.pack('8f', *data))
                
            self.log(f"已生成二进制校准文件: {os.path.basename(bin_path)}", "INFO")
            return bin_path
        except Exception as e:
            self.log(f"生成二进制文件失败: {str(e)}", "ERROR")
            return None
        
    def generate_default_calibration(self, freq_range: Tuple[float, float] = (8.0, 40.0), 
                                step: float = 0.01) -> str:
        """
        生成默认校准文件（所有参数为0），确保包含边界频率
        
        :param freq_range: 频率范围(GHz) (start, stop)
        :param step: 频率步进(GHz)
        :return: 生成的校准文件路径
        """
        # 默认设备元数据
        default_meta = {
            'operator': 'SYSTEM',
            'signal_gen': ('DEFAULT_SG', 'SN00000'),
            'spec_analyzer': ('DEFAULT_SA', 'SN00000'),
            'antenna': ('DEFAULT_ANT', 'SN00000'),
            'environment': (25.0, 50.0)  # 25°C, 50%RH
        }
        
        # 确保stop频率不小于start频率
        start_ghz = min(freq_range)
        stop_ghz = max(freq_range)
        
        # 频率参数
        freq_params = {
            'start_ghz': start_ghz,
            'stop_ghz': stop_ghz,
            'step_ghz': step
        }
        
        # 创建新校准文件
        filepath = self.create_new_calibration(
            equipment_meta=default_meta,
            freq_params=freq_params,
            version_notes="系统生成的默认校准文件（所有参数为0）"
        )
        
        # 计算精确的点数，避免浮点误差
        num_points = int(round((stop_ghz - start_ghz) / step)) + 1
        
        # 填充0值数据，确保包含边界频率
        for i in range(num_points):
            freq = start_ghz + i * step
            # 处理浮点精度问题，确保最后一个点是stop_ghz
            if i == num_points - 1:
                freq = stop_ghz
                
            zero_data = {
                'x_theta': 1.0, 'x_phi': 1.0,
                'ku_theta': 1.0, 'ku_phi': 1.0,
                'k_theta': 1.0, 'k_phi': 1.0,
                'ka_theta': 1.0, 'ka_phi': 1.0
            }
            self.add_data_point(round(freq, 6), zero_data)  # 保留6位小数避免浮点误差
        
        # 完成校准
        archived_path = self.finalize_calibration("系统自动生成的默认校准文件")
        
        return archived_path

    def create_new_calibration(self, 
                             equipment_meta: Dict, 
                             freq_params: Dict, 
                             version_notes: Optional[str] = None) -> str:
        """
        创建新校准文件
        
        :param equipment_meta: 设备元数据
        :param freq_params: 频率参数
        :param version_notes: 版本说明
        :return: 创建的校准文件路径
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
        
        # 计算总点数
        points = int((freq_params['stop_ghz'] - freq_params['start_ghz']) / freq_params['step_ghz']) + 1
        
        # 生成文件名
        filename = (
            f"RNX_Cal_DualPol_"
            f"{freq_params['start_ghz']}to{freq_params['stop_ghz']}GHz_"
            f"step{freq_params['step_ghz']}_{timestamp}.csv"
        )
        
        self.active_file = os.path.join(self.base_dir, filename)
        self.active_bin_file = self._generate_bin_filename(self.active_file)
        self.current_meta = {
            **equipment_meta,
            'freq_params': freq_params,
            'created': timestamp,
            'points': points,
            'version_notes': version_notes,
            'file_format': 'csv+bin'  # 标记文件格式
        }
        self._data_points = []  # 重置数据点
        
        # 写入文件头
        with self._file_lock, open(self.active_file, 'w', encoding='utf-8') as f:
            f.write(self._generate_header())
            if version_notes:
                f.write(f"!VersionNotes: {version_notes}\n")
        
        self.log(f"创建新校准文件: {filename}", "INFO")
        return self.active_file

    def _generate_header(self) -> str:
        """生成标准文件头"""
        meta = self.current_meta
        freq = meta['freq_params']
        
        header_lines = [
            "!RNX Dual-Polarized Feed Calibration Data",
            f"!Created: {meta['created'].replace('_', 'T')}Z",
            f"!Operator: {meta['operator']}",
            "!Equipment:",
            f"!  Signal_Generator: {meta['signal_gen'][0]}_SN:{meta['signal_gen'][1]}",
            f"!  Spectrum_Analyzer: {meta['spec_analyzer'][0]}_SN:{meta['spec_analyzer'][1]}",
            f"!  Antenna: {meta['antenna'][0]}_SN:{meta['antenna'][1]}",
            f"!Environment: {meta['environment'][0]}C, {meta['environment'][1]}%RH",
            "!Frequency:",
            f"!  Start: {freq['start_ghz']} GHz",
            f"!  Stop: {freq['stop_ghz']} GHz",
            f"!  Step: {freq['step_ghz']} GHz",
            f"!  Points: {meta['points']}",
            "!Data Columns:",
            "!  1: Frequency(GHz)",
            "!  2: X_Theta(dB)",
            "!  3: X_Phi(dB)",
            "!  4: Ku_Theta(dB)",
            "!  5: Ku_Phi(dB)",
            "!  6: K_Theta(dB)",
            "!  7: K_Phi(dB)",
            "!  8: Ka_Theta(dB)",
            "!  9: Ka_Phi(dB)",
            "Frequency(GHz),X_Theta,X_Phi,Ku_Theta,Ku_Phi,K_Theta,K_Phi,Ka_Theta,Ka_Phi"
        ]
        return '\n'.join(header_lines) + '\n'

    def add_data_point(self, freq_ghz: float, data: Dict) -> bool:
        """
        添加单频点数据
        
        :param freq_ghz: 当前频率(GHz)
        :param data: 测量数据
        :return: 是否成功添加
        """
        if not self.active_file:
            raise RuntimeError("没有活动的校准文件")
        
        # 验证数据范围
        for key, value in data.items():
            if not isinstance(value, (int, float)):
                self.log(f"无效数据格式: {key}={value}", "ERROR")
                return False
            if not (-100 <= value <= 100):  # 假设合理范围是-100到100 dB
                self.log(f"数据超出范围: {key}={value}", "WARNING")
        
        # 存储数据点用于BIN文件
        self._data_points.append({
            'freq': freq_ghz,
            **data
        })
        
        # 格式化数据行
        data_row = (
            f"{freq_ghz:.3f},"
            f"{data.get('x_theta', -99.99):.2f},"
            f"{data.get('x_phi', -99.99):.2f},"
            f"{data.get('ku_theta', -99.99):.2f},"
            f"{data.get('ku_phi', -99.99):.2f},"
            f"{data.get('k_theta', -99.99):.2f},"
            f"{data.get('k_phi', -99.99):.2f},"
            f"{data.get('ka_theta', -99.99):.2f},"
            f"{data.get('ka_phi', -99.99):.2f}\n"
        )
        
        # 写入数据（线程安全）
        with self._file_lock, open(self.active_file, 'a', encoding='utf-8') as f:
            f.write(data_row)
        
        return True
    
    def finalize_calibration(self, notes: str = "") -> Tuple[str, str]:
        """
        完成校准并添加校验信息
        
        :param notes: 附加说明
        :return: (归档后的CSV文件路径, BIN文件路径)
        """
        if not self.active_file:
            raise RuntimeError("没有活动的校准文件")
        
        # 添加结束标记
        with self._file_lock, open(self.active_file, 'a', encoding='utf-8') as f:
            f.write(f"!EndOfData: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n")
            if notes:
                f.write(f"!Notes: {notes}\n")
        
        # 生成MD5校验
        file_hash = self._calculate_file_hash()
        with open(self.active_file, 'a', encoding='utf-8') as f:
            f.write(f"!MD5: {file_hash}\n")
        
        # 生成BIN文件
        bin_path = self._write_bin_file(self.active_file)
        
        self.log(f"校准完成: {os.path.basename(self.active_file)}", "SUCCESS")
        
        # 归档文件
        archived_csv = self._archive_file()  # 归档CSV
        archived_bin = self._archive_file(bin_path) if bin_path else None  # 归档BIN
        
        self.active_file = None
        self.active_bin_file = None
        self.current_meta = {}
        self._data_points = []
        
        return archived_csv, archived_bin

    def load_calibration_file(self, filepath: str) -> Optional[Dict]:
        """
        加载校准文件(支持CSV和BIN格式)
        
        :param filepath: 文件路径
        :return: 包含元数据和数据的字典，None表示失败
        """
        if not os.path.exists(filepath):
            self.log(f"文件不存在: {filepath}", "ERROR")
            return None
        
        # 根据扩展名选择加载方式
        if filepath.lower().endswith('.bin'):
            return self._load_bin_file(filepath)
        else:
            return self._load_csv_file(filepath)
        
    def _load_bin_file(self, bin_path: str) -> Optional[Dict]:
        """
        加载BIN格式校准文件
        1. 先验证文件有效性
        2. 再读取文件内容
        """
        # 先验证文件
        if not self._validate_bin_file(bin_path):
            self.log(f"BIN文件验证失败: {bin_path}", "ERROR")
            return None
        
        # 验证通过后读取内容
        return self._read_bin_content(bin_path)

    def _validate_bin_file(self, filepath: str) -> bool:
        """
        验证BIN格式校准文件结构是否有效
        不解析具体内容，只检查文件格式和完整性
        """
        try:
            with open(filepath, 'rb') as f:
                # 验证头部
                magic = f.read(4)
                if magic != b'RNXC':
                    self.log("无效的二进制文件格式", "WARNING")
                    return False
                
                version = ord(f.read(1))
                if version != 1:
                    self.log(f"不支持的版本号: {version}", "WARNING")
                    return False
                
                # 读取元数据长度
                meta_len = int.from_bytes(f.read(4), 'little')
                # 跳过元数据
                f.seek(meta_len, 1)
                
                # 检查数据点数量
                file_size = os.path.getsize(filepath)
                header_size = 4 + 1 + 4 + meta_len  # 幻数+版本+长度+元数据
                data_size = file_size - header_size
                
                if data_size % 36 != 0:  # 每个数据点36字节(4+32)
                    self.log("数据大小不匹配", "WARNING")
                    return False
                
                return True
                
        except Exception as e:
            self.log(f"验证二进制文件失败: {str(e)}", "ERROR")
            return False
        
    def _read_bin_content(self, bin_path: str) -> Optional[Dict]:
        """
        读取已验证的BIN文件内容
        假设文件已经通过验证，直接解析内容
        """
        try:
            with open(bin_path, 'rb') as f:
                # 跳过已验证的头部
                f.read(4)  # 幻数
                f.read(1)  # 版本
                meta_len = int.from_bytes(f.read(4), 'little')
                meta_json = f.read(meta_len).decode('utf-8')
                meta = json.loads(meta_json)
                
                # 读取数据点
                data_points = []
                while True:
                    freq_bytes = f.read(4)
                    if not freq_bytes:
                        break
                    
                    freq = struct.unpack('f', freq_bytes)[0]
                    data = struct.unpack('8f', f.read(32))  # 8个float32=32字节
                    
                    data_points.append({
                        'freq': freq,
                        'x_theta': data[0], 'x_phi': data[1],
                        'ku_theta': data[2], 'ku_phi': data[3],
                        'k_theta': data[4], 'k_phi': data[5],
                        'ka_theta': data[6], 'ka_phi': data[7]
                    })
                self.current_meta = meta
                self.data_points = data_points
                return {
                    'meta': meta,
                    'data': data_points
                }
        except Exception as e:
            self.log(f"读取二进制文件内容失败: {str(e)}", "ERROR")
            return None

    def _load_csv_file(self, csv_path: str) -> Optional[Dict]:
        """
        加载CSV格式校准文件
        1. 先验证文件有效性
        2. 再读取文件内容
        """
        # 先验证文件
        if not self._validate_csv_file(csv_path):
            self.log(f"CSV文件验证失败: {csv_path}", "ERROR")
            return None
        
        # 验证通过后读取内容
        return self._read_csv_content(csv_path)

    def _validate_csv_file(self, filepath: str) -> bool:
        """
        验证CSV格式校准文件结构是否有效
        不解析具体数据值，只检查文件结构和元数据
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 检查文件头
            if not lines or not lines[0].startswith("!RNX Dual-Polarized Feed Calibration Data"):
                self.log("无效的文件头", "WARNING")
                return False
                
            # 定义必需的头字段
            REQUIRED_HEADERS = {
                "!Created:", "!Operator:", "!  Signal_Generator:", 
                "!  Spectrum_Analyzer:", "!  Antenna:", "!Environment:",
                "!  Start:", "!  Stop:", "!  Step:", "!  Points:", "!Data Columns:"
            }
            
            # 检查所有必需字段是否存在
            header_lines = [line.strip() for line in lines if line.startswith("!")]
            missing_headers = [h for h in REQUIRED_HEADERS if not any(l.startswith(h) for l in header_lines)]
            
            if missing_headers:
                self.log(f"文件头缺少必需字段: {', '.join(missing_headers)}", "WARNING")
                return False
            
            # 检查数据部分标题行
            data_lines = [line for line in lines if not line.startswith("!") and line.strip()]
            if not data_lines or not data_lines[0].startswith("Frequency(GHz),"):
                self.log("缺少或无效的数据标题行", "WARNING")
                return False
                
            # 检查结束标记
            if not any(line.startswith("!EndOfData:") for line in lines[-3:]):
                self.log("缺少结束标记", "WARNING")
                return False
                
            if not any(line.startswith("!MD5:") for line in lines[-3:]):
                self.log("缺少MD5校验", "WARNING")
                return False
                
            return True
            
        except Exception as e:
            self.log(f"验证CSV文件失败: {str(e)}", "ERROR")
            return False

    def _read_csv_content(self, csv_path: str) -> Optional[Dict]:
        """
        读取已验证的CSV文件内容
        假设文件已经通过验证，直接解析内容
        
        返回包含完整元数据和数据点的字典:
        {
            'meta': {
                'file_format': str,
                'header': list,
                'created': str,
                'operator': str,
                'signal_gen': (model, sn),
                'spec_analyzer': (model, sn),
                'antenna': (model, sn),
                'environment': (temp, humidity),
                'freq_params': {
                    'start_ghz': float,
                    'stop_ghz': float,
                    'step_ghz': float
                },
                'points': int,
                'version_notes': str,
                'end_of_data': str,
                'md5': str
            },
            'data': list  # 数据点列表
        }
        """
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 初始化元数据字典
            meta = {
                'file_format': 'csv',
                'header': [],
                'signal_gen': ('未知', '未知'),
                'spec_analyzer': ('未知', '未知'),
                'antenna': ('未知', '未知'),
                'environment': (0.0, 0.0),
                'freq_params': {
                    'start_ghz': 0.0,
                    'stop_ghz': 0.0,
                    'step_ghz': 0.0
                }
            }
            
            data_start = 0
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('!'):
                    meta['header'].append(line)
                    
                    # 解析创建时间
                    if line.startswith('!Created:'):
                        meta['created'] = line.split(':', 1)[1].strip()
                    
                    # 解析操作员
                    elif line.startswith('!Operator:'):
                        meta['operator'] = line.split(':', 1)[1].strip()
                    
                    # 解析信号源信息
                    elif line.startswith('!  Signal_Generator:'):
                        parts = line.split('_SN:')
                        model = parts[0].split(':', 1)[1].strip()
                        sn = parts[1].strip() if len(parts) > 1 else '未知'
                        meta['signal_gen'] = (model, sn)
                    
                    # 解析频谱分析仪信息
                    elif line.startswith('!  Spectrum_Analyzer:'):
                        parts = line.split('_SN:')
                        model = parts[0].split(':', 1)[1].strip()
                        sn = parts[1].strip() if len(parts) > 1 else '未知'
                        meta['spec_analyzer'] = (model, sn)
                    
                    # 解析天线信息
                    elif line.startswith('!  Antenna:'):
                        parts = line.split('_SN:')
                        model = parts[0].split(':', 1)[1].strip()
                        sn = parts[1].strip() if len(parts) > 1 else '未知'
                        meta['antenna'] = (model, sn)
                    
                    # 解析环境信息
                    elif line.startswith('!Environment:'):
                        env_parts = line.split(':', 1)[1].strip().split(',')
                        temp = float(env_parts[0].replace('C', '').strip())
                        humidity = float(env_parts[1].replace('%RH', '').strip())
                        meta['environment'] = (temp, humidity)
                    
                    # 解析频率参数
                    elif line.startswith('!  Start:'):
                        meta['freq_params']['start_ghz'] = float(line.split(':', 1)[1].replace('GHz', '').strip())
                    elif line.startswith('!  Stop:'):
                        meta['freq_params']['stop_ghz'] = float(line.split(':', 1)[1].replace('GHz', '').strip())
                    elif line.startswith('!  Step:'):
                        meta['freq_params']['step_ghz'] = float(line.split(':', 1)[1].replace('GHz', '').strip())
                    elif line.startswith('!  Points:'):
                        meta['points'] = int(line.split(':', 1)[1].strip())
                    
                    # 解析版本说明
                    elif line.startswith('!VersionNotes:'):
                        meta['version_notes'] = line.split(':', 1)[1].strip()
                    
                    # 解析结束标记
                    elif line.startswith('!EndOfData:'):
                        meta['end_of_data'] = line.split(':', 1)[1].strip()
                    
                    # 解析MD5校验
                    elif line.startswith('!MD5:'):
                        meta['md5'] = line.split(':', 1)[1].strip()
                
                else:
                    data_start = i
                    break
            
            # 跳过标题行（第一个非注释行）
            data_lines = [line.strip() for line in lines[data_start:] if line.strip() and not line.startswith('!')]
            if not data_lines:
                self.log("没有有效数据行", "WARNING")
                return None
                
            # 确认标题行
            header_line = data_lines[0]
            if not header_line.startswith("Frequency(GHz),"):
                self.log(f"无效的数据标题行: {header_line}", "WARNING")
                return None
                
            # 处理数据行（跳过标题行）
            data_points = []
            for line in data_lines[1:]:
                if not line or line.startswith('!'):
                    continue
                    
                parts = line.split(',')
                if len(parts) != 9:
                    self.log(f"数据行格式错误，应有9列，实际{len(parts)}列: {line}", "WARNING")
                    continue
                
                try:
                    freq = float(parts[0])
                    # 验证频率值范围 (假设在0.1-100 GHz之间)
                    if not (0.1 <= freq <= 100.0):
                        self.log(f"频率值{freq}GHz超出有效范围(0.1-100GHz)", "WARNING")
                        continue
                    
                    # 验证补偿值范围 (假设在-100到100 dB之间)
                    compensation_values = []
                    for val in parts[1:9]:
                        try:
                            num = float(val)
                            if not (-100 <= num <= 100):
                                self.log(f"补偿值超出有效范围(-100-100dB): {val}", "WARNING")
                                break
                            compensation_values.append(num)
                        except ValueError:
                            self.log(f"无效数值格式: {val}", "WARNING")
                            break
                    
                    if len(compensation_values) != 8:
                        continue  # 跳过无效行
                        
                    data_points.append({
                        'freq': freq,
                        'x_theta': compensation_values[0],
                        'x_phi': compensation_values[1],
                        'ku_theta': compensation_values[2],
                        'ku_phi': compensation_values[3],
                        'k_theta': compensation_values[4],
                        'k_phi': compensation_values[5],
                        'ka_theta': compensation_values[6],
                        'ka_phi': compensation_values[7]
                    })
                except ValueError as e:
                    self.log(f"数据行解析失败: {line} - {str(e)}", "WARNING")
                    continue
            
            # 更新实例变量
            self.current_meta = meta
            self.data_points = data_points
            
            return {
                'meta': meta,
                'data': data_points
            }
            
        except Exception as e:
            self.log(f"读取CSV文件内容失败: {str(e)}", "ERROR")
            return None


    def _calculate_file_hash(self) -> str:
        """计算文件MD5校验值"""
        hash_md5 = hashlib.md5()
        with open(self.active_file, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _archive_file(self, filepath: Optional[str] = None) -> str:
        """将文件移动到归档目录
        :param filepath: 要归档的文件路径，如果为None则使用self.active_file
        :return: 归档后的文件路径
        """
        archive_dir = os.path.join(self.base_dir, "archive")
        os.makedirs(archive_dir, exist_ok=True)
        
        src = filepath if filepath is not None else self.active_file
        if src is None:
            raise ValueError("没有指定要归档的文件")
        
        filename = os.path.basename(src)
        dst = os.path.join(archive_dir, filename)
        
        shutil.move(src, dst)
        return dst

    def _backup_file(self) -> bool:
        """创建备份文件"""
        if not self.active_file:
            return False
            
        backup_dir = os.path.join(self.base_dir, "backup")
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(
            backup_dir, 
            f"backup_{os.path.basename(self.active_file)}_{timestamp}"
        )
        
        try:
            with self._file_lock:
                shutil.copy2(self.active_file, backup_file)
            self.log(f"创建备份: {backup_file}", "INFO")
            return True
        except Exception as e:
            self.log(f"备份失败: {str(e)}", "ERROR")
            return False

    def get_recent_calibrations(self, days: int = 7) -> List[Dict]:
        """
        获取最近校准记录
        
        :param days: 查询最近多少天的记录
        :return: 校准文件信息列表 [{
                'filename': str,
                'path': str,
                'modified': datetime,
                'size': int
            }]
        """
        recent_files = []
        cutoff_time = datetime.now() - datetime.timedelta(days=days)
        
        # 搜索主目录和归档目录
        search_dirs = [self.base_dir, os.path.join(self.base_dir, "archive")]
        
        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue
                
            for root, _, files in os.walk(search_dir):
                for file in files:
                    if file.startswith("RNX_Cal_DualPol_") and file.endswith(".csv"):
                        filepath = os.path.join(root, file)
                        try:
                            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                            if mtime > cutoff_time:
                                recent_files.append({
                                    'filename': file,
                                    'path': filepath,
                                    'modified': mtime,
                                    'size': os.path.getsize(filepath),
                                    'is_archived': "archive" in root
                                })
                        except Exception as e:
                            self.log(f"处理文件{file}失败: {str(e)}", "WARNING")
        
        # 按修改时间排序
        recent_files.sort(key=lambda x: x['modified'], reverse=True)
        return recent_files

    def get_version_history(self, filepath: str) -> List[str]:
        """
        获取文件的版本历史
        
        :param filepath: 校准文件路径
        :return: 版本说明列表
        """
        versions = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith("!VersionNotes:"):
                        versions.append(line.split(":", 1)[1].strip())
        except Exception as e:
            self.log(f"获取版本历史失败: {str(e)}", "ERROR")
        return versions


class ProcessManager:
    """进程管理单例类，负责检测和防止重复运行"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self.current_pid = os.getpid()
            self.script_path = os.path.abspath(sys.argv[0])
            self.lock_file = os.path.join(
                os.path.dirname(self.script_path),
                f".{os.path.basename(self.script_path)}.lock"
            )
            self.lock_fd = None
    
    def check_duplicate_instance(self):
        """检查是否有重复实例运行（支持跨平台）"""
        # 方法1：使用进程名检测（适用于所有平台）
        duplicate_count = self._count_process_instances()
        
        # 方法2：使用文件锁（防止终端多开）
        if not self._acquire_file_lock():
            duplicate_count += 1
        
        if duplicate_count > 2:
            self._show_warning_dialog()
            return True
        return False
    
    def _count_process_instances(self):
        """统计当前脚本的运行实例数"""
        count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # 跨平台兼容性处理
                cmdline = proc.info.get('cmdline', [])
                if (cmdline and 
                    os.path.abspath(cmdline[0]) == self.script_path and
                    proc.info['pid'] != self.current_pid):
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, IndexError):
                continue
        return count
    
    def _acquire_file_lock(self):
        """使用文件锁机制（支持Windows和Linux）"""
        try:
            if os.name == 'nt':  # Windows
                self.lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            else:  # Unix-like
                self.lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o644)
            atexit.register(self._release_file_lock)
            return True
        except OSError:
            return False
    
    def _release_file_lock(self):
        """释放文件锁"""
        if self.lock_fd:
            os.close(self.lock_fd)
            try:
                os.unlink(self.lock_file)
            except:
                pass
            self.lock_fd = None
    
    def _show_warning_dialog(self):
        """显示重复运行警告对话框"""
        app = QApplication.instance() or QApplication(sys.argv)
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("程序已运行")
        msg.setText("检测到程序已在运行中！")
        msg.setInformativeText("请勿重复启动本程序。")
        msg.setStandardButtons(QMessageBox.Ok)
        
        # 添加程序图标
        if hasattr(sys, '_MEIPASS'):  # PyInstaller打包环境
            icon_path = os.path.join(sys._MEIPASS, 'app.ico')
        else:
            icon_path = os.path.join(os.path.dirname(__file__), 'app.ico')
        
        if os.path.exists(icon_path):
            msg.setWindowIcon(QIcon(icon_path))
        
        # 居中显示对话框
        screen = QApplication.primaryScreen()
        msg.move(
            screen.geometry().center() - msg.rect().center()
        )
        msg.exec_()
        sys.exit(1)


if __name__ == "__main__":
    # 先检查是否已有实例运行
    process_mgr = ProcessManager()
    if process_mgr.check_duplicate_instance():
        sys.exit(1)
    
    # 正常启动主程序
    app = QApplication(sys.argv)
    
    # 设置应用程序名称（用于任务管理器识别）
    app.setApplicationName("RNX Quantum Antenna Test System")
    app.setApplicationDisplayName("RNX量子天线测试系统")
    

    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
