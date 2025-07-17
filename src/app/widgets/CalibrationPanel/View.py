# app/widgets/CalibrationPanel/View.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QLabel, QPushButton, QDoubleSpinBox, QProgressBar
)
from PyQt5.QtCore import Qt

class CalibrationView(QWidget):
    def __init__(self):
        super().__init__()
        
        # 设备状态区域
        self.device_group = QGroupBox("设备状态")
        self.power_meter_status = QLabel("功率计: 未连接")
        self.signal_gen_status = QLabel("信号源: 未连接")
        
        # 校准参数设置
        self.param_group = QGroupBox("校准参数")
        self.start_freq = QDoubleSpinBox()
        self.stop_freq = QDoubleSpinBox()
        self.step_freq = QDoubleSpinBox()
        self.ref_power = QDoubleSpinBox()
        
        # 控制按钮
        self.btn_start = QPushButton("开始校准")
        self.btn_stop = QPushButton("终止")
        self.btn_export = QPushButton("导出数据")
        
        # 进度显示
        self.progress_bar = QProgressBar()
        self.current_step = QLabel("准备就绪")
        
        self._setup_ui()

    def _setup_ui(self):
        # 设备状态布局
        device_layout = QVBoxLayout()
        device_layout.addWidget(self.power_meter_status)
        device_layout.addWidget(self.signal_gen_status)
        self.device_group.setLayout(device_layout)

        # 参数表格布局
        param_layout = QFormLayout()
        param_layout.addRow("起始频率 (GHz):", self.start_freq)
        param_layout.addRow("终止频率 (GHz):", self.stop_freq)
        param_layout.addRow("步进 (MHz):", self.step_freq)
        param_layout.addRow("参考功率 (dBm):", self.ref_power)
        self.param_group.setLayout(param_layout)

        # 按钮组
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_start)
        button_layout.addWidget(self.btn_stop)
        button_layout.addWidget(self.btn_export)

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.device_group)
        main_layout.addWidget(self.param_group)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.current_step)
        
        self.setLayout(main_layout)
        self._init_values()

    def _init_values(self):
        # 初始化默认值
        self.start_freq.setRange(0.1, 40)
        self.start_freq.setValue(1.0)
        self.stop_freq.setRange(0.1, 40)
        self.stop_freq.setValue(10.0)
        self.step_freq.setRange(1, 1000)
        self.step_freq.setValue(100)
        self.ref_power.setRange(-50, 10)
        self.ref_power.setValue(-10.0)
