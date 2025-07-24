from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from enum import Enum, auto
from .Model import StatusPanelModel
from .View import StatusPanelView

class FeedState(Enum):
    """馈源模组状态枚举"""
    REACHED = auto()      # 达位完成
    REACHING = auto()     # 达位运动中
    HOMED = auto()        # 复位完成
    HOMING = auto()       # 复位运动中
    UNKNOWN = auto()      # 未知状态

class StatusPanelController(QObject):
    cal_file_loaded = pyqtSignal(str)
    motion_command = pyqtSignal(str)
    operation_completed = pyqtSignal(str, bool)  # axis, succes
    
    
    def __init__(self, view: StatusPanelView, model: StatusPanelModel):
        super().__init__()
        self.view = view
        self.model = model
        self.log_callback = None

        # 馈源模组状态机
        self.feed_states = {
            'X': FeedState.UNKNOWN,
            'KU': FeedState.UNKNOWN,
            'K': FeedState.UNKNOWN,
            'KA': FeedState.UNKNOWN,
            'Z': FeedState.UNKNOWN
        }
        
        # 当前操作状态
        self.current_operation = None
        self.operating_axis = None
        self.pending_operations = []  # 待处理操作队列
        
        # 状态更新标志
        self._update_motion = True
        self._update_source = True
        
        # 操作超时定时器
        self.operation_timeout = QTimer()
        self.operation_timeout.setSingleShot(True)
        self.operation_timeout.timeout.connect(self._on_operation_timeout)

        # 界面获取数据
        self._main_window = None
        
        self.setup_connections()
        self.initialize_units()

    def set_log_callback(self, callback):
        """设置日志回调函数"""
        self.log_callback = callback

    def log(self, message, level="INFO"):
        """记录日志"""
        if self.log_callback:
            self.log_callback(message, level)

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

    def get_compensation_value(self, freq_ghz: float) -> float:
        """获取补偿值"""
        if hasattr(self, '_main_window') and self._main_window:
            return self._main_window.get_compensation_value(freq_ghz)
        return 0.0


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
        """处理单位变化事件"""
        self.model.update_unit(unit_type, unit)
        
        # 根据单位类型更新对应的显示值
        if unit_type == 'freq':
            current_freq = self.model.src_status.get('freq', '-')
            if current_freq != '-':
                formatted = self._format_quantity(current_freq, 'frequency')
                self.model.update_src_status({'freq': formatted})
                
        elif unit_type in ('power', 'raw_power'):
            current_power = self.model.src_status.get(unit_type, '-')
            if current_power != '-':
                formatted = self._format_quantity(current_power, 'power', 
                                            'src_power' if unit_type == 'power' else 'raw_power')
                self.model.update_src_status({unit_type: formatted})
        
        self.update_ui()



    def _format_quantity(self, value, quantity_type, target_widget=None):
        """格式化数值显示，考虑单位转换"""
        try:
            # 转换为浮点数
            num = float(str(value).strip())
            
            if quantity_type == 'frequency':
                # 频率单位转换
                current_unit = self.view.freq_unit_combo.currentText()
                converted, _ = self.model.unit_converter.convert_frequency(num, 'Hz', current_unit)
                
                # 根据单位确定小数位数
                if current_unit == 'Hz':
                    return f"{int(converted)} {current_unit}"  # Hz不保留小数
                elif current_unit == 'kHz':
                    return f"{converted:.3f} {current_unit}"  # kHz保留3位小数
                elif current_unit == 'MHz':
                    return f"{converted:.6f} {current_unit}"  # MHz保留6位小数
                elif current_unit == 'GHz':
                    return f"{converted:.9f} {current_unit}"  # GHz保留9位小数
                else:
                    return f"{converted:.6f} {current_unit}"  # 默认保留6位小数
                    
            elif quantity_type == 'power':
                # 获取当前单位
                if target_widget == 'src_power':
                    current_unit = self.view.power_unit_combo.currentText()
                else:
                    current_unit = self.view.raw_power_unit_combo.currentText()
                
                # 检查是否是电场强度单位
                if current_unit in self.model.unit_converter.E_FIELD_UNITS:
                    # 将dBm转换为电场强度
                    # 需要频率信息，从当前状态获取
                    freq_str = self.model.src_status.get('freq', '1GHz')  # 默认1GHz
                    try:
                        freq_ghz = float(freq_str.replace('GHz', '').strip())
                        freq_hz = freq_ghz * 1e9
                    except:
                        freq_hz = 1e9  # 默认1GHz
                    
                    # 转换为电场强度
                    efield_value = self.model.unit_converter.dbm_to_dbuV_m(num, freq_hz)
                    # 转换为目标单位
                    converted, unit = self.model.unit_converter.convert_efield(
                        efield_value, 'dBμV/m', current_unit
                    )
                    
                    # 电场强度格式化
                    if unit in ['dBμV/m', 'dBuV/m']:
                        return f"{converted:.2f} {unit}"
                    elif unit == 'V/m':
                        return f"{converted:.6f} {unit}"
                    else:  # mV/m, µV/m
                        return f"{converted:.3f} {unit}"
                else:
                    # 普通功率单位转换
                    converted, unit = self.model.unit_converter.convert_power(num, 'dBm', current_unit)
                    
                    # 功率单位格式化
                    if unit in ['dBm', 'dBW']:
                        return f"{converted:.2f} {unit}"
                    elif unit == 'W':
                        return f"{converted:.6f} {unit}"
                    else:  # mW, µW, nW
                        return f"{converted:.3f} {unit}"
                    
        except (ValueError, TypeError):
            return str(value)




    def on_load_cal_file(self):
        cal_file = self.view.cal_file_input.text()
        if cal_file:
            self.model.update_src_status({'cal_file': cal_file})
            self.cal_file_loaded.emit(cal_file)
            self.update_ui()

    def _update_feed_state(self, axis: str, status: dict):
        """更新馈源模组状态"""
        if 'reach' in status:
            if "OK" in status['reach']:
                self.feed_states[axis] = FeedState.REACHED
            elif "MOVING" in status['reach']:
                self.feed_states[axis] = FeedState.REACHING
                
        if 'home' in status:
            if "OK" in status['home']:
                self.feed_states[axis] = FeedState.HOMED
            elif "MOVING" in status['home']:
                self.feed_states[axis] = FeedState.HOMING

    def _get_reached_axes(self, exclude_axis=None):
        """获取当前处于达位状态的模组(排除指定轴)"""
        return [axis for axis, state in self.feed_states.items() 
                if state == FeedState.REACHED and axis != exclude_axis]

    def _process_pending_operations(self):
        """处理待执行的操作队列"""
        if self.pending_operations and not self.current_operation:
            operation = self.pending_operations.pop(0)
            self._execute_operation(*operation)

    def _execute_operation(self, operation: str, axis: str):
        """执行操作(达位或复位)"""
        self.current_operation = operation
        self.operating_axis = axis
        self._operation_confirm_count = 0  # 初始化计数器
        
        # 更新UI显示操作状态
        self.model.style_status['motion_label']['text'] = \
            f"{axis}轴{'复位' if operation == 'HOMING' else '达位'}中..."
        self.model.style_status['motion_label']['style'] = "color: #ff8f00;"
        self.update_ui()
        
        # 启动超时定时器(90秒)
        self.operation_timeout.start(90000)
        
        # 发送实际的硬件命令
        cmd = f"MOTion:{'HOME' if operation == 'HOMING' else 'FEED'} {axis}"
        self.motion_command.emit(cmd)  # 通过信号发送命令
        self.log(f"发送命令: {cmd}", "INFO")
 

    def _on_operation_complete(self, success: bool):
        """操作完成回调"""
        self.operation_timeout.stop()
        
        if success:
            # 更新状态
            if self.current_operation == "HOMING":
                self.feed_states[self.operating_axis] = FeedState.HOMED
            elif self.current_operation == "FEEDING":
                self.feed_states[self.operating_axis] = FeedState.REACHED
            
            self.log(f"{self.operating_axis}轴{self.current_operation}操作完成", "SUCCESS")
        else:
            self.log(f"{self.operating_axis}轴{self.current_operation}操作失败", "ERROR")

        # 发射操作完成信号
        self.operation_completed.emit(self.operating_axis, success)
        
        # 重置当前操作状态
        self.current_operation = None
        self.operating_axis = None
        
        # 恢复UI显示
        self.model.style_status['motion_label']['text'] = "运动状态: 就绪"
        self.model.style_status['motion_label']['style'] = "color: #228B22;"
        self.update_ui()
        
        # 处理下一个待执行操作
        self._process_pending_operations()

    def _on_operation_timeout(self):
        """操作超时处理"""
        self.log(f"{self.operating_axis}轴{self.current_operation}操作超时", "WARNING")
        self._on_operation_complete(False)

    def request_feed(self, axis: str):
        """请求模组达位"""
        # 检查是否有其他模组处于达位状态
        reached_axes = self._get_reached_axes(exclude_axis=axis)
        
        if reached_axes:
            # 先复位其他模组
            for other_axis in reached_axes:
                self.pending_operations.append(("HOMING", other_axis))
            
            # 将当前模组的达位请求加入队列
            self.pending_operations.append(("FEEDING", axis))
            
            # 如果没有正在进行的操作，开始处理队列
            if not self.current_operation:
                self._process_pending_operations()
        else:
            # 没有其他模组达位，直接执行
            self._execute_operation("FEEDING", axis)

    def request_home(self, axis: str):
        """请求模组复位"""
        # 复位操作可以直接执行
        self._execute_operation("HOMING", axis)

    def update_motion_status(self, status: dict):
        """更新运动状态"""
        if self._update_motion:
            for axis, axis_status in status.items():
                if axis in self.model.motion_status:
                    # 更新馈源状态机
                    self._update_feed_state(axis, axis_status)
                    # 检查是否有错误状态
                    error_items = {k: v for k, v in axis_status.items() if v == "ERROR"}
                    if error_items:
                        if self.log_callback:
                            self.log_callback(f"轴 {axis} 状态查询异常: {error_items}", "WARNING")
                        
                        # 只更新错误项为ERROR，其他项保持不变
                        for item, value in axis_status.items():
                            if value == "ERROR":
                                self.model.motion_status[axis][item] = "ERROR"
                    else:
                        # 更新运动状态
                        self.model.update_motion_status(axis, axis_status)
                        
                        # 检查当前操作是否完成
                        if self.current_operation and self.operating_axis == axis:
                            # 添加状态确认计数器
                            if not hasattr(self, '_operation_confirm_count'):
                                self._operation_confirm_count = 0
                                
                            if (self.current_operation == "HOMING" and "OK" in axis_status.get("home", "")):
                                self._operation_confirm_count += 1
                            elif (self.current_operation == "FEEDING" and "OK" in axis_status.get("reach", "")):
                                self._operation_confirm_count += 1
                            else:
                                self._operation_confirm_count = 0
                                
                            # 只有当连续2次确认操作完成才真正完成
                            if self._operation_confirm_count >= 2:
                                self._on_operation_complete(True)
                                self._operation_confirm_count = 0  # 重置计数器
            self.update_ui()


    def update_src_status(self, status: dict):
        """更新信号源状态"""
        if self._update_source:
            # 检查是否有错误状态
            error_items = {k: v for k, v in status.items() if v == "ERROR"}
            
            if error_items:
                if self.log_callback:
                    self.log_callback(f"信号源状态查询异常: {error_items}", "WARNING")
                
                # 只更新错误项为ERROR，其他项保持不变
                for item, value in status.items():
                    if value == "ERROR":
                        self.model.src_status[item] = "ERROR"
                if status.get('power') == "ERROR":
                    self.model.src_status['raw_power'] = "ERROR"
            else:
                # 格式化数值并更新
                formatted_status = {}
                for key, value in status.items():
                    if key == 'freq':
                        formatted_status[key] = self._format_quantity(value, 'frequency')
                    elif key == 'power':
                        # 获取当前频率
                        freq_str = status.get('freq', '0')
                        try:
                            freq_ghz = float(freq_str.replace('GHz', '').strip()) if 'GHz' in freq_str else float(freq_str)/1e9
                            # 应用补偿值
                            compensation = self.get_compensation_value(freq_ghz)
                            compensated_power = float(value) + compensation
                            formatted_status[key] = self._format_quantity(str(compensated_power), 'power', 'src_power')
                            # 同时更新原始功率
                            formatted_status['raw_power'] = self._format_quantity(value, 'power', 'raw_power')
                        except ValueError:
                            formatted_status[key] = self._format_quantity(value, 'power', 'src_power')
                    elif key == 'raw_power':
                        # 原始功率不应用补偿
                        if 'power' not in formatted_status:  # 如果power还没处理过
                            formatted_status[key] = self._format_quantity(value, 'power', 'raw_power')
                    else:
                        formatted_status[key] = value
                self.model.update_src_status(formatted_status)
            self.update_ui()



    def update_operation_status(self, axis_status: dict = None):
        """更新操作状态显示"""
        if self.current_operation and self.operating_axis:
            if self.operating_axis == "ALL":
                self.operating_axis = "Z"
            if axis_status and self.operating_axis in axis_status:
                status = axis_status[self.operating_axis]
                if (self.current_operation == "HOMING" and "OK" in status.get("home", "")) or \
                   (self.current_operation == "FEEDING" and "OK" in status.get("reach", "")):
                    self._on_operation_complete(True)
                else:
                    # 操作仍在进行中
                    self.model.style_status['motion_label']['text'] = \
                        f"{self.operating_axis}轴{'复位' if self.current_operation == 'HOMING' else '达位'}中..."
                    self.model.style_status['motion_label']['style'] = "color: #ff8f00;"
            else:
                # 无状态更新，保持当前显示
                pass
        else:
            # 无操作，显示就绪状态
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
        if power_unit in self.model.unit_converter.E_FIELD_UNITS:
            power_color = self.model.unit_converter.get_efield_unit_color(power_unit)
        else:
            power_color = self.model.unit_converter.get_power_unit_color(power_unit)
        self.view.power_unit_combo.setStyleSheet(
            f"background: {power_color}; color: white;"
        )
        
        # 原始功率单位组合框
        raw_power_unit = self.view.raw_power_unit_combo.currentText()
        if raw_power_unit in self.model.unit_converter.E_FIELD_UNITS:
            raw_power_color = self.model.unit_converter.get_efield_unit_color(raw_power_unit)
        else:
            raw_power_color = self.model.unit_converter.get_power_unit_color(raw_power_unit)
        self.view.raw_power_unit_combo.setStyleSheet(
            f"background: {raw_power_color}; color: white;"
        )
        
        # 频率单位组合框(固定颜色)
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
