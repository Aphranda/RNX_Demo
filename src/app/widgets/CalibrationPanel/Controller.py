# app/widgets/CalibrationPanel/Controller.py
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from app.controllers.CalibrationFileManager import CalibrationFileManager
import pandas as pd
from pathlib import Path
from typing import List, Optional

class CalibrationController(QObject):
    # 定义信号
    connect_instruments = pyqtSignal(str, str)  # (signal_gen, power_meter)
    auto_detect_instruments = pyqtSignal()
    start_calibration = pyqtSignal(float, float, float, float)  # (start, stop, step, ref)
    start_calibration_with_list = pyqtSignal(list, float)  # (freq_list, ref)
    stop_calibration = pyqtSignal()
    export_data = pyqtSignal()

    def __init__(self, view, model):
        super().__init__()
        self._view = view
        self._model = model
        self._log_callback = None
        self._freq_list: List[float] = []  # 存储导入的频点列表

        # 初始化校准文件管理器
        self.cal_manager = CalibrationFileManager(
            base_dir="calibrations",
            log_callback=self._log
        )
        
        # 连接信号
        self._connect_signals()
        
        # 初始化按钮状态
        self._update_button_states()

    def _connect_signals(self):
        """连接所有UI信号"""
        self._view.btn_connect.clicked.connect(self._on_connect)
        self._view.btn_auto_detect.clicked.connect(self.auto_detect_instruments.emit)
        self._view.btn_start.clicked.connect(self._on_start)
        self._view.btn_stop.clicked.connect(self.stop_calibration.emit)
        self._view.btn_export.clicked.connect(self.export_data.emit)
        self._view.btn_import.clicked.connect(self._import_freq_list)
        self._view.range_mode.toggled.connect(self._update_mode_ui)

    def set_log_callback(self, callback):
        """设置日志回调"""
        self._log_callback = callback

    def _log(self, message: str, level: str = 'INFO'):
        """记录日志"""
        if self._log_callback:
            self._log_callback(message, level)

    def _update_mode_ui(self, checked: bool):
        """更新模式UI状态"""
        self._view._update_mode_visibility()
        self._update_button_states()

    def _import_freq_list(self):
        """导入频点列表"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self._view,
                "选择频点列表文件",
                "",
                "CSV文件 (*.csv);;所有文件 (*)"
            )
            
            if not file_path:
                return
                
            # 读取CSV文件
            df = pd.read_csv(file_path)
            if 'freq' not in df.columns:
                raise ValueError("CSV文件必须包含'freq'列")
                
            self._freq_list = sorted(df['freq'].tolist())
            freq_count = len(self._freq_list)
            
            # 验证频率范围
            min_freq = min(self._freq_list)
            max_freq = max(self._freq_list)
            if min_freq < 0.1 or max_freq > 40:
                raise ValueError("频率范围必须在0.1-40GHz之间")
                
            # 更新UI显示
            self._view.freq_list_info.setText(
                f"已导入{freq_count}个频点 ({min_freq:.3f}-{max_freq:.3f}GHz)"
            )
            self._log(f"成功导入{freq_count}个频点", "INFO")
            
        except Exception as e:
            self._log(f"导入频点列表失败: {str(e)}", "ERROR")
            QMessageBox.warning(self._view, "导入错误", f"导入频点列表失败:\n{str(e)}")
            self._freq_list = []
            self._view.freq_list_info.setText("未导入频点列表")

    def _on_connect(self):
        """处理仪器连接"""
        sig_gen = self._view.signal_gen_address.text().strip()
        power_meter = self._view.power_meter_address.text().strip()
        
        # try:
        default_path = self.cal_manager.generate_default_calibration(
            freq_range=(8.0, 10),
            step=0.01,
        )
        #     self._log(f"默认校准文件已生成: {default_path}", "INFO")
        # except Exception as e:
        #     self._log(f"生成默认校准文件失败: {str(e)}", "ERROR")

        if not sig_gen or not power_meter:
            QMessageBox.warning(self._view, "警告", "请输入仪器地址")
            return
            
        self.connect_instruments.emit(sig_gen, power_meter)

    def _on_start(self):
        """处理开始校准"""
        ref = self._view.ref_power.value()
        
        if self._view.range_mode.isChecked():
            # 范围模式
            start = self._view.start_freq.value()
            stop = self._view.stop_freq.value()
            step = self._view.step_freq.value()
            
            if start >= stop:
                QMessageBox.warning(self._view, "警告", "终止频率必须大于起始频率")
                return
            
            # 创建设备元数据
            equipment_meta = {
                'operator': '操作员名称',
                'signal_gen': ('信号源型号', '序列号'),
                'spec_analyzer': ('频谱分析仪型号', '序列号'),
                'antenna': ('天线型号', '序列号'),
                'environment': (25.0, 50.0)
            }
            
            # 频率参数
            freq_params = {
                'start_ghz': start,
                'stop_ghz': stop,
                'step_ghz': step
            }
            
            # 创建新校准文件
            self.cal_manager.create_new_calibration(
                equipment_meta=equipment_meta,
                freq_params=freq_params,
                version_notes=f"参考功率: {ref}dBm"
            )
            
            self.start_calibration.emit(start, stop, step, ref)
        else:
            # 频点列表模式
            if not self._freq_list:
                QMessageBox.warning(self._view, "警告", "请先导入频点列表")
                return
                
            # 创建设备元数据
            equipment_meta = {
                'operator': '操作员名称',
                'signal_gen': ('信号源型号', '序列号'),
                'spec_analyzer': ('频谱分析仪型号', '序列号'),
                'antenna': ('天线型号', '序列号'),
                'environment': (25.0, 50.0)
            }
            
            # 频率参数
            freq_params = {
                'freq_list': self._freq_list,
                'min_freq': min(self._freq_list),
                'max_freq': max(self._freq_list),
                'count': len(self._freq_list)
            }
            
            # 创建新校准文件
            self.cal_manager.create_new_calibration(
                equipment_meta=equipment_meta,
                freq_params=freq_params,
                version_notes=f"参考功率: {ref}dBm (频点列表模式)"
            )
            
            self.start_calibration_with_list.emit(self._freq_list, ref)

    def update_instrument_status(self, instrument_type: str, connected: bool, info: str = ""):
        """更新仪器状态显示"""
        if instrument_type == 'signal_gen':
            label = self._view.signal_gen_status
            status = "已连接" if connected else "未连接"
            if info:
                status += f" ({info})"
            label.setText(f"信号源: {status}")
        elif instrument_type == 'power_meter':
            label = self._view.power_meter_status
            status = "已连接" if connected else "未连接"
            if info:
                status += f" ({info})"
            label.setText(f"功率计: {status}")
        
        self._update_button_states()

    def update_progress(self, value: int, message: str):
        """更新进度"""
        self._view.progress_bar.setValue(value)
        self._view.current_step.setText(message)
        self._update_button_states()

    def _update_button_states(self):
        """根据状态更新按钮可用性"""
        is_running = 0 < self._view.progress_bar.value() < 100
        is_connected = all([
            "已连接" in self._view.signal_gen_status.text(),
            "已连接" in self._view.power_meter_status.text()
        ])
        
        # 更新按钮状态
        self._view.btn_start.setEnabled(not is_running and is_connected)
        self._view.btn_stop.setEnabled(is_running)
        self._view.btn_export.setEnabled(
            self._view.progress_bar.value() == 100
        )
        
        # 频点列表模式下的特殊控制
        if not self._view.range_mode.isChecked():
            self._view.btn_start.setEnabled(
                not is_running and is_connected and bool(self._freq_list)
            )

    def get_current_freq_list(self) -> Optional[List[float]]:
        """获取当前频点列表"""
        return self._freq_list if self._freq_list else None
