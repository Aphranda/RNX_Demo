from PyQt5.QtWidgets import QWidget,QVBoxLayout
from .View import StatusPanelView
from .Model import StatusPanelModel
from .Controller import StatusPanelController

class StatusPanel(QWidget):
    """
    状态面板主类（兼容旧接口的MVC封装）
    保留原始文件名作为模块入口，内部实现MVC分离
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # MVC组件初始化
        self._view = StatusPanelView()
        self._model = StatusPanelModel()
        self._controller = StatusPanelController(self._view, self._model)
        
        # 设置布局（保持原始结构）
        layout = QVBoxLayout(self)
        layout.addWidget(self._view)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 暴露常用信号
        self.cal_file_loaded = self._controller.cal_file_loaded

    # 兼容旧版API --------------------------------------------------
    @property
    def motion_label(self):
        """兼容旧代码的运动模组标签访问"""
        return self._view.motion_label

    @property
    def src_label(self):
        """兼容旧代码的信号源标签访问"""
        return self._view.src_label

    def update_motion_status(self, axis: str, status: dict):
        """
        更新运动模组状态（兼容旧接口）
        :param axis: 轴名称 (X/KU/K/KA/Z)
        :param status: 状态字典 {reach: str, home: str, speed: str}
        """
        self._controller.update_motion_status(axis, status)

    def update_src_status(self, status: dict):
        """
        更新信号源状态（兼容旧接口）
        :param status: 状态字典 {
            freq: str, 
            raw_power: str, 
            power: str, 
            rf: str,
            cal_file: str
        }
        """
        self._controller.update_src_status(status)

    # 新增便捷访问器 -----------------------------------------------
    @property
    def current_cal_file(self) -> str:
        """获取当前校准文件路径"""
        return self._model.src_status['cal_file']

    @property
    def current_freq_unit(self) -> str:
        """获取当前频率单位"""
        return self._model.units['freq']

    # 保留原始UI元素访问（根据需要暴露）
    @property
    def load_cal_btn(self):
        """加载校准按钮（兼容旧代码）"""
        return self._view.load_cal_btn

    @property
    def cal_file_input(self):
        """校准文件输入框（兼容旧代码）"""
        return self._view.cal_file_input
    
    def set_cal_file_style(self, text: str, state: str):
        """设置校准文件状态样式（新推荐方式）"""
        self._controller.set_cal_file_style(text, state)
