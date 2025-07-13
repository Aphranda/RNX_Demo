from PyQt5.QtWidgets import (
    QMainWindow, QStatusBar, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout,
    QSizePolicy, QToolBar, QFileDialog,QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtCore import QRegExp
from pathlib import Path

from app.widgets.LogWidget import LogWidget
from app.widgets.SimpleLinkDiagram import SimpleLinkDiagram
from app.widgets.StatusPanel import StatusPanel

class MainWindowUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RNX Quantum Antenna Test System - Demo")
        self.setGeometry(50, 40, 1800, 1100)
        
        # 初始化 UI 控件
        self._init_ui_components()
        
        # 设置布局
        self._setup_layout()
        
        # 应用样式表
        self._load_stylesheet()

    def _init_ui_components(self):
        """初始化所有 UI 控件"""
        # 状态栏
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        
        # 中央控件
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        
        # 链路图
        self.link_diagram = SimpleLinkDiagram()
        
        # 日志区域
        self.log_output = LogWidget()
        
        # 状态面板
        self.status_panel = StatusPanel()
        
        # ETH 设置控件
        self.eth_ip_input = QLineEdit()
        self.eth_ip_input.setPlaceholderText("192.168.1.11")
        self.eth_port_input = QLineEdit()
        self.eth_port_input.setPlaceholderText("7")
        self.eth_connect_btn = QPushButton("连接")
        self.eth_disconnect_btn = QPushButton("断开连接")
        self.freq_feed_link_check = QCheckBox("频率联动")
        self.freq_feed_link_check.setChecked(False)
        
        # 链路控制控件
        self.link_mode_combo = QComboBox()
        self.link_mode_combo.addItems([
            "FEED_X_THETA", "FEED_X_PHI", "FEED_KU_THETA", "FEED_KU_PHI",
            "FEED_K_THETA", "FEED_K_PHI", "FEED_KA_THETA", "FEED_KA_PHI"
        ])
        self.link_set_btn = QPushButton("设置链路")
        self.link_query_btn = QPushButton("查询链路")
        
        # 信号源控件
        self.freq_input = QLineEdit()
        self.freq_input.setPlaceholderText("如 8GHz")
        self.freq_btn = QPushButton("设置频率")
        self.freq_query_btn = QPushButton("查询频率")
        self.power_input = QLineEdit()
        self.power_input.setPlaceholderText("如 -40dBm")
        self.raw_power_input = QLineEdit()
        self.raw_power_input.setPlaceholderText("信号源实际输出")
        self.power_btn = QPushButton("设置功率")
        self.power_query_btn = QPushButton("查询功率")
        self.output_combo = QComboBox()
        self.output_combo.addItems(["ON", "OFF"])
        self.output_btn = QPushButton("设置输出")
        self.output_query_btn = QPushButton("查询输出")
        
        # 运动控制控件
        self.home_combo = QComboBox()
        self.home_combo.addItems(["X", "KU", "K", "KA", "ALL"])
        self.home_btn = QPushButton("执行复位")
        self.home_query_btn = QPushButton("查询复位")
        self.feed_combo = QComboBox()
        self.feed_combo.addItems(["X", "KU", "K", "KA"])
        self.feed_btn = QPushButton("执行达位")
        self.feed_query_btn = QPushButton("查询达位")
        self.speed_mod_combo = QComboBox()
        self.speed_mod_combo.addItems(["X", "KU", "K", "KA", "Z"])
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["LOW", "MID1", "MID2", "MID3", "HIGH"])
        self.speed_btn = QPushButton("设置速度")
        self.speed_query_btn = QPushButton("查询速度")
        
        # 添加输入验证器
        power_validator = QRegExpValidator(QRegExp(r"^-?\d+\.?\d*\s*(dBm)?$"))
        self.power_input.setValidator(power_validator)
        self.raw_power_input.setValidator(power_validator)

    def _setup_layout(self):
        """设置主布局"""
        main_layout = QHBoxLayout()
        
        # ==== 左侧面板 ====
        left_panel = QVBoxLayout()
        
        # 链路图区域
        link_group = QGroupBox("链路图")
        link_layout = QVBoxLayout(link_group)
        center_layout = QHBoxLayout()
        center_layout.addStretch()
        center_layout.addWidget(self.link_diagram)
        center_layout.addStretch()
        link_layout.addLayout(center_layout)
        left_panel.addWidget(link_group, stretch=3)
        
        # 日志区域
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        log_layout.addWidget(self.log_output)
        left_panel.addWidget(log_group, stretch=2)
        
        main_layout.addLayout(left_panel, stretch=2)
        
        # ==== 右侧面板 ====
        right_panel = QVBoxLayout()
        
        # 状态显示
        status_group = QGroupBox("状态显示")
        status_layout = QVBoxLayout(status_group)
        status_layout.addWidget(self.status_panel)
        right_panel.addWidget(status_group)
        
        # ETH 设置
        eth_group = QGroupBox()
        eth_layout = QHBoxLayout(eth_group)
        eth_layout.addWidget(QLabel("ETH IP:"))
        eth_layout.addWidget(self.eth_ip_input)
        eth_layout.addWidget(QLabel("Port:"))
        eth_layout.addWidget(self.eth_port_input)
        eth_layout.addWidget(self.eth_connect_btn)
        eth_layout.addWidget(self.eth_disconnect_btn)
        eth_layout.addWidget(self.freq_feed_link_check)
        eth_layout.addStretch()
        right_panel.addWidget(eth_group)
        
        # 链路控制
        link_ctrl_group = QGroupBox("链路控制")
        link_ctrl_layout = QHBoxLayout(link_ctrl_group)
        link_ctrl_layout.addWidget(QLabel("链路模式:"))
        link_ctrl_layout.addWidget(self.link_mode_combo)
        link_ctrl_layout.addWidget(self.link_set_btn)
        link_ctrl_layout.addWidget(self.link_query_btn)
        right_panel.addWidget(link_ctrl_group)
        
        # 信号源控制
        src_group = QGroupBox("信号源控制")
        src_layout = QGridLayout(src_group)
        src_layout.addWidget(QLabel("信号频率:"), 0, 0)
        src_layout.addWidget(self.freq_input, 0, 1, 1, 2)
        src_layout.addWidget(self.freq_btn, 0, 3)
        src_layout.addWidget(self.freq_query_btn, 0, 4)
        src_layout.addWidget(QLabel("馈源功率:"), 1, 0)
        src_layout.addWidget(self.power_input, 1, 1)
        src_layout.addWidget(self.raw_power_input, 1, 2)
        src_layout.addWidget(self.power_btn, 1, 3)
        src_layout.addWidget(self.power_query_btn, 1, 4)
        src_layout.addWidget(QLabel("RF输出:"), 2, 0)
        src_layout.addWidget(self.output_combo, 2, 1, 1, 2)
        src_layout.addWidget(self.output_btn, 2, 3)
        src_layout.addWidget(self.output_query_btn, 2, 4)
        right_panel.addWidget(src_group)
        
        # 运动控制
        self.motion_group = QGroupBox("运动控制")
        motion_layout = QGridLayout(self.motion_group)
        motion_layout.addWidget(QLabel("复位:"), 0, 0)
        motion_layout.addWidget(self.home_combo, 0, 1)
        motion_layout.addWidget(self.home_btn, 0, 2)
        motion_layout.addWidget(self.home_query_btn, 0, 3)
        motion_layout.addWidget(QLabel("达位:"), 1, 0)
        motion_layout.addWidget(self.feed_combo, 1, 1)
        motion_layout.addWidget(self.feed_btn, 1, 2)
        motion_layout.addWidget(self.feed_query_btn, 1, 3)
        motion_layout.addWidget(QLabel("速度:"), 2, 0)
        motion_layout.addWidget(self.speed_mod_combo, 2, 1)
        motion_layout.addWidget(self.speed_combo, 2, 2)
        motion_layout.addWidget(self.speed_btn, 2, 3)
        motion_layout.addWidget(self.speed_query_btn, 2, 4)
        right_panel.addWidget(self.motion_group)
        
        main_layout.addLayout(right_panel, stretch=3)
        
        # 设置中央控件布局
        layout = QVBoxLayout(self.central_widget)
        layout.addLayout(main_layout)

    def _load_stylesheet(self):
        """加载样式表"""
        search_paths = [
            "src/resources/styles/main_window.qss",
            "resources/styles/main_window.qss",
            ":/styles/main_window.qss"
        ]
        
        for path in search_paths:
            if Path(path).exists():
                with open(path, 'r', encoding='utf-8') as f:
                    self.setStyleSheet(f.read())
                print(f"成功加载样式表: {path}")
                return
        
        print("警告: 使用嵌入式默认样式")
        self.setStyleSheet("QMainWindow { background: #f0f0f0; }")

    def log(self, message, level="INFO"):
        """记录日志"""
        self.log_output.log(message, level)

    def show_status(self, message):
        """在状态栏显示消息"""
        self.status_bar.showMessage(message)
