from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QStatusBar, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout, QSizePolicy,QMessageBox,QCheckBox
)
from PyQt5.QtGui import QFont, QColor, QPainter, QPen
from PyQt5.QtCore import Qt, QPointF, QThread, pyqtSignal, QMutex
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtCore import QRegExp

import sys, os, psutil
import socket, select
import datetime
import time
import atexit # 确保程序退出时清理资源
import os
import hashlib
import shutil
import datetime
import threading
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone
import json,struct


class StatusQueryThread(QThread):
    status_signal = pyqtSignal(dict)

    def __init__(self, ip, port, mutex, parent=None):
        super().__init__(parent)
        self.ip = ip
        self.port = int(port)
        self.mutex = mutex
        self._running = True
        self.current_operation = None  # 新增：当前操作状态
        self.operating_axis = None    # 新增：当前操作的轴

    def run(self):
        axes = ["X", "KU", "K", "KA", "Z"]
        axis_idx = 0
        while self._running:
            status = {"motion": {}, "src": {}}
            self.mutex.lock()
            try:
                # 每次只查一个轴
                axis= axes[axis_idx]
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
        """
        带超时重发机制的查询方法
        参数:
            cmd: 要发送的命令字符串
            max_retries: 最大重试次数 (默认3次)
            base_timeout: 基础超时时间(秒)，会随重试次数增加 (默认1秒)
        返回:
            成功: 返回设备响应字符串
            失败: 返回错误信息字符串
        """
        retry_count = 0
        last_exception = None
        
        while retry_count < max_retries:
            sock = None
            try:
                # 动态计算当前超时时间 (指数退避算法)
                current_timeout = min(base_timeout * (2 ** retry_count), 5.0)  # 最大不超过5秒
                
                # 建立连接并设置超时
                sock = socket.create_connection((self.ip, self.port), timeout=current_timeout)
                sock.settimeout(current_timeout)
                
                # 发送命令
                sock.sendall((cmd + '\n').encode('utf-8'))
                
                # 接收数据（支持分片接收）
                data = b''
                start_time = time.time()
                while True:
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
        
        # 所有重试失败后的处理
        error_msg = f"命令 '{cmd}' 执行失败(重试{retry_count}次)"
        if last_exception:
            error_msg += f": {str(last_exception)}"
        
        return error_msg


    def stop(self):
        self._running = False

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

