from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, 
    QGroupBox, QLineEdit, QPushButton, QSizePolicy
)
from widgets.AutoFontSizeComboBox import AutoFontSizeComboBox
from widgets.AutoFontSizeLabel import AutoFontSizeLabel
from PyQt5.QtCore import Qt

class StatusPanelView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setMinimumWidth(240)
        self.h_layout = QHBoxLayout(self)
        self.h_layout.setContentsMargins(18, 5, 18, 5)
        self.h_layout.setSpacing(10)

        # 运动模组状态
        self.setup_motion_group()
        # 信号源状态
        self.setup_src_group()

        self.motion_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.src_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        self.h_layout.addWidget(self.motion_group, stretch=1)
        self.h_layout.addWidget(self.src_group, stretch=1)

    def setup_motion_group(self):
        self.motion_group = QGroupBox("运动模组状态")
        motion_layout = QVBoxLayout(self.motion_group)
        self.motion_label = QLabel("")
        self.motion_label.setProperty("panelTitle", True)
        motion_layout.addWidget(self.motion_label)

        self.motion_grid = QGridLayout()
        self.motion_grid.setSpacing(6)
        self.motion_grid.setVerticalSpacing(6)
        motion_layout.addLayout(self.motion_grid)
        
        # 运动模组表格
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
            self.motion_reach[axis].setMinimumHeight(20)
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

    def setup_src_group(self):
        self.src_group = QGroupBox("信号源状态")
        src_layout = QVBoxLayout(self.src_group)
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
        self.src_grid.addWidget(self.freq_unit_combo, 0, 2)

        # 信号源功率信息
        self.src_grid.addWidget(QLabel("信号功率:"), 1, 0)
        self.src_raw_power = AutoFontSizeLabel()
        self.src_raw_power.setProperty("statusValue", True)
        self.src_grid.addWidget(self.src_raw_power, 1, 1)

        # 功率单位下拉框
        self.raw_power_unit_combo = AutoFontSizeComboBox()
        self.src_grid.addWidget(self.raw_power_unit_combo, 1, 2)

        self.src_grid.addWidget(QLabel("馈源功率:"), 2, 0)
        self.src_power = AutoFontSizeLabel()
        self.src_power.setProperty("statusValue", True)
        self.src_grid.addWidget(self.src_power, 2, 1)

        # 馈源功率单位下拉框
        self.power_unit_combo = AutoFontSizeComboBox()
        self.src_grid.addWidget(self.power_unit_combo, 2, 2)

        self.src_grid.addWidget(QLabel("RF输出:"), 3, 0)
        self.src_rf = AutoFontSizeLabel()
        self.src_rf.setProperty("statusValue", True)
        self.src_grid.addWidget(self.src_rf, 3, 1)

        # 校准文件状态
        self.cal_file_status = AutoFontSizeLabel("Calib Miss")
        self.cal_file_status.setProperty("AutoScale", True)
        self.cal_file_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.src_grid.addWidget(self.cal_file_status, 3, 2)
        
        # 校准文件路径输入和加载按钮
        self.src_grid.addWidget(QLabel("校准路径:"), 5, 0)
        self.cal_file_input = QLineEdit()
        self.cal_file_input.setPlaceholderText("选择校准文件...")
        self.src_grid.addWidget(self.cal_file_input, 5, 1)
        
        self.load_cal_btn = QPushButton("加载")
        self.src_grid.addWidget(self.load_cal_btn, 5, 2)

        src_layout.addStretch()
        
    def apply_style(self, element: str):
            """应用指定元素的样式"""
            style_data = self.controller.model.style_status.get(element)
            if not style_data:
                return
                
            widget = getattr(self, element, None)
            if widget:
                widget.setText(style_data['text'])
                widget.setStyleSheet(style_data['style'])