# app/widgets/CalibrationPanel/View.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QLabel, QPushButton, QDoubleSpinBox, QProgressBar, 
    QFormLayout, QLineEdit, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon,QColor
from pathlib import Path

class CalibrationView(QWidget):
    def __init__(self):
        super().__init__()

        # 状态颜色定义
        self._status_colors = {
            'connected': QColor(0, 180, 0),    # 绿色
            'disconnected': QColor(180, 0, 0), # 红色
            'detecting': QColor(255, 165, 0),  # 橙色
            'error': QColor(255, 0, 0),       # 红色
            'default': QColor(0, 0, 0)        # 黑色
        }
        
        self._init_ui_components()
        self._setup_ui_layout()
        self._setup_window_properties()


    def _setup_window_properties(self):
        """只设置窗口显示属性"""
        self.setWindowTitle("RNX 校准工具")
        self.setWindowFlags(
            Qt.Window | 
            Qt.CustomizeWindowHint |
            Qt.WindowTitleHint |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowCloseButtonHint
        )
        self.setFixedSize(700, 900)  # 增加高度以容纳新控件
        
        # 设置窗口图标
        icon_path = "src/resources/icons/icon_calibration.png"
        if Path(icon_path).exists():
            self.setWindowIcon(QIcon(icon_path))

    def _init_ui_components(self):
        """初始化所有UI组件"""
        # 设备状态
        self.device_group = QGroupBox("设备状态")
        self.power_meter_status = QLabel("功率计: 未连接")
        self.signal_gen_status = QLabel("信号源: 未连接")

        self.antenna_model = QLineEdit("RNX_ANT")
        self.antenna_model.setPlaceholderText("天线型号")
        self.antenna_sn = QLineEdit("SN00000")
        self.antenna_sn.setPlaceholderText("天线序列号")
        
        # 仪器连接
        self.instr_group = QGroupBox("仪器连接")
        self.signal_gen_name = QLineEdit("PLASG")  # 新增信号源名称输入
        self.signal_gen_name.setPlaceholderText("信号源型号(如PLASG)")
        self.power_meter_name = QLineEdit("NRP50S")  # 新增功率计名称输入
        self.power_meter_name.setPlaceholderText("功率计型号(如NRP50S)")
        self.signal_gen_address = QLineEdit("TCPIP0::192.168.1.10::inst0::INSTR")
        self.power_meter_address = QLineEdit("TCPIP0::192.168.1.11::inst0::INSTR")
        self.btn_connect = QPushButton("连接仪器")
        self.btn_auto_detect = QPushButton("自动检测仪器")
        
        # 频率模式选择
        self.mode_group = QGroupBox("频率模式")
        self.range_mode = QRadioButton("频率范围模式")
        self.list_mode = QRadioButton("频点列表模式")
        self.range_mode.setChecked(True)
        self.mode_button_group = QButtonGroup()
        self.mode_button_group.addButton(self.range_mode)
        self.mode_button_group.addButton(self.list_mode)
        
        # 校准参数
        self.param_group = QGroupBox("校准参数")
        self.start_freq = QDoubleSpinBox()
        self.stop_freq = QDoubleSpinBox()
        self.step_freq = QDoubleSpinBox()
        self.ref_power = QDoubleSpinBox()
        
        # 频点列表控件
        self.freq_list_group = QGroupBox("频点列表")
        self.freq_list_info = QLabel("未导入频点列表")
        self.btn_import = QPushButton("导入频点列表")
        self.btn_import.setEnabled(True)
        
        # 控制按钮
        self.btn_start = QPushButton("开始校准")
        self.btn_stop = QPushButton("终止")
        self.btn_export = QPushButton("导出数据")
        
        # 进度显示
        self.progress_bar = QProgressBar()
        self.current_step = QLabel("准备就绪")

        # 初始化默认值
        self._init_default_values()

    def _init_default_values(self):
        """设置UI组件默认值"""
        self.start_freq.setRange(0.1, 40)
        self.start_freq.setValue(8.0)
        self.stop_freq.setRange(0.1, 40)
        self.stop_freq.setValue(40.0)
        self.step_freq.setRange(0.01, 1)
        self.step_freq.setValue(0.01)
        self.ref_power.setRange(-50, 10)
        self.ref_power.setValue(-30.0)
        self.progress_bar.setRange(0, 100)

    def _setup_ui_layout(self):
        """设置UI布局"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        
        # 设备状态布局
        device_layout = QVBoxLayout()
        device_layout.addWidget(self.power_meter_status)
        device_layout.addWidget(self.signal_gen_status)
        self.device_group.setLayout(device_layout)

        # 仪器连接布局
        instr_layout = QFormLayout()
        instr_layout.addRow("信号源型号:", self.signal_gen_name)  # 新增行
        instr_layout.addRow("信号源地址:", self.signal_gen_address)
        instr_layout.addRow("功率计型号:", self.power_meter_name)  # 新增行
        instr_layout.addRow("功率计地址:", self.power_meter_address)

        # 在仪器连接布局中添加天线信息行
        instr_layout.addRow("天线型号:", self.antenna_model)
        instr_layout.addRow("天线序列号:", self.antenna_sn)
        instr_layout.addRow(self.btn_connect)
        instr_layout.addRow(self.btn_auto_detect)
        self.instr_group.setLayout(instr_layout)
        
        # 频率模式布局
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.range_mode)
        mode_layout.addWidget(self.list_mode)
        self.mode_group.setLayout(mode_layout)
        
        # 参数布局
        param_layout = QFormLayout()
        param_layout.addRow("起始频率 (GHz):", self.start_freq)
        param_layout.addRow("终止频率 (GHz):", self.stop_freq)
        param_layout.addRow("步进 (GHz):", self.step_freq)
        param_layout.addRow("参考功率 (dBm):", self.ref_power)
        self.param_group.setLayout(param_layout)
        
        # 频点列表布局
        freq_list_layout = QVBoxLayout()
        freq_list_layout.addWidget(self.freq_list_info)
        freq_list_layout.addWidget(self.btn_import)
        self.freq_list_group.setLayout(freq_list_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_start)
        button_layout.addWidget(self.btn_stop)
        button_layout.addWidget(self.btn_export)
        
        # 主布局
        self.main_layout.addWidget(self.device_group)
        self.main_layout.addWidget(self.instr_group)
        self.main_layout.addWidget(self.mode_group)
        self.main_layout.addWidget(self.param_group)
        self.main_layout.addWidget(self.freq_list_group)
        self.main_layout.addLayout(button_layout)
        self.main_layout.addWidget(self.progress_bar)
        self.main_layout.addWidget(self.current_step)
        
        # 初始状态
        self._update_mode_visibility()

    def _update_mode_visibility(self):
        """根据选择的模式显示/隐藏相关控件"""
        is_range_mode = self.range_mode.isChecked()
        self.param_group.setVisible(is_range_mode)
        self.freq_list_group.setVisible(not is_range_mode)
