# app/widgets/CalibrationPanel/Controller.py
from PyQt5.QtCore import QObject, pyqtSignal
from app.utils.SignalUnitConverter import SignalUnitConverter

class CalibrationController(QObject):
    calibration_started = pyqtSignal()
    calibration_stopped = pyqtSignal()
    calibration_completed = pyqtSignal(dict)  # emits calibration data
    instruments_connected = pyqtSignal()
    
    def __init__(self, view, model):
        super().__init__()
        self._view = view
        self._model = model
        self._log_callback = None
        
        # Connect signals
        self._connect_signals()
        
    def _connect_signals(self):
        """Connect view signals to controller methods"""
        self._view.btn_start.clicked.connect(self._on_start_calibration)
        self._view.btn_stop.clicked.connect(self._on_stop_calibration)
        self._view.btn_export.clicked.connect(self._on_export_data)
        self._view.btn_connect.clicked.connect(self._on_connect_instruments)
        self._view.btn_auto_detect.clicked.connect(self._on_auto_detect)
        
    def set_log_callback(self, callback):
        """Set logging callback function"""
        self._log_callback = callback
        
    def _log(self, message, level='info'):
        """Log a message using the callback if available"""
        if self._log_callback:
            self._log_callback(message, level)
            
    def _on_start_calibration(self):
        """Handle start calibration button click"""
        self._log("Starting calibration process...")
        self.calibration_started.emit()
        
    def _on_stop_calibration(self):
        """Handle stop calibration button click"""
        self._log("Calibration stopped by user")
        self.calibration_stopped.emit()
        
    def _on_export_data(self):
        """Handle export data button click"""
        self._log("Exporting calibration data...")
        # TODO: Implement export functionality
        
    def _on_connect_instruments(self):
        """Handle connect instruments button click"""
        signal_gen_addr = self._view.signal_gen_address.text()
        power_meter_addr = self._view.power_meter_address.text()
        
        self._log(f"Connecting to instruments: SignalGen={signal_gen_addr}, PowerMeter={power_meter_addr}")
        # TODO: Implement actual connection logic
        self.instruments_connected.emit()
        
    def _on_auto_detect(self):
        """Handle auto detect instruments button click"""
        self._log("Auto-detecting instruments...")
        # TODO: Implement auto-detection logic
        
    def update_instrument_status(self, instrument_type: str, status: str, connected: bool):
        """Update instrument status display"""
        if instrument_type.lower() == 'signal_gen':
            label = self._view.signal_gen_status
        elif instrument_type.lower() == 'power_meter':
            label = self._view.power_meter_status
        else:
            return
            
        label.setText(status)
        if connected:
            label.setStyleSheet("color: green;")
        else:
            label.setStyleSheet("color: red;")
            
    def update_progress(self, value: int, message: str):
        """Update progress bar and status message"""
        self._view.progress_bar.setValue(value)
        self._view.current_step.setText(message)
