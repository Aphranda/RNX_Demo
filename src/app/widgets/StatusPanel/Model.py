from typing import Dict, Optional
from utils.SignalUnitConverter import SignalUnitConverter

class StatusPanelModel:
    def __init__(self):
        self.unit_converter = SignalUnitConverter()

        # 新增样式状态
        self.style_status = {
            'cal_file': {
                'text': 'Calib Miss',
                'style': "background:#ffcdd2; color:#d32f2f;"  # 默认错误样式
            }
        }
        
        # 运动模组状态
        self.motion_status = {
            'X': {'reach': '-', 'home': '-', 'speed': '-'},
            'KU': {'reach': '-', 'home': '-', 'speed': '-'},
            'K': {'reach': '-', 'home': '-', 'speed': '-'},
            'KA': {'reach': '-', 'home': '-', 'speed': '-'},
            'Z': {'reach': '-', 'home': '-', 'speed': '-'}
        }
        
        # 信号源状态
        self.src_status = {
            'freq': '-',
            'raw_power': '-',
            'power': '-',
            'rf': '-',
            'cal_file': 'Calib Miss'
        }
        
        # 单位设置
        self.units = {
            'freq': self.unit_converter.default_freq_unit,
            'raw_power': self.unit_converter.default_power_unit,
            'power': self.unit_converter.default_power_unit
        }

    def update_motion_status(self, axis: str, status: Dict[str, str]):
        if axis in self.motion_status:
            self.motion_status[axis].update(status)

    def update_src_status(self, status: Dict[str, str]):
        self.src_status.update(status)

    def update_unit(self, unit_type: str, unit: str):
        if unit_type in self.units:
            self.units[unit_type] = unit

    def update_style_status(self, element: str, style: dict):
        """更新元素样式状态
        :param element: 元素名称如 'cal_file'
        :param style: 样式字典 {text: str, style: str}
        """
        if element in self.style_status:
            self.style_status[element].update(style)
