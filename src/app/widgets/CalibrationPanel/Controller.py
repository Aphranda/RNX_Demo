# app/widgets/CalibrationPanel/Controller.py
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox

class CalibrationController(QObject):
    # 定义信号
    connect_instruments = pyqtSignal(str, str)  # (signal_gen, power_meter)
    auto_detect_instruments = pyqtSignal()
    start_calibration = pyqtSignal(float, float, float, float)  # (start, stop, step, ref)
    stop_calibration = pyqtSignal()
    export_data = pyqtSignal()

    def __init__(self, view, model):
        super().__init__()
        self._view = view
        self._model = model
        self._log_callback = None
        
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

    def set_log_callback(self, callback):
        """设置日志回调"""
        self._log_callback = callback

    def _log(self, message, level='INFO'):
        """记录日志"""
        if self._log_callback:
            self._log_callback(message, level)

    def _on_connect(self):
        """处理仪器连接"""
        sig_gen = self._view.signal_gen_address.text().strip()
        power_meter = self._view.power_meter_address.text().strip()
        
        if not sig_gen or not power_meter:
            QMessageBox.warning(self._view, "警告", "请输入仪器地址")
            return
            
        self.connect_instruments.emit(sig_gen, power_meter)

    def _on_start(self):
        """处理开始校准"""
        start = self._view.start_freq.value()
        stop = self._view.stop_freq.value()
        step = self._view.step_freq.value()
        ref = self._view.ref_power.value()
        
        if start >= stop:
            QMessageBox.warning(self._view, "警告", "终止频率必须大于起始频率")
            return
            
        self.start_calibration.emit(start, stop, step, ref)

    def update_instrument_status(self, instrument_type, connected, info=""):
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

    def update_progress(self, value, message):
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
        
        self._view.btn_start.setEnabled(not is_running and is_connected)
        self._view.btn_stop.setEnabled(is_running)
        self._view.btn_export.setEnabled(
            self._view.progress_bar.value() == 100
        )