class LogWidget(QTextEdit):
    """带等级和时间戳的日志输出控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)

    def log(self, message, level="INFO"):
        now = datetime.now().strftime("%H:%M:%S")
        color = {
            "INFO": "#222222",
            "SUCCESS": "#228B22",
            "WARNING": "#e67e22",
            "ERROR": "#d32f2f",
            "SEND": "#0078d7",
            "RECV": "#8e44ad"
        }.get(level, "#222222")
        html = f'<span style="color:gray;">[{now}]</span> ' \
               f'<span style="color:{color};font-weight:bold;">[{level}]</span> ' \
               f'<span style="color:{color};">{message}</span>'
        self.append(html)

class StatusPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(240)
        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(18, 5, 18, 5)
        h_layout.setSpacing(10)

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

        self.src_grid.addWidget(QLabel("信号频率:"), 0, 0)
        self.src_freq = QLabel("-")
        self.src_freq.setProperty("statusValue", True)
        self.src_grid.addWidget(self.src_freq, 0, 1)

        self.src_grid.addWidget(QLabel("信号功率:"), 1, 0)
        self.src_raw_power = QLabel("-")
        self.src_raw_power.setProperty("statusValue", True)
        self.src_grid.addWidget(self.src_raw_power, 1, 1)

        self.src_grid.addWidget(QLabel("馈源功率:"), 2, 0)
        self.src_power = QLabel("-")
        self.src_power.setProperty("statusValue", True)
        self.src_grid.addWidget(self.src_power, 2, 1)

        self.src_grid.addWidget(QLabel("RF输出:"), 3, 0)
        self.src_rf = QLabel("-")
        self.src_rf.setProperty("statusValue", True)
        self.src_grid.addWidget(self.src_rf, 3, 1)


        # 新增：校准文件状态
        self.src_grid.addWidget(QLabel("校准文件:"), 4, 0)
        self.cal_file_status = QLabel("未加载")
        self.cal_file_status.setProperty("statusValue", True)
        self.src_grid.addWidget(self.cal_file_status, 4, 1)
        
        # 新增：校准文件路径输入和加载按钮
        self.src_grid.addWidget(QLabel("校准路径:"), 5, 0)
        self.cal_file_input = QLineEdit()

        self.cal_file_input.setPlaceholderText("选择校准文件...")
        self.src_grid.addWidget(self.cal_file_input, 5, 1)
        
        self.load_cal_btn = QPushButton("加载")
        self.load_cal_btn.setFixedWidth(80)  # 设置固定宽度
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
        motion_group = QGroupBox("运动控制")
        motion_layout = QGridLayout()
        motion_group.setLayout(motion_layout)
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
        right_panel.addWidget(motion_group)

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
        else:
            self.log(f"连接失败: {message}", "ERROR")


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
        else:
            self.show_status("未连接到设备。")
            self.log("未连接到设备。", "WARNING")

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



    # def load_calibration_file(self):
    #     """加载校准文件"""
    #     from PyQt5.QtWidgets import QFileDialog

    #     # 获取最近校准文件目录
    #     cal_dir = "calibrations"  # 默认目录
    #     if hasattr(self, 'cal_manager'):
    #         cal_dir = self.cal_manager.base_dir
        
    #     # 打开文件选择对话框
    #     file_path, _ = QFileDialog.getOpenFileName(
    #         self, 
    #         "选择校准文件", 
    #         cal_dir, 
    #         "校准文件 (*.csv);;所有文件 (*)"
    #     )
        
    #     if file_path:
    #         self.status_panel.cal_file_input.setText(file_path)
    #         self.log(f"已选择校准文件: {file_path}", "INFO")
            
    #         # 验证文件
    #         if not hasattr(self, 'cal_manager'):
    #             self.cal_manager = CalibrationFileManager(log_callback=self.log)
                
    #         if self.cal_manager.validate_calibration_file(file_path):
    #             self.status_panel.cal_file_status.setText("已加载")
    #             self.status_panel.cal_file_status.setStyleSheet(
    #                 "background:#b6f5c6; color:#0078d7; border:2px solid #0078d7; border-radius:8px;"
    #             )
    #             self.show_status(f"校准文件有效: {os.path.basename(file_path)}")
    #             self.log("校准文件验证通过", "SUCCESS")
                
    #             # 这里可以添加实际加载校准数据的逻辑
    #             # 例如: self.load_calibration_data(file_path)
    #         else:
    #             self.status_panel.cal_file_status.setText("无效")
    #             self.status_panel.cal_file_status.setStyleSheet(
    #                 "background:#ffcdd2; color:#d32f2f; border:2px solid #0078d7; border-radius:8px;"
    #             )
    #             self.show_status("校准文件无效")
    #             self.log("校准文件验证失败", "ERROR")

    def load_calibration_file(self, filepath: str):
        """加载校准文件"""
        from PyQt5.QtWidgets import QFileDialog


        # 确保cal_manager已初始化
        if self.cal_manager is None:
            self.cal_manager = CalibrationFileManager(log_callback=self.log)

           # self.cal_manager.generate_default_calibration((8, 40), 0.01)  # 生成默认校准数据
        
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

            # 打印文件内容验证
            if file_path.lower().endswith('.bin'):
                self._print_bin_file_contents(file_path)  # 调用解耦后的BIN文件打印函数
            elif file_path.lower().endswith('.csv'):
                self._print_csv_file_contents(file_path)
            
            # 使用CalibrationFileManager加载文件
            if not hasattr(self, 'cal_manager'):
                self.cal_manager = CalibrationFileManager(log_callback=self.log)
            
            result = self.cal_manager.load_calibration_file(file_path)
            if result:
                self.calibration_data = result['data']
                self.compensation_enabled = True
                self.status_panel.cal_file_status.setText("已加载")
                self.status_panel.cal_file_status.setStyleSheet(
                    "background:#b6f5c6; color:#0078d7; border:2px solid #0078d7; border-radius:8px;"
                )
                self.log("校准文件加载成功，补偿功能已启用", "SUCCESS")
            else:
                self.compensation_enabled = False
                self.status_panel.cal_file_status.setText("无效")
                self.status_panel.cal_file_status.setStyleSheet(
                    "background:#ffcdd2; color:#d32f2f; border:2px solid #0078d7; border-radius:8px;"
                )
                self.log("校准文件加载失败", "ERROR")

    def _print_bin_file_contents(self, bin_path: str):
        """打印BIN文件内容用于验证数据正确性"""
        try:
            result = self.cal_manager._read_bin_file(bin_path)
            if not result:
                self.log("无法读取BIN文件内容", "ERROR")
                return
                
            meta = result['meta']
            data_points = result['data']
            
            self.log("\n=== BIN文件元数据 ===", "INFO")
            self.log(f"创建时间: {meta.get('created', '未知')}", "INFO")
            self.log(f"操作员: {meta.get('operator', '未知')}", "INFO")
            self.log(f"信号源: {meta.get('signal_gen', ['未知', '未知'])[0]} (SN: {meta.get('signal_gen', ['', '未知'])[1]})", "INFO")
            self.log(f"频谱分析仪: {meta.get('spec_analyzer', ['未知', '未知'])[0]} (SN: {meta.get('spec_analyzer', ['', '未知'])[1]})", "INFO")
            self.log(f"天线: {meta.get('antenna', ['未知', '未知'])[0]} (SN: {meta.get('antenna', ['', '未知'])[1]})", "INFO")
            self.log(f"环境: {meta.get('environment', [0, 0])[0]}°C, {meta.get('environment', [0, 0])[1]}%RH", "INFO")
            
            freq_params = meta.get('freq_params', {})
            self.log("\n=== 频率参数 ===", "INFO")
            self.log(f"起始频率: {freq_params.get('start_ghz', '未知')} GHz", "INFO")
            self.log(f"终止频率: {freq_params.get('stop_ghz', '未知')} GHz", "INFO")
            self.log(f"步进: {freq_params.get('step_ghz', '未知')} GHz", "INFO")
            self.log(f"点数: {meta.get('points', '未知')}", "INFO")
            
            self.log("\n=== 数据点示例 ===", "INFO")
            if data_points:
                # 打印前5个点
                self.log("前5个数据点:", "INFO")
                for i, point in enumerate(data_points[:5]):
                    self.log(
                        f"点 {i}: 频率={point['freq']:.3f}GHz, "
                        f"Xθ={point['x_theta']:.2f}, Xφ={point['x_phi']:.2f}, "
                        f"KUθ={point['ku_theta']:.2f}, KUφ={point['ku_phi']:.2f}, "
                        f"Kθ={point['k_theta']:.2f}, Kφ={point['k_phi']:.2f}, "
                        f"KAθ={point['ka_theta']:.2f}, KAφ={point['ka_phi']:.2f}", 
                        "INFO"
                    )
                
                # 打印后5个点（如果存在）
                if len(data_points) > 5:
                    self.log("\n最后5个数据点:", "INFO")
                    for i, point in enumerate(data_points[-5:], len(data_points)-5):
                        self.log(
                            f"点 {i}: 频率={point['freq']:.3f}GHz, "
                            f"Xθ={point['x_theta']:.2f}, Xφ={point['x_phi']:.2f}, "
                            f"KUθ={point['ku_theta']:.2f}, KUφ={point['ku_phi']:.2f}, "
                            f"Kθ={point['k_theta']:.2f}, Kφ={point['k_phi']:.2f}, "
                            f"KAθ={point['ka_theta']:.2f}, KAφ={point['ka_phi']:.2f}", 
                            "INFO"
                        )
            
            self.log("\n=== 总结 ===", "INFO")
            self.log(f"总数据点数: {len(data_points)}", "INFO")
            self.log(f"预期点数: {meta.get('points', '未知')}", "INFO")
            if len(data_points) == meta.get('points', -1):
                self.log("数据点数匹配", "SUCCESS")
            else:
                self.log("数据点数不匹配", "ERROR")
        
        except Exception as e:
            self.log(f"读取BIN文件失败: {str(e)}", "ERROR")

    def _print_csv_file_contents(self, csv_path: str):
        """打印CSV文件内容用于验证数据正确性"""
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            self.log("\n=== CSV文件内容 ===", "INFO")
            
            # 打印前10行（通常是元数据和标题）
            self.log("文件头:", "INFO")
            for line in lines[:10]:
                if line.strip():  # 跳过空行
                    self.log(line.strip(), "INFO")
            
            # 打印数据部分的前5行和后5行
            data_lines = [line for line in lines if not line.startswith('!') and line.strip()]
            if len(data_lines) > 1:  # 第一行是标题
                self.log("\n数据前5行:", "INFO")
                for line in data_lines[1:6]:
                    self.log(line.strip(), "INFO")
                
                if len(data_lines) > 6:
                    self.log("\n数据后5行:", "INFO")
                    for line in data_lines[-5:]:
                        self.log(line.strip(), "INFO")
            
            # 打印文件统计信息
            self.log("\n=== 文件统计 ===", "INFO")
            self.log(f"总行数: {len(lines)}", "INFO")
            self.log(f"数据行数: {len(data_lines)-1}", "INFO")  # 减去标题行
            self.log(f"文件大小: {os.path.getsize(csv_path)/1024:.2f} KB", "INFO")
            
        except Exception as e:
            self.log(f"读取CSV文件失败: {str(e)}", "ERROR")

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
        axes = ["X", "KU", "K", "KA", "Z"]
        # 更新缓存
        for axis in axes:
            if axis in status.get("motion", {}):
                for key in ["reach", "home", "speed"]:
                    val = status["motion"][axis].get(key)
                    if val is not None:
                        self.status_cache["motion"][axis][key] = val
        for key in ["freq", "power", "rf"]:
            val = status.get("src", {}).get(key)
            if val is not None:
                self.status_cache["src"][key] = val

        def set_status_color(label, text):
            if text is None:
                text = "-"
            if any(x in text.upper() for x in ["NO", "FAIL"]):
                label.setStyleSheet("background:#fff9c4; color:#0078d7; border:2px solid #0078d7; border-radius:8px;")
            elif any(x in text.upper() for x in ["OK", "PASS"]):
                label.setStyleSheet("background:#b6f5c6; color:#0078d7; border:2px solid #0078d7; border-radius:8px;")
            elif any(x in text for x in ["超时", "timeout", "连接失败"]):
                label.setStyleSheet("background:#ffcdd2; color:#d32f2f; border:2px solid #0078d7; border-radius:8px;")
            else:
                label.setStyleSheet("background:#f5faff; color:#0078d7; border:2px solid #0078d7; border-radius:8px;")

        # 刷新界面，始终显示所有缓存值
        for axis in axes:
            axis_status = self.status_cache["motion"][axis]
            # 达位
            if axis == "Z":
                self.status_panel.motion_reach[axis].setText("NO Pa")
                set_status_color(self.status_panel.motion_reach[axis], "NO Pa")
            else:
                txt = axis_status.get("reach", "-")
                self.status_panel.motion_reach[axis].setText(txt)
                set_status_color(self.status_panel.motion_reach[axis], txt)
            # 复位
            txt = axis_status.get("home", "-")
            self.status_panel.motion_home[axis].setText(txt)
            set_status_color(self.status_panel.motion_home[axis], txt)
            # 速度
            txt = axis_status.get("speed", "-")
            self.status_panel.motion_speed[axis].setText(txt)
            # 根据速度等级着色（橙黄系，和蓝色对比强）
            speed_color = {
                "LOW":   "#ffe082",
                "MID1":  "#ffd54f",
                "MID2":  "#ffb300",
                "MID3":  "#ff8f00",
                "HIGH":  "#ff6f00"
            }
            bg = speed_color.get(txt.upper(), "#f5faff")
            self.status_panel.motion_speed[axis].setStyleSheet(
                f"background:{bg}; color:#0078d7; border:2px solid #0078d7; border-radius:8px;"
            )


        # 信号源
        src = self.status_cache["src"]
        # ==== 新增：状态颜色设置 ====
        
        # ==== 新增：格式化频率和功率 ====
        def format_freq(freq_str):
            try:
                freq = str(freq_str).replace("Hz", "").replace("hz", "").replace(" ", "")
                freq_val = float(freq)
                # 科学计数法或大数转GHz
                if freq_val >= 1e6:
                    return f"{freq_val/1e9:.6f} GHz"
                else:
                    return f"{freq_val} Hz"
            except Exception:
                return str(freq_str)

        def format_power(power_str):
            try:
                power = str(power_str).replace("dBm", "").replace("dbm", "").replace(" ", "")
                power_val = float(power)
                return f"{power_val:.2f} dBm"
            except Exception:
                return str(power_str)

        freq_disp = format_freq(src.get("freq", "-"))
        self.status_panel.src_freq.setText(freq_disp)
        set_status_color(self.status_panel.src_freq, freq_disp)

        power_raw_disp = format_power(src.get("power", "-"))
        self.status_panel.src_raw_power.setText(power_raw_disp)
        set_status_color(self.status_panel.src_raw_power, power_raw_disp)

        # 功率显示加入补偿
        power_str = src.get("power", "-")
        if power_str != "-" and self.compensation_enabled:
            try:
                # 解析查询到的功率值
                measured_power = float(power_str.replace("dBm", "").strip())
                
                # 获取当前频率
                freq_str = src.get("freq", "0")
                freq_ghz = float(freq_str.replace("GHz", "").strip()) if "GHz" in freq_str else float(freq_str)/1e9
                
                # 计算补偿值
                compensation = self.get_compensation_value(freq_ghz)
                actual_power = measured_power + compensation
                
                power_disp = f"{actual_power:.2f} dBm"
            except ValueError:
                power_disp = format_power(power_str)
        else:
            power_disp = format_power(power_str)
        
        self.status_panel.src_power.setText(power_disp)
        set_status_color(self.status_panel.src_power, power_disp)

        # RF输出显示 - 直接添加条件判断
        rf_status = src.get("rf", "-")
        self.status_panel.src_rf.setText(rf_status)
        if rf_status.upper() == "ON":
            self.status_panel.src_rf.setStyleSheet(
                "background:#b6f5c6; color:#0078d7; border:2px solid #0078d7; border-radius:8px;"
            )
        else:
            # 使用默认样式
            self.status_panel.src_rf.setStyleSheet(
                "background:#f5faff; color:#0078d7; border:2px solid #0078d7; border-radius:8px;"
            )

        # 更新状态标签显示
        if self.status_thread and self.status_thread.current_operation:
            operation = self.status_thread.current_operation
            axis = self.status_thread.operating_axis
            if operation == "HOMING":
                self.status_panel.motion_label.setText(f"{axis}轴复位中...")
                self.status_panel.motion_label.setStyleSheet("color: #ff8f00;")  # 橙色
            elif operation == "FEEDING":
                self.status_panel.motion_label.setText(f"{axis}轴达位中...")
                self.status_panel.motion_label.setStyleSheet("color: #ff8f00;")  # 橙色
            # 检查操作是否完成
            axis_status = self.status_cache["motion"].get(axis, {})
            if (operation == "HOMING" and "OK" in axis_status.get("home", "")) or \
            (operation == "FEEDING" and "OK" in axis_status.get("reach", "")):
                self.status_thread.current_operation = None
                self.status_thread.operating_axis = None
                self.status_panel.motion_label.setText("运动状态: 就绪")
                self.status_panel.motion_label.setStyleSheet("color: #228B22;")  # 绿色
        else:
            self.status_panel.motion_label.setText("运动状态: 就绪")
            self.status_panel.motion_label.setStyleSheet("color: #228B22;")  # 绿色
        
        # 信号源状态标签保持不变
        self.status_panel.src_label.setText("信号源状态更新中...")
        self.status_panel.src_label.setStyleSheet("color: #228B22;")



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
        
    def _read_bin_file(self, bin_path: str) -> Optional[Dict]:
        """读取BIN格式校准文件"""
        try:
            with open(bin_path, 'rb') as f:
                # 验证头部
                magic = f.read(4)
                if magic != b'RNXC':
                    raise ValueError("无效的二进制文件格式")
                
                version = ord(f.read(1))
                if version != 1:
                    raise ValueError(f"不支持的版本号: {version}")
                
                # 读取元数据
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
                
                return {
                    'meta': meta,
                    'data': data_points
                }
        except Exception as e:
            self.log(f"读取二进制文件失败: {str(e)}", "ERROR")
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
            return self._read_bin_file(filepath)
        else:
            return self._load_csv_file(filepath)

    def _load_csv_file(self, csv_path: str) -> Optional[Dict]:
        """加载CSV格式校准文件"""
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 解析元数据
            meta = {
                'file_format': 'csv',
                'header': []
            }
            data_start = 0
            for i, line in enumerate(lines):
                if line.startswith('!'):
                    meta['header'].append(line.strip())
                    # 解析特定元数据
                    if line.startswith('!Created:'):
                        meta['created'] = line.split(':', 1)[1].strip()
                    elif line.startswith('!Operator:'):
                        meta['operator'] = line.split(':', 1)[1].strip()
                    elif line.startswith('!  Points:'):
                        meta['points'] = int(line.split(':', 1)[1].strip())
                else:
                    data_start = i
                    break
            
            # 解析数据
            data_points = []
            for line in lines[data_start:]:
                if line.startswith('!') or not line.strip():
                    continue
                
                parts = line.strip().split(',')
                if len(parts) != 9:
                    continue
                
                try:
                    data_points.append({
                        'freq': float(parts[0]),
                        'x_theta': float(parts[1]),
                        'x_phi': float(parts[2]),
                        'ku_theta': float(parts[3]),
                        'ku_phi': float(parts[4]),
                        'k_theta': float(parts[5]),
                        'k_phi': float(parts[6]),
                        'ka_theta': float(parts[7]),
                        'ka_phi': float(parts[8])
                    })
                except ValueError:
                    continue
            
            return {
                'meta': meta,
                'data': data_points
            }
        except Exception as e:
            self.log(f"读取CSV文件失败: {str(e)}", "ERROR")
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

    def validate_calibration_file(self, filepath: str) -> bool:
        """
        验证现有校准文件完整性
        
        :param filepath: 校准文件路径
        :return: 文件是否有效
        """
        if not os.path.exists(filepath):
            self.log(f"文件不存在: {filepath}", "ERROR")
            return False
        
        # 根据文件扩展名选择验证方式
        if filepath.lower().endswith('.bin'):
            return self._validate_bin_file(filepath)
        else:
            return self._validate_csv_file(filepath)

    def _validate_bin_file(self, filepath: str) -> bool:
        """验证BIN格式校准文件"""
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

    def _validate_csv_file(self, filepath: str) -> bool:
        """验证CSV格式校准文件"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 检查文件头
            if not lines or not lines[0].startswith("!RNX Dual-Polarized Feed Calibration Data"):
                self.log("无效的文件头", "WARNING")
                return False
                
            # 提取元数据
            header_points = None
            for line in lines:
                if line.startswith("!  Points:"):
                    header_points = int(line.split(":")[1].strip())
                    break
                    
            if header_points is None:
                self.log("缺少点数信息", "WARNING")
                return False
                
            # 统计数据行数
            data_lines = sum(1 for line in lines if not line.startswith("!") and line.strip())
            if data_lines - 1 != header_points:  # 减去标题行
                self.log(f"数据点数不匹配: 预期{header_points}, 实际{data_lines-1}", "WARNING")
                return False
                
            # 检查结束标记和校验值
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
        
    def print_bin_file_contents(self, bin_path: str):
        """
        打印BIN文件内容用于验证数据正确性
        
        :param bin_path: BIN文件路径
        """
        if not os.path.exists(bin_path):
            self.log(f"BIN文件不存在: {bin_path}", "ERROR")
            return
        
        try:
            with open(bin_path, 'rb') as f:
                # 读取头部
                magic = f.read(4)
                version = ord(f.read(1))
                meta_len = int.from_bytes(f.read(4), 'little')
                meta_json = f.read(meta_len).decode('utf-8')
                meta = json.loads(meta_json)
                
                self.log("\n=== BIN文件元数据 ===", "INFO")
                self.log(f"幻数: {magic}", "INFO")
                self.log(f"版本: {version}", "INFO")
                self.log(f"元数据长度: {meta_len} 字节", "INFO")
                self.log("元数据内容:", "INFO")
                for key, value in meta.items():
                    self.log(f"  {key}: {value}", "INFO")
                
                self.log("\n=== 数据点 ===", "INFO")
                point_count = 0
                while True:
                    freq_bytes = f.read(4)
                    if not freq_bytes:
                        break
                    
                    freq = struct.unpack('f', freq_bytes)[0]
                    data = struct.unpack('8f', f.read(32))
                    
                    # 打印前5个和后5个数据点，避免日志过多
                    if point_count < 5 or point_count >= (meta.get('points', 0) - 5):
                        self.log(
                            f"点 {point_count}: 频率={freq:.3f}GHz, "
                            f"Xθ={data[0]:.2f}, Xφ={data[1]:.2f}, "
                            f"KUθ={data[2]:.2f}, KUφ={data[3]:.2f}, "
                            f"Kθ={data[4]:.2f}, Kφ={data[5]:.2f}, "
                            f"KAθ={data[6]:.2f}, KAφ={data[7]:.2f}", 
                            "INFO"
                        )
                    
                    point_count += 1
                
                self.log(f"\n=== 总结 ===", "INFO")
                self.log(f"总数据点数: {point_count}", "INFO")
                self.log(f"预期点数: {meta.get('points', '未知')}", "INFO")
                if point_count == meta.get('points', -1):
                    self.log("数据点数匹配", "SUCCESS")
                else:
                    self.log("数据点数不匹配", "ERROR")
        
        except Exception as e:
            self.log(f"读取BIN文件失败: {str(e)}", "ERROR")

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
    
    # # 加载样式表
    # with open("style.qss", "r", encoding="utf-8") as f:
    #     app.setStyleSheet(f.read())
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
