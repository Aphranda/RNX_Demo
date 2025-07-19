# app/widgets/CalibrationPanel/CalibrationPanel.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from .View import CalibrationView
from .Model import CalibrationModel
from .Controller import CalibrationController

class CalibrationPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize MVC components
        self._view = CalibrationView()
        self._model = CalibrationModel()
        self._controller = CalibrationController(self._view, self._model)
        
        # Set up layout
        layout = QVBoxLayout(self)
        layout.addWidget(self._view)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Connect parent's log if available
        if hasattr(parent, 'log'):
            self._controller.set_log_callback(parent.log)

    # Property accessors
    @property
    def start_freq(self):
        return self._view.start_freq.value()
    
    @property
    def stop_freq(self):
        return self._view.stop_freq.value()
    
    @property
    def step_freq(self):
        return self._view.step_freq.value()
    
    @property
    def ref_power(self):
        return self._view.ref_power.value()
    
    @property
    def signal_gen_address(self):
        return self._view.signal_gen_address.text()
    
    @property
    def power_meter_address(self):
        return self._view.power_meter_address.text()
    
    @property
    def btn_start(self):
        return self._view.btn_start
    
    @property
    def btn_stop(self):
        return self._view.btn_stop
    
    @property
    def btn_export(self):
        return self._view.btn_export
    
    @property
    def btn_connect(self):
        return self._view.btn_connect
    
    @property
    def btn_auto_detect(self):
        return self._view.btn_auto_detect
    
    @property
    def progress_bar(self):
        return self._view.progress_bar
    
    @property
    def current_step(self):
        return self._view.current_step
    
    def update_instrument_status(self, instrument_type: str, status: str, connected: bool):
        """Update instrument connection status display"""
        self._controller.update_instrument_status(instrument_type, status, connected)

