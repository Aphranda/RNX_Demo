from PyQt5.QtCore import QObject, pyqtSignal
from .Model import StatusPanelModel
from .View import StatusPanelView

class StatusPanelController(QObject):
    cal_file_loaded = pyqtSignal(str)  # 校准文件加载信号
    
    def __init__(self, view: StatusPanelView, model: StatusPanelModel):
        super().__init__()
        self.view = view
        self.model = model
        
        self.setup_connections()
        self.initialize_units()

    def setup_connections(self):
        # 单位选择变化
        self.view.freq_unit_combo.currentTextChanged.connect(
            lambda unit: self.on_unit_changed('freq', unit))
        self.view.raw_power_unit_combo.currentTextChanged.connect(
            lambda unit: self.on_unit_changed('raw_power', unit))
        self.view.power_unit_combo.currentTextChanged.connect(
            lambda unit: self.on_unit_changed('power', unit))
        
        # 校准文件加载
        self.view.load_cal_btn.clicked.connect(self.on_load_cal_file)

    def initialize_units(self):
        # 初始化单位下拉框
        self.view.freq_unit_combo.addItems(list(self.model.unit_converter.FREQ_UNITS.keys()))
        self.view.freq_unit_combo.setCurrentText(self.model.units['freq'])
        
        power_units = list(self.model.unit_converter.POWER_UNITS.keys()) + \
                     list(self.model.unit_converter.E_FIELD_UNITS.keys())
        self.view.raw_power_unit_combo.addItems(power_units)
        self.view.raw_power_unit_combo.setCurrentText(self.model.units['raw_power'])
        
        self.view.power_unit_combo.addItems(power_units)
        self.view.power_unit_combo.setCurrentText(self.model.units['power'])

    def on_unit_changed(self, unit_type: str, unit: str):
        self.model.update_unit(unit_type, unit)
        self.update_ui()

    def on_load_cal_file(self):
        cal_file = self.view.cal_file_input.text()
        if cal_file:
            self.model.update_src_status({'cal_file': cal_file})
            self.cal_file_loaded.emit(cal_file)
            self.update_ui()

    def update_motion_status(self, axis: str, status: dict[str, str]):
        self.model.update_motion_status(axis, status)
        self.update_ui()

    def update_src_status(self, status: dict[str, str]):
        self.model.update_src_status(status)
        self.update_ui()

    def update_ui(self):
        # 更新运动模组状态
        for axis, status in self.model.motion_status.items():
            if axis in self.view.motion_reach:
                self.view.motion_reach[axis].setText(status['reach'])
                self.view.motion_home[axis].setText(status['home'])
                self.view.motion_speed[axis].setText(status['speed'])
        
        # 更新信号源状态
        src = self.model.src_status
        self.view.src_freq.setText(src['freq'])
        self.view.src_raw_power.setText(src['raw_power'])
        self.view.src_power.setText(src['power'])
        self.view.src_rf.setText(src['rf'])
        self.view.cal_file_status.setText(src['cal_file'])

        cal_style = self.model.style_status.get('cal_file')
        if cal_style:
            self.view.cal_file_status.setText(cal_style['text'])
            self.view.cal_file_status.setStyleSheet(cal_style['style'])

    def set_cal_file_style(self, text: str, state: str):
        """设置校准文件状态样式
        :param text: 显示文本
        :param state: 状态类型 ('loaded', 'missing', 'invalid')
        """
        styles = {
            'loaded': "background:#b6f5c6; color:#0078d7;",
            'missing': "background:#fff9c4; color:#0078d7;",
            'invalid': "background:#ffcdd2; color:#d32f2f;"
        }
        
        self.model.update_style_status('cal_file', {
            'text': text,
            'style': styles.get(state, styles['missing'])
        })
        self.update_ui()
