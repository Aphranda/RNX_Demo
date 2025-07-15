from PyQt5.QtCore import QObject, pyqtSignal
from .Model import StatusPanelModel
from .View import StatusPanelView

class StatusPanelController(QObject):
    cal_file_loaded = pyqtSignal(str)
    
    def __init__(self, view: StatusPanelView, model: StatusPanelModel):
        super().__init__()
        self.view = view
        self.model = model

        # 日志回调函数
        self.log_callback = None
        
        self.setup_connections()
        self.initialize_units()

        # 状态更新标志
        self._update_motion = True
        self._update_source = True
    
    def set_log_callback(self, callback):
        """设置日志回调函数"""
        self.log_callback = callback

    def update_motion_display(self, enable: bool):
        """控制运动状态显示更新"""
        self._update_motion = enable
        if not enable:
            for axis in self.model.motion_status:
                self.model.update_motion_status(axis, {
                    'reach': '-', 
                    'home': '-', 
                    'speed': '-'
                })
            self.update_ui()
 
    def update_source_display(self, enable: bool):
        """控制信号源显示更新"""
        self._update_source = enable
        if not enable:
            self.model.update_src_status({
                'freq': '-',
                'raw_power': '-',
                'power': '-',
                'rf': '-'
            })
            self.update_ui()
 
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

    def update_motion_status(self, status: dict):
        """更新运动状态"""
        if self._update_motion:
            for axis, axis_status in status.items():
                if axis in self.model.motion_status:
                    # 检查是否有错误状态
                    
                    error_items = {k: v for k, v in axis_status.items() if v == "ERROR"}
                    if error_items:
                        # 记录日志
                        if self.log_callback:
                            self.log_callback(f"轴 {axis} 状态查询异常: {error_items}", "WARNING")
                        
                        # 只更新错误项为ERROR，其他项保持不变
                        for item, value in axis_status.items():
                            if value == "ERROR":
                                self.model.motion_status[axis][item] = "ERROR"
                    else:
                        self.model.update_motion_status(axis, axis_status)
            self.update_ui()

    def update_src_status(self, status: dict):
        """更新信号源状态"""
        if self._update_source:
            # 检查是否有错误状态
            error_items = {k: v for k, v in status.items() if v == "ERROR"}
            
            if error_items:
                # 记录日志
                if self.log_callback:
                    self.log_callback(f"信号源状态查询异常: {error_items}", "WARNING")
                
                # 只更新错误项为ERROR，其他项保持不变
                for item, value in status.items():
                    if value == "ERROR":
                        self.model.src_status[item] = "ERROR"
            else:
                # 没有错误则正常更新
                self.model.update_src_status(status)
            self.update_ui()


    def update_operation_status(self, operation: str, axis: str):
        """更新操作状态显示"""
        if operation and axis:
            self.model.style_status['motion_label']['text'] = f"{axis}轴{'复位' if operation == 'HOMING' else '达位'}中..."
            self.model.style_status['motion_label']['style'] = "color: #ff8f00;"
        else:
            self.model.style_status['motion_label']['text'] = "运动状态: 就绪"
            self.model.style_status['motion_label']['style'] = "color: #228B22;"
        self.update_ui()

    def update_ui(self):
        # 更新运动模组状态
        for axis, status in self.model.motion_status.items():
            if axis in self.view.motion_reach:
                self._update_status_label(self.view.motion_reach[axis], status['reach'])
                self._update_status_label(self.view.motion_home[axis], status['home'])
                
                # 更新速度标签
                speed_text = status.get('speed', '-')
                self.view.motion_speed[axis].setText(speed_text)
                
                # 确保速度样式被应用
                self.model.update_speed_style(axis, speed_text)
                speed_style = self.model.style_status.get(f'speed_{axis}', {})
                if speed_style:
                    self.view.motion_speed[axis].setStyleSheet(speed_style.get('style', ''))
        
        # 更新信号源状态
        src = self.model.src_status
        self._update_status_label(self.view.src_freq, src['freq'])
        self._update_status_label(self.view.src_raw_power, src['raw_power'])
        self._update_status_label(self.view.src_power, src['power'])
        self._update_status_label(self.view.src_rf, src['rf'])
        
        # 更新校准文件状态
        cal_style = self.model.style_status.get('cal_file')
        if cal_style:
            self.view.cal_file_status.setText(cal_style['text'])
            self.view.cal_file_status.setStyleSheet(cal_style['style'])
            
        # 更新运动状态标签
        motion_style = self.model.style_status.get('motion_label')
        if motion_style:
            self.view.motion_label.setText(motion_style['text'])
            self.view.motion_label.setStyleSheet(motion_style['style'])
            
        # 更新单位组合框颜色
        self._update_unit_combo_colors()

    def _update_status_label(self, label, text):
        """更新状态标签"""
        label.setText(str(text).strip())
        style = self.model.get_status_style(text)
        label.setStyleSheet(style)

    def _update_unit_combo_colors(self):
        """更新单位组合框颜色"""
        # 功率单位组合框
        power_unit = self.view.power_unit_combo.currentText()
        power_color = self.model.unit_converter.get_power_unit_color(power_unit)
        self.view.power_unit_combo.setStyleSheet(
            f"background: {power_color}; color: white;"
        )
        
        # 原始功率单位组合框
        raw_power_unit = self.view.raw_power_unit_combo.currentText()
        raw_power_color = self.model.unit_converter.get_power_unit_color(raw_power_unit)
        self.view.raw_power_unit_combo.setStyleSheet(
            f"background: {raw_power_color}; color: white;"
        )
        
        # 频率单位组合框（固定颜色）
        freq_color = "#0078d7"
        self.view.freq_unit_combo.setStyleSheet(
            f"background: {freq_color}; color: white;"
        )

    def set_cal_file_style(self, text: str, state: str):
        """设置校准文件状态样式"""
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
