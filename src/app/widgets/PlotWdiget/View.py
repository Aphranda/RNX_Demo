from pathlib import Path
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QValueAxis, QSplineSeries
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPen, QPainter
from PyQt5.QtWidgets import (QVBoxLayout, QWidget, QToolBar, QAction, 
                            QSizePolicy, QFileDialog, QMessageBox)

class PlotView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置窗口属性
        self.setMinimumSize(800, 600)
        self.setWindowTitle("RNX 校准数据绘图")

        # self._load_stylesheet()
        
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
        self.setLayout(layout)
        
        # 初始化坐标轴
        self.axis_x = QValueAxis()
        self.axis_y = QValueAxis()
        self.chart.addAxis(self.axis_x, Qt.AlignBottom)
        self.chart.addAxis(self.axis_y, Qt.AlignLeft)
        
        # 存储系列对象
        self.series = {}
    
    def plot_data(self, data, title="校准数据", x_label="频率 (GHz)", y_label="值"):
        """绘制校准数据曲线"""
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

    def clear_plot(self):
        """清除所有图表数据"""
        # 使用更高效的方式清除图表
        self.chart.removeAllSeries()
        self.series = {}
        
        # 重置坐标轴范围
        self.axis_x.setRange(0, 40)  # 默认频率范围
        self.axis_y.setRange(-100, 0)  # 默认dB范围
        
        # 保持标题和标签不变，仅清除数据
    
    def show_error(self, message):
        """显示错误消息"""
        QMessageBox.critical(self, "导入错误", message)

  
