
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QStatusBar, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout, 
    QSizePolicy, QMessageBox, QCheckBox, QToolBar, QAction, QFileDialog
)
from PyQt5.QtCore import Qt, QMutex, QFile,QTextStream
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtCore import QRegExp
import sys, os
from pathlib import Path  # 必须添加这行导入

from .widgets.AutoFontSizeComboBox import AutoFontSizeComboBox
from .widgets.AutoFontSizeLabel import AutoFontSizeLabel
from .widgets.LogWidget import LogWidget
from .widgets.SimpleLinkDiagram import SimpleLinkDiagram
from .widgets.StatusPanel import StatusPanel
from .threads.StatusQueryThread import StatusQueryThread

from app.utils import SignalUnitConverter

class MainWindow(QMainWindow):
    def __init__(self, Communicator, SignalUnitConverter, CalibrationFileManager):
        super().__init__()
        self.setWindowTitle("RNX Quantum Antenna Test System - Demo")
        self.setGeometry(50, 40, 1800, 1100)
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        #引入样式表
        self.load_stylesheet()

        # 子控件实例化
        self.autoFontSizeLabel = AutoFontSizeLabel
        self.autoFontSizeComboBox = AutoFontSizeComboBox

        self.child_control = {
            "Lable":self.autoFontSizeLabel,
            "ComboBox":self.autoFontSizeComboBox
        }


        # 初始化外部类
        self.tcp_client = Communicator
        self.unit_converter = SignalUnitConverter
        self.calibrationFileManager = CalibrationFileManager

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
    
    def load_stylesheet(self):
        # 自动探测可能的资源位置
        search_paths = [
            # 开发模式路径（PyCharm/VSCode直接运行）
            "src/resources/styles/main_window.qss",
            # 打包后路径
            "resources/styles/main_window.qss",
            # 资源系统路径
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
        self.status_panel = StatusPanel(self.unit_converter, self.child_control)
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
            self.cal_manager = self.calibrationFileManager(log_callback=self.log)
    
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



