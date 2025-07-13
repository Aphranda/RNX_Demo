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



class StatusPanel(QWidget):
    def __init__(self, SignalUnitConverter, child_control, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(240)
        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(18, 5, 18, 5)
        h_layout.setSpacing(10)

        # 单位换算实例化
        self.unit_converter = SignalUnitConverter
        AutoFontSizeLabel = child_control["Lable"]
        AutoFontSizeComboBox = child_control["ComboBox"]


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
