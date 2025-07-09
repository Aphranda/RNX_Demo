from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QStatusBar, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout, QSizePolicy,QMessageBox
)
from PyQt5.QtGui import QFont, QColor, QPainter, QPen
from PyQt5.QtCore import Qt, QPointF, QThread, pyqtSignal, QMutex
import sys, os, psutil
import socket, select
import datetime
import time


class StatusQueryThread(QThread):
    status_signal = pyqtSignal(dict)

    def __init__(self, ip, port, mutex, parent=None):
        super().__init__(parent)
        self.ip = ip
        self.port = int(port)
        self.mutex = mutex
        self._running = True
        self.Is_moving = False  # 新增标志位

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
                    reach = "NO Parameter"
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
        self.current_link = link_mode
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
            ("Ku_THETA", "FEED_Ku_THETA"),
            ("Ku_PHI", "FEED_Ku_PHI"),
            ("K_THETA", "FEED_K_THETA"),
            ("K_PHI", "FEED_K__PHI"),
            ("Ka_THETA", "FEED_Ka_THETA"),
            ("Ka_PHI", "FEED_Ka_PHI"),
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
        now = datetime.datetime.now().strftime("%H:%M:%S")
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
        self.src_grid.addWidget(QLabel("输出频率:"), 0, 0)
        self.src_freq = QLabel("-")
        self.src_freq.setProperty("statusValue", True)
        self.src_grid.addWidget(self.src_freq, 0, 1)
        self.src_grid.addWidget(QLabel("输出功率:"), 1, 0)
        self.src_power = QLabel("-")
        self.src_power.setProperty("statusValue", True)
        self.src_grid.addWidget(self.src_power, 1, 1)
        self.src_grid.addWidget(QLabel("RF输出:"), 2, 0)
        self.src_rf = QLabel("-")
        self.src_rf.setProperty("statusValue", True)
        self.src_grid.addWidget(self.src_rf, 2, 1)
        src_layout.addStretch()

        motion_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        src_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        h_layout.addWidget(motion_group, stretch=1)
        h_layout.addWidget(src_group, stretch=1)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RNX Quantum Antenna Test System")
        self.setGeometry(150, 40, 1600, 1100)
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.apply_flat_style()  # 应用Fluent样式
        self.tcp_client = TcpClient()
        self.comm_mutex = QMutex()
        self.status_thread = None

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
            "FEED_X_THETA", "FEED_X_PHI", "FEED_Ku_THETA", "FEED_Ku_PHI",
            "FEED_K_THETA", "FEED_K__PHI", "FEED_Ka_THETA", "FEED_Ka_PHI"
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

        # 信号源控制
        src_group = QGroupBox("信号源控制")
        src_layout = QGridLayout()
        src_group.setLayout(src_layout)
        src_layout.addWidget(QLabel("频率:"), 0, 0)
        self.freq_input = QLineEdit()
        self.freq_input.setPlaceholderText("如 8GHz")
        src_layout.addWidget(self.freq_input, 0, 1)
        self.freq_btn = QPushButton("设置频率")
        self.freq_btn.clicked.connect(self.send_freq_cmd)
        src_layout.addWidget(self.freq_btn, 0, 2)
        self.freq_query_btn = QPushButton("查询频率")
        self.freq_query_btn.clicked.connect(self.query_freq_cmd)
        src_layout.addWidget(self.freq_query_btn, 0, 3)
        src_layout.addWidget(QLabel("功率:"), 1, 0)
        self.power_input = QLineEdit()
        self.power_input.setPlaceholderText("如 -40dBm")
        src_layout.addWidget(self.power_input, 1, 1)
        self.power_btn = QPushButton("设置功率")
        self.power_btn.clicked.connect(self.send_power_cmd)
        src_layout.addWidget(self.power_btn, 1, 2)
        self.power_query_btn = QPushButton("查询功率")
        self.power_query_btn.clicked.connect(self.query_power_cmd)
        src_layout.addWidget(self.power_query_btn, 1, 3)
        src_layout.addWidget(QLabel("RF输出:"), 2, 0)
        self.output_combo = QComboBox()
        self.output_combo.addItems(["ON", "OFF"])
        src_layout.addWidget(self.output_combo, 2, 1)
        self.output_btn = QPushButton("设置输出")
        self.output_btn.clicked.connect(self.send_output_cmd)
        src_layout.addWidget(self.output_btn, 2, 2)
        self.output_query_btn = QPushButton("查询输出")
        self.output_query_btn.clicked.connect(self.query_output_cmd)
        src_layout.addWidget(self.output_query_btn, 2, 3)
        right_panel.addWidget(src_group)

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

    # --- 指令组合与发送 ---
    def send_link_cmd(self):
        mode = self.link_mode_combo.currentText()
        cmd = f"CONFigure:LINK {mode}"
        self.link_diagram.set_link(mode)  # 动态刷新链路图
        self.send_and_log(cmd)

    def query_link_cmd(self):
        cmd = "READ:LINK:STATe?"
        self.send_and_log(cmd)

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
        cmd = f"SOURce:POWer {val}"
        self.send_and_log(cmd)

    def query_power_cmd(self):
        cmd = "READ:SOURce:POWer?"
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
        self.send_and_log(cmd)

    def query_home_cmd(self):
        val = self.home_combo.currentText()
        cmd = f"READ:MOTion:HOME? {val}"
        self.send_and_log(cmd)

    def send_feed_cmd(self):
        val = self.feed_combo.currentText()
        cmd = f"MOTion:FEED {val}"
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
                self.status_panel.motion_reach[axis].setText("NO Param")
                set_status_color(self.status_panel.motion_reach[axis], "NO Param")
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
        power_disp = format_power(src.get("power", "-"))
        self.status_panel.src_power.setText(power_disp)
        set_status_color(self.status_panel.src_power, power_disp)
        self.status_panel.src_rf.setText(src.get("rf", "-"))
        set_status_color(self.status_panel.src_rf, src.get("rf", "-"))

        self.status_panel.motion_label.setText("运动状态更新中...")
        self.status_panel.motion_label.setStyleSheet("color: #228B22;")
        self.status_panel.src_label.setText("信号源状态更新中...")
        self.status_panel.src_label.setStyleSheet("color: #228B22;")

def count_current_process_instances():
    current_pid = os.getpid()  # 当前进程PID
    current_script_path = os.path.abspath(sys.argv[0])  # 当前脚本绝对路径
    count = 0
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            # 检查进程命令行是否匹配当前脚本路径
            cmdline = proc.info['cmdline']
            if cmdline and os.path.abspath(cmdline[0]) == current_script_path:
                if proc.info['pid'] != current_pid:  # 排除自己
                    count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, IndexError):
            continue
    return count

if __name__ == "__main__":

    if count_current_process_instances() > 2:
        app = QApplication(sys.argv)  # 先创建QApplication
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("警告")
        msg.setText("已有相同软件在运行！")
        msg.setInformativeText("请勿重复启动本程序。")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()  # 等待用户点击确认
        
        sys.exit(1)  # 用户点击确认后退出

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())