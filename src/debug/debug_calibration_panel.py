# debug/debug_calibration_panel.py
import sys
import os
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
print("PATH:",sys.path)

# 现在可以使用绝对路径导入
from src.app.widgets.CalibrationPanel.CalibrationPanel import CalibrationPanel


def main():
    app = QApplication(sys.argv)
    
    # 主窗口设置
    window = QWidget()
    window.setWindowTitle("校准面板调试窗口")
    window.resize(800, 600)
    
    # 创建校准面板
    panel = CalibrationPanel(window)  # 注意这里修改了，直接使用类名
    
    # 设置布局
    layout = QVBoxLayout(window)
    layout.addWidget(panel)
    window.setLayout(layout)
    
    # 模拟设备连接状态
    def simulate_connection():
        panel.update_instrument_status('signal_gen', '信号源: 已连接 (NRP-50S)', True)
        panel.update_instrument_status('power_meter', '功率计: 已连接 (NRP-50S)', True)
    
    from PyQt5.QtCore import QTimer
    QTimer.singleShot(1000, simulate_connection)
    
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
