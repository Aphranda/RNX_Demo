from PyQt5.QtWidgets import QWidget, QVBoxLayout
from .View import StatusPanelView
from .Model import StatusPanelModel
from .Controller import StatusPanelController

class StatusPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # MVC组件初始化
        self._view = StatusPanelView()
        self._model = StatusPanelModel()
        self._controller = StatusPanelController(self._view, self._model)
        # 设置日志回调
        if hasattr(parent, 'log'):
            self._controller.set_log_callback(parent.log)
        
        # 设置布局
        layout = QVBoxLayout(self)
        layout.addWidget(self._view)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 暴露常用信号
        self.cal_file_loaded = self._controller.cal_file_loaded

    # 兼容旧版API
    @property
    def motion_label(self):
        return self._view.motion_label

    @property
    def src_label(self):
        return self._view.src_label

    def update_motion_status(self, status: dict):
        self._controller.update_motion_status(status)

    def update_src_status(self, status: dict):
        self._controller.update_src_status(status)

    def update_operation_status(self, operation: str, axis: str):
        """更新操作状态显示"""
        self._controller.update_operation_status(operation, axis)

    # 属性访问器
    @property
    def current_cal_file(self) -> str:
        return self._model.src_status['cal_file']

    @property
    def current_freq_unit(self) -> str:
        return self._model.units['freq']

    @property
    def load_cal_btn(self):
        return self._view.load_cal_btn

    @property
    def cal_file_input(self):
        return self._view.cal_file_input

    @property
    def power_unit_combo(self):
        return self._view.power_unit_combo
 
    @property
    def raw_power_unit_combo(self):
        return self._view.raw_power_unit_combo
 
    @property
    def freq_unit_combo(self):
        return self._view.freq_unit_combo
 
    @property
    def unit_converter(self):
        return self._model.unit_converter
    
    def set_cal_file_style(self, text: str, state: str):
        self._controller.set_cal_file_style(text, state)
