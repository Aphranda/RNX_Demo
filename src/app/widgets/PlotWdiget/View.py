from pathlib import Path
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QValueAxis, QSplineSeries
from PyQt5.QtCore import Qt, pyqtSignal, QPointF
from PyQt5.QtGui import QColor, QPen, QPainter, QFont
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QFrame, QScrollArea, QWidget, QToolBar, QAction, 
                            QSizePolicy, QFileDialog, QMessageBox, QCheckBox, QGraphicsSimpleTextItem)

class PlotView(QWidget):

    series_visibility_changed = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置窗口属性
        self.setMinimumSize(800, 600)
        self.setWindowTitle("RNX 校准数据绘图")
        
        # 创建工具栏
        self.toolbar = QToolBar("绘图工具栏")
        self.toolbar.setMovable(False)
        
        # 添加工具栏按钮
        self.import_action = QAction("导入文件", self)
        self.import_action.setStatusTip("从CSV文件导入校准数据")
        
        self.clear_action = QAction("清除图表", self)
        self.clear_action.setStatusTip("清除所有数据系列")
        
        self.toolbar.addAction(self.import_action)
        self.toolbar.addAction(self.clear_action)
        
        # 创建图表和视图
        self.chart = QChart()
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        self.chart.setTheme(QChart.ChartThemeLight)
        
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 设置布局
        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.chart_view)
        
        
        # 初始化坐标轴
        self.axis_x = QValueAxis()
        self.axis_y = QValueAxis()
        self.chart.addAxis(self.axis_x, Qt.AlignBottom)
        self.chart.addAxis(self.axis_y, Qt.AlignLeft)
        
        # 存储系列对象
        self.series = {}

        # 创建复选框容器
        self.checkbox_container = QFrame()
        self.checkbox_layout = QHBoxLayout()
        self.checkbox_container.setLayout(self.checkbox_layout)
        
        # 添加滚动区域
        scroll = QScrollArea()
        scroll.setWidget(self.checkbox_container)
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(60)
        scroll.setFrameShape(QFrame.NoFrame)
        
        # 修改布局
        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(scroll)  # 添加复选框滚动区域
        layout.addWidget(self.chart_view)
        self.setLayout(layout)
        
        # 存储复选框
        self.series_checkboxes = {}

        # 添加十字线和坐标显示相关成员变量
        self.crosshair_v = None
        self.crosshair_h = None
        self.coord_label = None
        self._crosshair_initialized = False
        
        # 设置鼠标跟踪
        self.chart_view.setMouseTracking(True)
        self.chart_view.scene().installEventFilter(self)

    def ensure_crosshair_initialized(self):
        """确保十字线已初始化"""
        if not self._crosshair_initialized:
            self.init_crosshair()
            self._crosshair_initialized = True
        
    def init_crosshair(self):
        """初始化十字线"""
        # 垂直线
        self.crosshair_v = QLineSeries()
        self.crosshair_v.setPen(QPen(Qt.gray, 1, Qt.DashLine))
        self.chart.addSeries(self.crosshair_v)
        self.crosshair_v.attachAxis(self.axis_x)
        self.crosshair_v.attachAxis(self.axis_y)
        self.crosshair_v.setVisible(False)
        
        # 水平线
        self.crosshair_h = QLineSeries()
        self.crosshair_h.setPen(QPen(Qt.gray, 1, Qt.DashLine))
        self.chart.addSeries(self.crosshair_h)
        self.crosshair_h.attachAxis(self.axis_x)
        self.crosshair_h.attachAxis(self.axis_y)
        self.crosshair_h.setVisible(False)
        
        # 坐标标签
        self.coord_label = QGraphicsSimpleTextItem(self.chart)
        self.coord_label.setFont(QFont("Arial", 8))
        self.coord_label.setBrush(Qt.black)
        self.coord_label.setVisible(False)
        # 设置Z值为最高
        self.coord_label.setZValue(1000)
    
    def eventFilter(self, obj, event):
        """处理鼠标移动事件，显示十字线和坐标"""
        if obj is self.chart_view.scene():
            if event.type() == event.GraphicsSceneMouseMove:
                # 确保十字线已初始化
                self.ensure_crosshair_initialized()
                
                # 获取鼠标位置
                mouse_pos = event.scenePos()
                chart_pos = self.chart_view.mapFromScene(mouse_pos)
                value_pos = self.chart.mapToValue(chart_pos)
                
                # 检查是否在图表区域内
                if self.chart.plotArea().contains(chart_pos):
                    # 更新十字线位置
                    self.update_crosshair(value_pos.x(), value_pos.y())
                    
                    # 更新坐标标签
                    self.update_coord_label(value_pos.x(), value_pos.y(), chart_pos)
                    
                    # 显示十字线和标签
                    self.crosshair_v.setVisible(True)
                    self.crosshair_h.setVisible(True)
                    self.coord_label.setVisible(True)
                    
        return super().eventFilter(obj, event)
    
    def update_crosshair(self, x, y):
        """更新十字线位置"""
        if self.crosshair_v is None or self.crosshair_h is None:
            return
            
        # 获取Y轴范围
        y_min, y_max = self.axis_y.min(), self.axis_y.max()
        # 获取X轴范围
        x_min, x_max = self.axis_x.min(), self.axis_x.max()
        
        # 更新垂直线 (x固定，y从最小到最大)
        self.crosshair_v.clear()
        self.crosshair_v.append(x, y_min)
        self.crosshair_v.append(x, y_max)
        
        # 更新水平线 (y固定，x从最小到最大)
        self.crosshair_h.clear()
        self.crosshair_h.append(x_min, y)
        self.crosshair_h.append(x_max, y)
    
    def update_coord_label(self, x, y, chart_pos):
        """更新坐标标签位置和文本"""
        if self.coord_label is None:
            return
            
        # 设置标签文本
        self.coord_label.setText(f"X: {x:.3f}, Y: {y:.3f}")
        
        # 计算标签位置 (鼠标位置右侧10像素)
        label_pos = QPointF(chart_pos.x() + 10, chart_pos.y())
        scene_pos = self.chart_view.mapToScene(label_pos.toPoint())
        
        # 确保标签不会超出图表区域
        plot_area = self.chart.plotArea()
        text_width = self.coord_label.boundingRect().width()
        text_height = self.coord_label.boundingRect().height()
        
        if scene_pos.x() + text_width > plot_area.right():
            scene_pos.setX(plot_area.right() - text_width - 5)
        if scene_pos.y() + text_height > plot_area.bottom():
            scene_pos.setY(plot_area.bottom() - text_height - 5)
        
        self.coord_label.setPos(scene_pos)
    
    def clear_plot(self):
        """清除所有图表数据"""
        # 隐藏十字线和标签
        if hasattr(self, 'crosshair_v') and self.crosshair_v is not None:
            self.crosshair_v.setVisible(False)
        if hasattr(self, 'crosshair_h') and self.crosshair_h is not None:
            self.crosshair_h.setVisible(False)
        if hasattr(self, 'coord_label') and self.coord_label is not None:
            self.coord_label.setVisible(False)
        
        # 原有的清除代码
        self.chart.removeAllSeries()
        self.series = {}
        self._crosshair_initialized = False
        self.crosshair_v = None
        self.crosshair_h = None
        self.coord_label = None
        
        # 重置坐标轴范围
        self.axis_x.setRange(0, 40)  # 默认频率范围
        self.axis_y.setRange(-100, 0)  # 默认dB范围


    def plot_data(self, data, title="校准数据", x_label="频率 (GHz)", y_label="值"):
        """绘制校准数据曲线"""
        # 清除现有复选框
        for i in reversed(range(self.checkbox_layout.count())): 
            self.checkbox_layout.itemAt(i).widget().setParent(None)
        self.series_checkboxes = {}
        self.chart.removeAllSeries()
        self.series = {}
        
        # 设置图表标题和坐标轴标签
        self.chart.setTitle(title)
        self.axis_x.setTitleText(x_label)
        self.axis_y.setTitleText(y_label)
        
        # 颜色预设
        colors = [
            QColor(65, 105, 225),  # RoyalBlue
            QColor(220, 20, 60),   # Crimson
            QColor(46, 139, 87),   # SeaGreen
            QColor(255, 140, 0),   # DarkOrange
            QColor(148, 0, 211),   # DarkViolet
            QColor(0, 191, 255),   # DeepSkyBlue
            QColor(255, 215, 0),   # Gold
            QColor(0, 128, 128),   # Teal
        ]
        
        # 添加数据系列
        min_x, max_x = float('inf'), float('-inf')
        min_y, max_y = float('inf'), float('-inf')
        
        for i, (name, points) in enumerate(data.items()):
            # 跳过空系列
            if not points:
                continue
                
            # 使用QSplineSeries代替QLineSeries实现平滑曲线
            series = QSplineSeries()  # 修改为使用平滑曲线系列
            series.setName(name)
            
            # 添加数据点
            for freq, value in points:
                series.append(freq, value)
                min_x = min(min_x, freq)
                max_x = max(max_x, freq)
                min_y = min(min_y, value)
                max_y = max(max_y, value)
            
            # 设置线条样式
            pen = QPen(colors[i % len(colors)], 2.5)
            series.setPen(pen)
            
            self.chart.addSeries(series)
            series.attachAxis(self.axis_x)
            series.attachAxis(self.axis_y)
            self.series[name] = series
        
        # 设置坐标轴范围（确保有有效数据）
        if min_x != float('inf') and max_x != float('-inf'):
            x_padding = (max_x - min_x) * 0.05
            self.axis_x.setRange(min_x - x_padding, max_x + x_padding)
        
        if min_y != float('inf') and max_y != float('-inf'):
            y_padding = (max_y - min_y) * 0.1
            self.axis_y.setRange(min_y - y_padding, max_y + y_padding)

        for name in data.keys():
            checkbox = QCheckBox(name)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(
                lambda state, n=name: self.series_visibility_changed.emit(n, state == Qt.Checked)
            )
            self.series_checkboxes[name] = checkbox
            self.checkbox_layout.addWidget(checkbox)
        self.update_axes_range()

    def set_series_visibility(self, name, visible):
        """设置系列可见性并更新坐标轴范围"""
        if name in self.series:
            self.series[name].setVisible(visible)
            if name in self.series_checkboxes:
                self.series_checkboxes[name].setChecked(visible)
        
        # 更新坐标轴范围
        self.update_axes_range()
    
    def update_axes_range(self):
        """根据可见系列更新坐标轴范围"""
        min_x, max_x = float('inf'), float('-inf')
        min_y, max_y = float('inf'), float('-inf')
        
        # 只考虑可见的系列
        for name, series in self.series.items():
            if series.isVisible() and series.count() > 0:
                # 获取系列中的数据范围
                points = [series.at(i) for i in range(series.count())]
                x_values = [p.x() for p in points]
                y_values = [p.y() for p in points]
                
                min_x = min(min_x, min(x_values))
                max_x = max(max_x, max(x_values))
                min_y = min(min_y, min(y_values))
                max_y = max(max_y, max(y_values))
        
        # 如果有可见数据，则更新坐标轴范围
        if min_x != float('inf') and max_x != float('-inf'):
            x_padding = (max_x - min_x) * 0.05
            self.axis_x.setRange(min_x - x_padding, max_x + x_padding)
        
        if min_y != float('inf') and max_y != float('-inf'):
            y_padding = (max_y - min_y) * 0.1
            self.axis_y.setRange(min_y - y_padding, max_y + y_padding)
        else:
            # 如果没有可见数据，设置默认范围
            self.axis_y.setRange(-100, 0)

    def show_error(self, message):
        """显示错误消息"""
        QMessageBox.critical(self, "导入错误", message)

  
