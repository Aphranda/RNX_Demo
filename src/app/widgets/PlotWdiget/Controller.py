from PyQt5.QtWidgets import QFileDialog
from collections import defaultdict
import os
import re
from app.controllers.CalibrationFileManager import CalibrationFileManager

class PlotController:
    def __init__(self, model, view):
        self.model = model
        self.view = view
        self.file_manager = CalibrationFileManager()  # 创建文件管理器实例
        
        # 连接视图信号
        self.view.import_action.triggered.connect(self.import_data)
        self.view.clear_action.triggered.connect(self.clear_plot)
    
    def import_data(self):
        """导入数据文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.view,
            "选择校准文件",
            "",
            "校准文件 (*.csv *.bin);;所有文件 (*)"
        )
        if not file_path:
            return
        
        self.load_and_plot(file_path)
    
    def load_and_plot(self, file_path=None):
        """加载并绘制校准数据"""
        if not file_path:
            return self.import_data()
        
        # 使用文件管理器加载校准数据
        result = self.file_manager.load_calibration_file(file_path)
        if not result:
            self.view.show_error(f"无法加载校准文件: {os.path.basename(file_path)}")
            return
        
        # 准备绘图数据
        plot_data = defaultdict(list)
        for point in result['data']:
            freq = point['freq']
            
            # 添加所有可用数据系列
            plot_data['Theta'].append((freq, point.get('theta', 0.0)))
            plot_data['Phi'].append((freq, point.get('phi', 0.0)))
            plot_data['Theta_corrected'].append((freq, point.get('theta_corrected', 0.0)))
            plot_data['Phi_corrected'].append((freq, point.get('phi_corrected', 0.0)))
            plot_data['Horn_Gain'].append((freq, point.get('horn_gain', 0.0)))
            
            # 添加V/M值系列
            if 'theta_corrected_vm' in point:
                plot_data['Theta_V/M'].append((freq, point['theta_corrected_vm']))
            if 'phi_corrected_vm' in point:
                plot_data['Phi_V/M'].append((freq, point['phi_corrected_vm']))
        
        # 对每个系列按频率排序
        for series in plot_data.values():
            series.sort(key=lambda x: x[0])
        
        # 从文件名生成标题
        file_name = os.path.basename(file_path)
        polarization = "双极化" if "DualPol" in file_name else "单极化"
        ref_power_match = re.search(r"RefPwr([-\d.]+)dBm", file_name)
        ref_power = ref_power_match.group(1) if ref_power_match else "未知"
        
        title = f"{polarization}校准 (参考功率: {ref_power} dBm)"
        
        # 绘制数据
        self.plot_merged_data(plot_data, title)
    
    def plot_merged_data(self, data_dict, title="合并校准数据"):
        """绘制合并后的校准数据"""
        self.model.clear_data()
        for name, points in data_dict.items():
            self.model.add_custom_data(name, points)
        
        self.view.plot_data(
            self.model.get_data(),
            title=title,
            y_label="值"
        )
    
    def clear_plot(self):
        """清除图表"""
        self.view.clear_plot()
        