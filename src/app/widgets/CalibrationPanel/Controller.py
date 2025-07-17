# app/widgets/CalibrationPanel/Controller.py
import pandas as pd
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QFileDialog
from app.core.exceptions.calibration import CalibrationError
from app.services.calibration import CalibrationService

class CalibrationController(QObject):
    progress_updated = pyqtSignal(int, str)
    calibration_finished = pyqtSignal(bool, str)
    
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.service = CalibrationService()
        self._connect_signals()

    def _connect_signals(self):
        self.view.btn_start.clicked.connect(self.start_calibration)
        self.view.btn_stop.clicked.connect(self.stop_calibration)
        self.view.btn_export.clicked.connect(self.export_data)
        
        self.progress_updated.connect(self.view.progress_bar.setValue)
        self.progress_updated.connect(self.view.current_step.setText)
        self.calibration_finished.connect(self._on_finished)

    def start_calibration(self):
        params = {
            'start_hz': self.view.start_freq.value() * 1e9,
            'stop_hz': self.view.stop_freq.value() * 1e9,
            'step_hz': self.view.step_freq.value() * 1e6,
            'ref_power': self.view.ref_power.value()
        }
        
        try:
            self.service.start_async(
                params=params,
                progress_callback=self._update_progress,
                finished_callback=self._on_calibration_done
            )
            self._set_controls_enabled(False)
        except CalibrationError as e:
            self.calibration_finished.emit(False, str(e))

    def _update_progress(self, percent: int, message: str):
        self.progress_updated.emit(percent, message)

    def _on_calibration_done(self, success: bool, message: str):
        self.calibration_finished.emit(success, message)

    def _on_finished(self, success: bool, message: str):
        self._set_controls_enabled(True)
        if not success:
            self.view.show_error(message)

    def _set_controls_enabled(self, enabled: bool):
        self.view.btn_start.setEnabled(enabled)
        self.view.param_group.setEnabled(enabled)

    def export_data(self):
        if not hasattr(self, '_last_results'):
            return
            
        path, _ = QFileDialog.getSaveFileName(
            self.view, 
            "导出校准数据", 
            "", 
            "CSV文件 (*.csv);;Excel文件 (*.xlsx)"
        )
        
        if path:
            df = pd.DataFrame([vars(p) for p in self._last_results])
            if path.endswith('.csv'):
                df.to_csv(path, index=False)
            else:
                df.to_excel(path, index=False)