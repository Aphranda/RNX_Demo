from PyQt5.QtWidgets import (
    QApplication
)
from PyQt5.QtCore import QDir
import sys


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

    # 初始化资源系统
    QDir.addSearchPath('resources', 'resources')  # 添加资源搜索路径
    
    # 设置应用程序名称（用于任务管理器识别）
    app.setApplicationName("RNX Quantum Antenna Test System")
    app.setApplicationDisplayName("RNX量子天线测试系统")
    
    window = MainWindow(communicator,unit_converter,calibrationFileManager)
    window.show()
    sys.exit(app.exec_())