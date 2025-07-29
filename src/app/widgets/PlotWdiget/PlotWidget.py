from .View import PlotView
from .Model import PlotModel
from .Controller import PlotController
from PyQt5.QtWidgets import QWidget, QVBoxLayout

class PlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = PlotModel()
        self._view = PlotView()
        self.controller = PlotController(self._model, self._view)

        # 控制器与视图连接
        # Set up layout
        layout = QVBoxLayout(self)
        layout.addWidget(self._view)
        layout.setContentsMargins(0, 0, 0, 0)

    def set_series_visibility(self, name, visible):
        """设置系列可见性"""
        self._view.set_series_visibility(name, visible)
        
    def plot_calibration_data(self, file_path=None):
        """绘制校准数据"""
        self.controller.load_and_plot(file_path)
    
    def plot_merged_data(self, data_dict, title="合并校准数据"):
        """绘制合并后的校准数据"""
        self.controller.plot_merged_data(data_dict, title)
    
    def clear_plot(self):
        """清除图表"""
        # 直接调用视图的清除方法
        self._view.clear_plot()
