from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QStatusBar, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout, 
    QSizePolicy, QMessageBox, QCheckBox, QToolBar, QAction, QFileDialog
)
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QFontMetrics, QTextCursor, QTextCharFormat, QIcon
from PyQt5.QtCore import Qt, QPointF, QThread, pyqtSignal, QMutex
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


from app.core.tcp_client import TcpClient
from app.main_window import MainWindow
from app.utils.ProcessManager import ProcessManager
from app.utils.SignalUnitConverter import SignalUnitConverter
from app.controllers.CalibrationFileManager import CalibrationFileManager



if __name__ == "__main__":
    # 先检查是否已有实例运行
    process_mgr = ProcessManager()
    if process_mgr.check_duplicate_instance():
        sys.exit(1)
    
    communicator = TcpClient()
    unit_converter = SignalUnitConverter()
    calibrationFileManager = CalibrationFileManager
    
    # 正常启动主程序
    app = QApplication(sys.argv)
    
    # 设置应用程序名称（用于任务管理器识别）
    app.setApplicationName("RNX Quantum Antenna Test System")
    app.setApplicationDisplayName("RNX量子天线测试系统")
    
    # # 加载样式表
    # with open("style.qss", "r", encoding="utf-8") as f:
    #     app.setStyleSheet(f.read())
    
    window = MainWindow(communicator,unit_converter,calibrationFileManager)
    window.show()
    sys.exit(app.exec_())