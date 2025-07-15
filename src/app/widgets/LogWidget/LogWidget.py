from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal
from .View import LogWidgetView
from .Controller import LogWidgetController

class LogWidget(QWidget):
    """整合后的日志控件，组合视图和控制器"""
    
    errorLogged = pyqtSignal(str)  # 保持与旧版兼容的信号

    def __init__(self, parent=None, max_lines=5000, default_level="ALL"):
        super().__init__(parent)
        
        # 创建视图和控制器
        self.view = LogWidgetView(self)
        self.controller = LogWidgetController(self.view)
        
        # 设置初始参数
        self.controller.max_lines = max_lines
        self.controller._update_log_level(default_level)
        
        # 转发信号
        self.controller.error_logged.connect(self.errorLogged)
        
        # 设置布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    # -------------------- 公共接口 --------------------
    def log(self, message, level="INFO"):
        """记录日志"""
        self.controller.log(message, level)

    def clear(self):
        """清空日志"""
        self.controller.clear()

    def set_max_lines(self, max_lines):
        """设置最大日志行数"""
        self.controller.set_max_lines(max_lines)

    def set_auto_scroll(self, enabled):
        """设置是否自动滚动到底部"""
        self.controller.set_auto_scroll(enabled)
