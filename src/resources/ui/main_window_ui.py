from PyQt5.QtWidgets import (
    QMainWindow, QStatusBar, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout,
    QSizePolicy, QToolBar, QFileDialog, QCheckBox, QAction
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QRegExpValidator, QIcon
from PyQt5.QtCore import QRegExp
from pathlib import Path

from app.widgets.LogWidget.LogWidget import LogWidget
from app.widgets.SimpleLinkDiagram import SimpleLinkDiagram
from app.widgets.StatusPanel.StatusPanel import StatusPanel
from app.widgets.CalibrationPanel.CalibrationPanel import CalibrationPanel

class MainWindowUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RNX Quantum Antenna Test System - Demo")
        self.setGeometry(50, 40, 1800, 1100)
        
        # 初始化 UI 控件
        self._init_ui_components()
        
        # 设置布局
        self._setup_layout()
        
        # 创建工具栏
        self._create_toolbar()
        
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
        self.status_panel = StatusPanel(self)

        # 创建校准面板控制器
        self.calibration_panel = CalibrationPanel(self)
        self.calibration_panel.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.calibration_panel.hide()  # 初始隐藏


        
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

    def _create_toolbar(self):
        """创建主工具栏"""
        self.toolbar = QToolBar("主工具栏")
        self.toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)
        
        # 设置工具栏图标和文字都显示
        # self.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        
        # 校准工具
        icon_path = "src/resources/icons/icon_calibration.png"
        if Path(icon_path).exists():
            self.calibration_action = QAction(QIcon(icon_path), "校准", self)
        else:
            self.calibration_action = QAction("校准", self)
        self.calibration_action.setStatusTip("打开校准工具")
        self.toolbar.addAction(self.calibration_action)

        # 数据绘图
        icon_path = "src/resources/icons/icon_plot.png"  # 使用实际路径
        if Path(icon_path).exists():
            self.plot_action = QAction(QIcon(icon_path), "数据绘图", self)
        else:
            self.plot_action = QAction("数据绘图", self)
        self.plot_action.setStatusTip("打开数据绘图工具")
        self.toolbar.addAction(self.plot_action)
        
        # 添加分隔线
        self.toolbar.addSeparator()
        
        # 数据导入
        icon_path = "src/resources/icons/icon_import.png"
        if Path(icon_path).exists():
            self.import_action = QAction(QIcon(icon_path), "导入数据", self)
        else:
            self.import_action = QAction("导入数据", self)
        self.import_action.setStatusTip("导入测试数据")
        self.toolbar.addAction(self.import_action)
        
        # 数据导出
        icon_path = "src/resources/icons/icon_export.png"
        if Path(icon_path).exists():
            self.export_action = QAction(QIcon(icon_path), "导出数据", self)
        else:
            self.export_action = QAction("导出数据", self)
        self.export_action.setStatusTip("导出测试数据")
        self.toolbar.addAction(self.export_action)
        
        # 添加分隔线
        self.toolbar.addSeparator()
        
        # 系统设置
        icon_path = "src/resources/icons/icon_settings.png"
        if Path(icon_path).exists():
            self.settings_action = QAction(QIcon(icon_path), "系统设置", self)
        else:
            self.settings_action = QAction("系统设置", self)
        self.settings_action.setStatusTip("打开系统设置")
        self.toolbar.addAction(self.settings_action)
        
        # 帮助
        icon_path = "src/resources/icons/icon_help.png"
        if Path(icon_path).exists():
            self.help_action = QAction(QIcon(icon_path), "帮助", self)
        else:
            self.help_action = QAction("帮助", self)
        self.help_action.setStatusTip("打开帮助文档")
        self.toolbar.addAction(self.help_action)


    def _setup_layout(self):
        """设置主布局"""
        main_layout = QHBoxLayout()
        main_layout.setSpacing(10)  # 增加主布局间距
        
        # ==== 左侧面板 ====
        left_panel = QVBoxLayout()
        left_panel.setSpacing(8)  # 减小左侧面板间距
        
        # 链路图区域 - 使用固定高度
        # 链路图区域 - 使用固定高度并确保居中
        link_group = QGroupBox("链路图")
        link_layout = QVBoxLayout(link_group)
        link_layout.setContentsMargins(5, 10, 5, 10)
        
        # 创建居中布局的容器
        diagram_container = QWidget()
        diagram_container_layout = QHBoxLayout(diagram_container)
        self.link_diagram.setFixedHeight(470)  # 设置固定高度
        diagram_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # 添加伸缩因子使链路图居中
        diagram_container_layout.addStretch()
        diagram_container_layout.addWidget(self.link_diagram)
        diagram_container_layout.addStretch()
        
        link_layout.addWidget(diagram_container)
        left_panel.addWidget(link_group)
            
        # 日志区域 - 使用剩余空间
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(5, 10, 5, 10)  # 减小内边距
        log_layout.addWidget(self.log_output)
        left_panel.addWidget(log_group, stretch=1)  # 使用拉伸因子
        
        main_layout.addLayout(left_panel, stretch=2)
        
        # ==== 右侧面板 ====
        right_panel = QVBoxLayout()
        right_panel.setSpacing(8)  # 减小右侧面板间距
        
        # 状态显示 - 固定高度
        status_group = QGroupBox("状态显示")
        status_layout = QVBoxLayout(status_group)
        status_layout.setContentsMargins(5, 10, 5, 10)
        status_layout.addWidget(self.status_panel)
        right_panel.addWidget(status_group)
        
        # ETH 设置 - 紧凑布局
        eth_group = QGroupBox("网络设置")
        eth_layout = QHBoxLayout(eth_group)
        eth_layout.setContentsMargins(5, 10, 5, 10)
        eth_layout.addWidget(QLabel("ETH IP:"))
        eth_layout.addWidget(self.eth_ip_input, stretch=1)  # 输入框可拉伸
        eth_layout.addWidget(QLabel("Port:"))
        eth_layout.addWidget(self.eth_port_input, stretch=1)
        eth_layout.addWidget(self.eth_connect_btn)
        eth_layout.addWidget(self.eth_disconnect_btn)
        eth_layout.addWidget(self.freq_feed_link_check)
        right_panel.addWidget(eth_group)
        
        # 链路控制 - 紧凑布局
        link_ctrl_group = QGroupBox("链路控制")
        link_ctrl_layout = QHBoxLayout(link_ctrl_group)
        link_ctrl_layout.setContentsMargins(5, 10, 5, 10)
        link_ctrl_layout.addWidget(QLabel("链路模式:"))
        link_ctrl_layout.addWidget(self.link_mode_combo, stretch=2)  # 组合框可拉伸
        link_ctrl_layout.addWidget(self.link_set_btn)
        link_ctrl_layout.addWidget(self.link_query_btn)
        right_panel.addWidget(link_ctrl_group)
        
        # 信号源控制 - 紧凑网格布局
        src_group = QGroupBox("信号源控制")
        src_layout = QGridLayout(src_group)
        src_layout.setContentsMargins(5, 10, 5, 10)
        src_layout.setVerticalSpacing(8)  # 减小行间距
        src_layout.setHorizontalSpacing(6)  # 减小列间距
        
        # 第一行 - 频率设置
        src_layout.addWidget(QLabel("信号频率:"), 0, 0)
        src_layout.addWidget(self.freq_input, 0, 1, 1, 2)
        src_layout.addWidget(self.freq_btn, 0, 3)
        src_layout.addWidget(self.freq_query_btn, 0, 4)
        
        # 第二行 - 功率设置
        src_layout.addWidget(QLabel("馈源功率:"), 1, 0)
        src_layout.addWidget(self.power_input, 1, 1)
        src_layout.addWidget(self.raw_power_input, 1, 2)
        src_layout.addWidget(self.power_btn, 1, 3)
        src_layout.addWidget(self.power_query_btn, 1, 4)
        
        # 第三行 - RF输出
        src_layout.addWidget(QLabel("RF输出:"), 2, 0)
        src_layout.addWidget(self.output_combo, 2, 1, 1, 2)
        src_layout.addWidget(self.output_btn, 2, 3)
        src_layout.addWidget(self.output_query_btn, 2, 4)
        
        right_panel.addWidget(src_group)
        
        # 运动控制 - 紧凑网格布局
        self.motion_group = QGroupBox("运动控制")
        motion_layout = QGridLayout(self.motion_group)
        motion_layout.setContentsMargins(5, 10, 5, 10)
        motion_layout.setVerticalSpacing(8)
        motion_layout.setHorizontalSpacing(6)
        
        # 第一行 - 复位
        motion_layout.addWidget(QLabel("复位:"), 0, 0)
        motion_layout.addWidget(self.home_combo, 0, 1)
        motion_layout.addWidget(self.home_btn, 0, 2)
        motion_layout.addWidget(self.home_query_btn, 0, 3)
        
        # 第二行 - 达位
        motion_layout.addWidget(QLabel("达位:"), 1, 0)
        motion_layout.addWidget(self.feed_combo, 1, 1)
        motion_layout.addWidget(self.feed_btn, 1, 2)
        motion_layout.addWidget(self.feed_query_btn, 1, 3)
        
        # 第三行 - 速度
        motion_layout.addWidget(QLabel("速度:"), 2, 0)
        motion_layout.addWidget(self.speed_mod_combo, 2, 1)
        motion_layout.addWidget(self.speed_combo, 2, 2)
        motion_layout.addWidget(self.speed_btn, 2, 3)
        motion_layout.addWidget(self.speed_query_btn, 2, 4)
        
        right_panel.addWidget(self.motion_group)
        
        main_layout.addLayout(right_panel, stretch=3)
        
        # 设置中央控件布局
        layout = QVBoxLayout(self.central_widget)
        layout.setContentsMargins(8, 8, 8, 8)  # 减小主窗口内边距
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
                return
        
        print("警告: 使用嵌入式默认样式")
        self.setStyleSheet("QMainWindow { background: #f0f0f0; }")

    def log(self, message, level="INFO"):
        """记录日志"""
        self.log_output.log(message, level)

    def show_status(self, message):
        """在状态栏显示消息"""
        self.status_bar.showMessage(message)



