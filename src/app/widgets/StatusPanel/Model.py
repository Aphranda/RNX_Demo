from typing import Dict, Optional
from utils.SignalUnitConverter import SignalUnitConverter

class StatusPanelModel:
    def __init__(self):
        self.unit_converter = SignalUnitConverter()

        # 样式状态
        self.style_status = {
            'cal_file': {
                'text': 'Calib Miss',
                'style': "background:#ffcdd2; color:#d32f2f;"  # 默认错误样式
            },
            'motion_label': {
                'text': '运动状态: 就绪',
                'style': "color: #228B22;"
            }
        }
        
        # 速度颜色映射
        self.speed_colors = {
            "LOW": "#ffe082",
            "MID1": "#ffd54f",
            "MID2": "#ffb300",
            "MID3": "#ff8f00",
            "HIGH": "#ff6f00"
        }
        
        # 状态颜色映射
        self.status_colors = {
            'NO': "background:#fff9c4; color:#0078d7; border:2px solid #0078d7; border-radius:8px;",
            'FAIL': "background:#fff9c4; color:#0078d7; border:2px solid #0078d7; border-radius:8px;",
            'OK': "background:#b6f5c6; color:#0078d7; border:2px solid #0078d7; border-radius:8px;",
            'PASS': "background:#b6f5c6; color:#0078d7; border:2px solid #0078d7; border-radius:8px;",
            'default': "background:#f5faff; color:#0078d7; border:2px solid #0078d7; border-radius:8px;",
            'error': "background:#ffcdd2; color:#d32f2f; border:2px solid #0078d7; border-radius:8px;"
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
            
            # 自动更新速度背景色
            if 'speed' in status:
                self.update_speed_style(axis, status['speed'])

    def update_src_status(self, status: Dict[str, str]):
        self.src_status.update(status)

    def update_unit(self, unit_type: str, unit: str):
        if unit_type in self.units:
            self.units[unit_type] = unit

    def update_style_status(self, element: str, style: dict):
        """更新元素样式状态"""
        if element in self.style_status:
            self.style_status[element].update(style)
            
    def update_speed_style(self, axis: str, speed_text: str):
        """更新速度标签样式"""
        # 确保速度文本是字符串并去除前后空格
        speed_text = str(speed_text).strip().upper()
        
        # 匹配速度级别
        speed_level = "UNKOWN"  # 默认值
        if "LOW" in speed_text:
            speed_level = "LOW"
        if "MID1" in speed_text:
            speed_level = "MID1"
        elif "MID2" in speed_text:
            speed_level = "MID2" 
        elif "MID3" in speed_text:
            speed_level = "MID3"
        elif "HIGH" in speed_text:
            speed_level = "HIGH"
        
        bg = self.speed_colors.get(speed_level, "#f5faff")
        style = f"background:{bg}; color:#0078d7; border:2px solid #0078d7; border-radius:8px;"
 
        # 确保样式状态被正确更新
        if f'speed_{axis}' not in self.style_status:
            self.style_status[f'speed_{axis}'] = {}
        self.style_status[f'speed_{axis}'].update({
            'style': style,
            'text': speed_text  # 同时保存文本
        })


    def get_status_style(self, text: str):
        """根据文本获取状态样式"""
        text = str(text).upper()
        if "ERROR" in text:
            return self.status_colors['error']
        if any(x in text for x in ["超时", "TIMEOUT", "连接失败"]):
            return self.status_colors['error']
        for key in self.status_colors:
            if key in text:
                return self.status_colors[key]
        return self.status_colors['default']

