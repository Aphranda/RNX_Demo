# app/widgets/CalibrationPanel/Controller.py
import pandas as pd
from pathlib import Path
from typing import List, Optional, Dict, Union
from datetime import datetime

from PyQt5.QtCore import QObject, pyqtSignal, QThread
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from app.controllers.CalibrationFileManager import CalibrationFileManager
from app.instruments.factory import InstrumentFactory
from app.instruments.interfaces import SignalSource, PowerSensor
from app.threads.CalibrationThread import CalibrationService, CalibrationPoint, CalibrationThread
from .Model import InstrumentInfo


class CalibrationController(QObject):
    # 定义信号
    instruments_connected = pyqtSignal(str, str)  # (signal_gen, power_meter)
    instruments_auto_detected = pyqtSignal()
    calibration_triggered = pyqtSignal(float, float, float, float)  # (start, stop, step, ref)
    calibration_triggered_with_list = pyqtSignal(list, float)  # (freq_list, ref)
    calibration_stopped = pyqtSignal()
    data_exported = pyqtSignal()

    def __init__(self, view, model):
        super().__init__()
        self._view = view
        self._model = model
        self._log_callback = None
        self._freq_list: List[float] = []
        self._calibration_thread = None
        self._calibration_service = CalibrationService()

        # 初始化校准文件管理器
        self.cal_manager = CalibrationFileManager(
            base_dir="calibrations",
            log_callback=self._log
        )

        # 连接信号
        self._connect_signals()
        self._update_button_states()

    def _connect_signals(self):
        """连接所有UI信号"""
        self._view.btn_connect.clicked.connect(self._on_connect)
        self._view.btn_auto_detect.clicked.connect(self._auto_detect_instruments)
        self._view.btn_start.clicked.connect(self._on_start)
        self._view.btn_stop.clicked.connect(self._on_stop)
        self._view.btn_export.clicked.connect(self._on_export)
        self._view.btn_import.clicked.connect(self._import_freq_list)
        self._view.range_mode.toggled.connect(self._update_mode_ui)
        self._view.btn_import_gain.clicked.connect(self._import_antenna_gain)

        # 连接校准服务信号
        self.calibration_triggered.connect(self._start_calibration_process)
        self.calibration_triggered_with_list.connect(self._start_calibration_with_list_process)

    def set_log_callback(self, callback):
        """设置日志回调"""
        self._log_callback = callback

    def _log(self, message: str, level: str = 'INFO'):
        """记录日志"""
        if self._log_callback:
            self._log_callback(message, level)

    # region 天线增益部分
    def _import_antenna_gain(self):
        """导入天线增益文件"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self._view,
                "选择天线增益文件",
                "",
                "CSV文件 (*.csv);;所有文件 (*)"
            )
            
            if not file_path:
                return
                
            df = pd.read_csv(file_path)
            df.columns = df.columns.str.lower()
            print(df.columns)
            # 检查必要的列
            if 'freq' not in df.columns or 'gain' not in df.columns:
                raise ValueError("CSV文件必须包含'freq'和'gain'列")
                
            # 验证频率范围
            min_freq = df['freq'].min()
            max_freq = df['freq'].max()
            if min_freq < 0.1 or max_freq > 40:
                raise ValueError("频率范围必须在0.1-40GHz之间")
                
            # 保存增益数据到模型
            self._model.antenna_gain_data = df.to_dict('records')
            
            # 更新UI显示
            freq_count = len(df)
            self._view.antenna_gain_info.setText(
                f"{min_freq:.1f}-{max_freq:.1f}GHz Load"
            )
            self._log(f"成功导入{freq_count}个天线增益点，（{min_freq:.3f}-{max_freq:.3f}GHz）", "INFO")
            
        except Exception as e:
            self._log(f"导入天线增益失败: {str(e)}", "ERROR")
            QMessageBox.warning(self._view, "导入错误", f"导入天线增益失败:\n{str(e)}")
            self._model.antenna_gain_data = None
            self._view.antenna_gain_info.setText("未导入天线增益")
    
    # endregion

    # region 仪器连接相关方法
    def _on_connect(self):
        """处理仪器连接"""
        sig_gen_name = self._view.signal_gen_name.text().strip()
        power_meter_name = self._view.power_meter_name.text().strip()
        sig_gen_addr = self._view.signal_gen_address.text().strip()
        power_meter_addr = self._view.power_meter_address.text().strip()
        
        if not all([sig_gen_name, power_meter_name, sig_gen_addr, power_meter_addr]):
            QMessageBox.warning(self._view, "警告", "请输入仪表名称和仪器地址")
            return
        
        try:
            # 尝试连接信号源
            sig_gen = InstrumentFactory.create_signal_source(sig_gen_addr, sig_gen_name)
            if sig_gen:
                self._model.signal_gen = InstrumentInfo(
                    address=sig_gen_addr,
                    model=sig_gen.model,
                    name=sig_gen_name,
                    connected=True,
                    instance=sig_gen  # 保存实际实例
                )
                self.update_instrument_status('signal_gen', True, f"{sig_gen_name} - {sig_gen.idn.split(',')[1]}")
                self._log(f"信号源连接成功: {sig_gen.idn}", "SUCCESS")
            else:
                raise Exception("无法识别信号源类型")
            
            # 尝试连接功率计
            pwr_meter = InstrumentFactory.create_power_meter(power_meter_addr, power_meter_name)
            if pwr_meter:
                self._model.power_meter = InstrumentInfo(
                    address=power_meter_addr,
                    model=pwr_meter.model,
                    name=power_meter_name,
                    connected=True,
                    instance=pwr_meter  # 保存实际实例
                )
                self.update_instrument_status('power_meter', True, f"{power_meter_name} - {pwr_meter.idn.split(',')[1]}")
                self._log(f"功率计连接成功: {pwr_meter.idn}", "SUCCESS")
                self.instruments_connected.emit(sig_gen_addr, power_meter_addr)
            else:
                raise Exception("无法识别功率计类型")

        except Exception as e:
            self._log(f"仪器连接失败: {str(e)}", "ERROR")
            QMessageBox.critical(self._view, "错误", f"仪器连接失败:\n{str(e)}")
            self._cleanup_instruments()
            self.update_instrument_status('signal_gen', False)
            self.update_instrument_status('power_meter', False)


    def _auto_detect_instruments(self):
        """自动检测连接的VISA仪器"""
        try:
            import pyvisa
            
            self._log("开始自动检测仪器...", "INFO")
            rm = pyvisa.ResourceManager()
            resources = rm.list_resources()
            
            if not resources:
                self._log("未检测到任何VISA仪器", "WARNING")
                QMessageBox.warning(self._view, "警告", "未检测到任何VISA仪器")
                return
                
            self._log(f"检测到VISA资源: {resources}", "INFO")
            
            signal_gen_address = ""
            power_meter_address = ""
            
            for resource in resources:
                try:
                    info = InstrumentFactory._identify_instrument(resource)
                    if not info:
                        continue
                    
                    if info['type'] == 'signal_source':
                        signal_gen_address = resource
                        self._log(f"检测到信号源: {info['model']} @ {resource}", "SUCCESS")
                    elif info['type'] == 'power_meter':
                        power_meter_address = resource
                        self._log(f"检测到功率计: {info['model']} @ {resource}", "SUCCESS")
                        
                except Exception as e:
                    self._log(f"检测设备{resource}时出错: {str(e)}", "WARNING")
                    continue
                    
            # 更新UI
            if signal_gen_address:
                self._view.signal_gen_address.setText(signal_gen_address)
                self.update_instrument_status('signal_gen', False, "检测到信号源")
                
            if power_meter_address:
                self._view.power_meter_address.setText(power_meter_address)
                self.update_instrument_status('power_meter', False, "检测到功率计")
                self.instruments_auto_detected.emit()
                
            if not signal_gen_address and not power_meter_address:
                self._log("未识别到支持的信号源或功率计", "WARNING")
                QMessageBox.warning(self._view, "警告", "未识别到支持的信号源或功率计")
                
        except ImportError:
            self._log("PyVISA未安装，无法自动检测仪器", "ERROR")
            QMessageBox.critical(self._view, "错误", "需要安装PyVISA才能自动检测仪器")
        except Exception as e:
            self._log(f"自动检测仪器失败: {str(e)}", "ERROR")
            QMessageBox.critical(self._view, "错误", f"自动检测仪器失败:\n{str(e)}")

    def _cleanup_instruments(self):
        """清理仪器连接"""
        if hasattr(self._model, 'signal_gen') and self._model.signal_gen.instance:
            try:
                self._model.signal_gen.instance.close()
            except:
                pass
            self._model.signal_gen = InstrumentInfo(address="", model="", name="")
            
        if hasattr(self._model, 'power_meter') and self._model.power_meter.instance:
            try:
                self._model.power_meter.instance.close()
            except:
                pass
            self._model.power_meter = InstrumentInfo(address="", model="", name="")

    # endregion

    # region 校准流程控制
    def _on_start(self):
        """处理开始校准按钮点击"""
        ref_power = self._view.ref_power.value()
        
        if self._view.range_mode.isChecked():
            # 范围模式
            start = self._view.start_freq.value()
            stop = self._view.stop_freq.value()
            step = self._view.step_freq.value()
            
            if start >= stop:
                QMessageBox.warning(self._view, "警告", "终止频率必须大于起始频率")
                return
            
            # 准备校准元数据
            equipment_meta = self._prepare_equipment_meta()
            freq_params = {
                'start_ghz': start,
                'stop_ghz': stop,
                'step_ghz': step,
                'custom_freqs': []
            }
            
            # 创建校准文件
            self.cal_manager.create_new_calibration(
                equipment_meta=equipment_meta,
                freq_params=freq_params,
                version_notes=f"参考功率: {ref_power}dBm"
            )
            
            # 触发校准信号
            self.calibration_triggered.emit(start, stop, step, ref_power)
        else:
            # 频点列表模式
            if not self._freq_list:
                QMessageBox.warning(self._view, "警告", "请先导入频点列表")
                return
                
            # 准备校准元数据
            equipment_meta = self._prepare_equipment_meta()
            freq_params = {
                'start_ghz': min(self._freq_list),
                'stop_ghz': max(self._freq_list),
                'step_ghz': "NONE",
                'custom_freqs': self._freq_list,
            }
            
            # 创建校准文件
            self.cal_manager.create_new_calibration(
                equipment_meta=equipment_meta,
                freq_params=freq_params,
                version_notes=f"参考功率: {ref_power}dBm (频点列表模式)"
            )
            
            # 触发校准信号
            self.calibration_triggered_with_list.emit(self._freq_list, ref_power)

    def _start_calibration_process(self, start: float, stop: float, step: float, ref_power: float):
        """处理范围模式校准启动"""
        freq_list = [start + i * step for i in range(int((stop - start) / step) + 1)]
        self._execute_calibration(freq_list, ref_power)

    def _start_calibration_with_list_process(self, freq_list: List[float], ref_power: float):
        """处理频点列表模式校准启动"""
        self._execute_calibration(freq_list, ref_power)

    def _execute_calibration(self, freq_list: List[float], ref_power: float):
        """执行校准流程"""
        if not hasattr(self._model, 'signal_gen') or not hasattr(self._model, 'power_meter'):
            QMessageBox.warning(self._view, "警告", "请先连接仪器")
            return
        
        # 检查是否实际连接了仪器实例
        if not self._model.signal_gen.instance or not self._model.power_meter.instance:
            QMessageBox.warning(self._view, "警告", "仪器实例未正确初始化")
            return
        
        # 转换为Hz单位
        freq_list_hz = [f * 1e9 for f in freq_list]
        print("freq_list_hz",freq_list_hz)
        
        # 启动校准服务
        self._calibration_service.start_calibration(
            signal_source=self._model.signal_gen.instance,  # 使用实际实例
            power_meter=self._model.power_meter.instance,   # 使用实际实例
            freq_list=freq_list_hz,
            ref_power=ref_power,
            progress_callback=self._update_progress,
            point_callback=self._save_calibration_point,
            finished_callback=self._on_calibration_finished,
            error_callback=self._on_calibration_error
        )


    def _on_stop(self):
        """处理停止校准"""
        self._calibration_service.stop_calibration()
        self.calibration_stopped.emit()
        self._update_progress(0, "校准已中止")

    def _on_export(self):
        """处理数据导出"""
        if self._model.calibration_data:
            try:
                file_path, _ = QFileDialog.getSaveFileName(
                    self._view,
                    "导出校准数据",
                    "",
                    "CSV文件 (*.csv);;所有文件 (*)"
                )
                
                if file_path:
                    self.cal_manager.export_to_csv(file_path, self._model.calibration_data)
                    self._log(f"校准数据已导出到: {file_path}", "SUCCESS")
                    self.data_exported.emit()
                    QMessageBox.information(self._view, "成功", "数据导出完成")
            except Exception as e:
                self._log(f"导出失败: {str(e)}", "ERROR")
                QMessageBox.critical(self._view, "错误", f"导出失败:\n{str(e)}")
        else:
            QMessageBox.warning(self._view, "警告", "没有可导出的校准数据")

    def _prepare_equipment_meta(self) -> Dict:
        """准备设备元数据"""
        return {
            'operator': '操作员名称',
            'signal_gen': (
                self._model.signal_gen.model if hasattr(self._model.signal_gen, 'model') else '未知',
                self._model.signal_gen.serial_number if hasattr(self._model.signal_gen, 'serial_number') else '未知'
            ),
            'power_meter': (
                self._model.power_meter.model if hasattr(self._model.power_meter, 'model') else '未知',
                self._model.power_meter.serial_number if hasattr(self._model.power_meter, 'serial_number') else '未知'
            ),
            'antenna': (
                self._view.antenna_model.text().strip() or 'DEFAULT_ANT',
                self._view.antenna_sn.text().strip() or 'SN00000'
            ),
            'environment': (25.0, 50.0)  # 温度, 湿度
        }

    # endregion

    # region 校准结果处理
    def _update_progress(self, value: int, message: str):
        """更新进度显示"""
        self._view.progress_bar.setValue(value)
        self._view.current_step.setText(message)
        self._update_button_states()

    def _save_calibration_point(self, point: CalibrationPoint):
        """保存单个校准点"""
        self._model.add_calibration_point(point)
        self.cal_manager.add_calibration_point(point)

    def _on_calibration_finished(self, results: List[CalibrationPoint]):
        """校准完成处理"""
        self._update_progress(100, "校准完成")
        QMessageBox.information(self._view, "完成", f"校准成功完成!\n共校准{len(results)}个频点")
        
    def _on_calibration_error(self, error_msg: str):
        """校准错误处理"""
        self._update_progress(0, f"错误: {error_msg}")
        QMessageBox.critical(self._view, "错误", error_msg)
        self._cleanup_instruments()
    # endregion

    # region 频点列表管理
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
            
            # 强制更新按钮状态
            self._update_button_states()  # 新增这行
            
        except Exception as e:
            self._log(f"导入频点列表失败: {str(e)}", "ERROR")
            QMessageBox.warning(self._view, "导入错误", f"导入频点列表失败:\n{str(e)}")
            self._freq_list = []
            self._view.freq_list_info.setText("未导入频点列表")
            self._update_button_states()  # 失败时也更新状态
    # endregion

    # region UI状态管理
    def update_instrument_status(self, instrument_type: str, connected: bool, info: str = ""):
        """更新仪器连接状态显示"""
        status_text = "已连接" if connected else "未连接"
        if info:
            status_text += f" ({info})"
            
        if instrument_type == 'signal_gen':
            self._view.signal_gen_status.setText(f"信号源: {status_text}")
        elif instrument_type == 'power_meter':
            self._view.power_meter_status.setText(f"功率计: {status_text}")
        
        self._update_button_states()

    def _update_mode_ui(self, checked: bool):
        """更新频率模式UI"""
        self._view._update_mode_visibility()
        # self._update_button_states()  # 确保模式切换时更新按钮状态

    def _update_button_states(self):
        """根据当前状态更新按钮可用性"""
        is_running = 0 < self._view.progress_bar.value() < 100
        is_connected = all([
            "已连接" in self._view.signal_gen_status.text(),
            "已连接" in self._view.power_meter_status.text()
        ])
        has_freq_list = bool(self._freq_list)
        
        # 调试信息
        # self._log(f"更新按钮状态: 运行中={is_running}, 已连接={is_connected}, 有频点列表={has_freq_list}, 范围模式={self._view.range_mode.isChecked()}", "DEBUG")
        
        # 更新按钮状态
        self._view.btn_connect.setEnabled(not is_running)
        self._view.btn_auto_detect.setEnabled(not is_running)
        
        # 修改这里：在频点列表模式下，只要仪器已连接且有频点列表，就启用开始按钮
        self._view.btn_start.setEnabled(not is_running and is_connected and 
                                    (self._view.range_mode.isChecked() or has_freq_list))
        
        self._view.btn_stop.setEnabled(is_running)
        self._view.btn_export.setEnabled(
            not is_running and 
            self._view.progress_bar.value() == 100
        )
        self._view.btn_import.setEnabled(not is_running)

    # endregion

    def get_current_freq_list(self) -> Optional[List[float]]:
        """获取当前频点列表"""
        return self._freq_list if self._freq_list else None

