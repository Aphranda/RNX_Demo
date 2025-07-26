from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import (QColor, QPainter, QPen, QFont, 
                         QLinearGradient, QPainterPath, QBrush, QPolygonF)
from PyQt5.QtCore import Qt, QPointF, QRectF, QTimer, QPoint
import math

class SimpleLinkDiagram(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(450)
        self.setMinimumWidth(480)
        self.current_link = "FEED_X_THETA"
        self.setStyleSheet("background: transparent;")
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        
        # 能量点配置
        self.energy_config = {
            'point_count': 4,        # 能量点数量
            'point_spacing': 0.08,   # 能量点间距(时间间隔)
            'point_size_range': (2, 3),  # 能量点大小范围(min, max)
            'point_alpha_range': (80, 200)  # 能量点透明度范围(min, max)
        }
        
        # 辐射效果配置
        self.radiation_config = {
            'angle_range': (-60, 60),  # 辐射角度范围(度)
            'angle_step': 15,          # 辐射线角度步长(度)
            'ring_count': 10,           # 同心圆环数量
            'ring_radius_range': (15, 80),  # 圆环半径范围(min, max)
            'ring_alpha_range': (40, 120)   # 圆环透明度范围(min, max)
        }
        
        # 动画相关属性
        self.animation_progress = 0
        self.radiation_progress = 0
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(50)  # 20 FPS
        
        # 信号源状态
        self.source_on = False  # 默认关闭状态
        
    def update_animation(self):
        """更新动画进度"""
        self.animation_progress = (self.animation_progress + 0.02) % 1.0
        
        # 当能量点接近天线时(>0.95)开始辐射动画
        if self.animation_progress > 0.95 and self.source_on:  # 只有信号源开启时才显示辐射
            self.radiation_progress = (self.radiation_progress + 0.1) % 1.0
        else:
            self.radiation_progress = 0
        self.update()

    def set_link(self, link_mode):
        normalized_link = link_mode.upper().replace("__", "_")
        self.current_link = normalized_link
        self.update()
        
    def set_source_state(self, state):
        """设置信号源状态
        Args:
            state: 可以是字符串"ON"/"OFF"或布尔值True/False
        """
        if isinstance(state, str):
            self.source_on = state.upper() == "ON"
        else:
            self.source_on = bool(state)
        self.update()

 
    def paintEvent(self, a0):
        super().paintEvent(a0)
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        
        # 配色方案
        node_border = QColor("#3367d6")
        node_text = QColor("#202124")
        line_color = QColor("#dadce0")
        highlight_color = QColor("#ea4335")
        highlight_text = QColor("#ea4335")
        energy_color = QColor(255, 215, 0, 200)
        signal_source_color = QColor("#4285F4") if self.source_on else QColor("#9E9E9E")  # 根据状态改变颜色
        antenna_color = QColor("#5F6368")
        radiation_color = QColor(255, 215, 0, 80)
        
        # 字体设置
        font = QFont("Segoe UI", 10, QFont.Medium)
        painter.setFont(font)
 
        # 布局参数
        start_x = 120
        start_y = 20
        antenna_w = 40
        antenna_h = 24
        gap_y = 35
 
        # 节点定义
        node_list = [
            ("X_THETA", "FEED_X_THETA"),
            ("X_PHI", "FEED_X_PHI"),
            ("KU_THETA", "FEED_KU_THETA"),
            ("KU_PHI", "FEED_KU_PHI"),
            ("K_THETA", "FEED_K_THETA"),
            ("K_PHI", "FEED_K_PHI"),
            ("KA_THETA", "FEED_KA_THETA"),
            ("KA_PHI", "FEED_KA_PHI"),
        ]
 
        # COM节点位置
        com_cx = start_x
        com_cy = start_y + (len(node_list) * (antenna_h + gap_y) - gap_y) // 2

        # ==================== 绘制信号源样式 ====================
        signal_w = 70
        signal_h = 50
        signal_rect = QRectF(com_cx - signal_w//2, com_cy - signal_h//2, signal_w, signal_h)
        
        grad = QLinearGradient(signal_rect.topLeft(), signal_rect.bottomRight())
        if self.source_on:
            grad.setColorAt(0, QColor("#E8F0FE"))
            grad.setColorAt(1, QColor("#D2E3FC"))
        else:
            grad.setColorAt(0, QColor("#F5F5F5"))
            grad.setColorAt(1, QColor("#E0E0E0"))
        painter.setBrush(grad)
        painter.setPen(QPen(signal_source_color, 2))
        painter.drawRoundedRect(signal_rect, 8, 8)
        
        # 绘制波形符号
        wave_path = QPainterPath()
        wave_start_x = com_cx - signal_w//2 + 15
        wave_end_x = com_cx + signal_w//2 - 15
        wave_height = 10
        segments = 6
        
        wave_path.moveTo(wave_start_x, com_cy)
        for i in range(1, segments+1):
            x = wave_start_x + (i * (wave_end_x - wave_start_x)/segments)
            y = com_cy + wave_height * math.sin(2 * math.pi * i / segments)
            wave_path.lineTo(x, y)
        
        painter.setPen(QPen(signal_source_color.darker(120), 2))
        painter.drawPath(wave_path)
        
        # 绘制内部辐射线
        painter.setPen(QPen(signal_source_color.lighter(130), 1.2))
        inner_radius = min(signal_w, signal_h) * 0.35
        
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            end_p = QPointF(com_cx + inner_radius * math.cos(rad), 
                           com_cy + inner_radius * math.sin(rad))
            painter.drawLine(QPointF(com_cx, com_cy), end_p)
        
        # 信号源文字标签
        label_rect = QRectF(com_cx - signal_w//2 - 120,
                           com_cy - signal_h//2, 
                           110,
                           signal_h)
        
        painter.setPen(QPen(QColor("#0F1018"), 1))
        painter.drawText(label_rect, Qt.AlignVCenter | Qt.AlignRight, "SOURCE")

        # ==================== 绘制天线节点和连线 ====================
        antenna_x = com_cx + 200
        for i, (name, link_key) in enumerate(node_list):
            ny = start_y + i * (antenna_h + gap_y)
            
            # 绘制连线
            is_active = self.current_link == link_key
            line_pen = QPen(highlight_color if is_active else line_color, 
                        4 if is_active else 2.5)
            line_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(line_pen)
            painter.setBrush(Qt.NoBrush)
            
            path = QPainterPath()
            path.moveTo(com_cx + signal_w//2, com_cy)
            
            ctrl1_x = com_cx + 90
            ctrl1_y = com_cy
            ctrl2_x = antenna_x - 90
            ctrl2_y = ny + antenna_h//2
            
            path.cubicTo(
                QPointF(ctrl1_x, ctrl1_y),
                QPointF(ctrl2_x, ctrl2_y),
                QPointF(antenna_x - antenna_w//2, ny + antenna_h//2)
            )
            painter.drawPath(path)
            
            # 能量流动效果 - 只在信号源开启时显示
            if is_active and self.source_on:
                t = self.animation_progress
                p0 = QPointF(com_cx + signal_w//2, com_cy)
                p1 = QPointF(ctrl1_x, ctrl1_y)
                p2 = QPointF(ctrl2_x, ctrl2_y)
                p3 = QPointF(antenna_x - antenna_w//2, ny + antenna_h//2)
                
                energy_point = self.cubic_bezier(p0, p1, p2, p3, t)
                
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(energy_color))
                painter.drawEllipse(energy_point, 3, 3)
                
                # 使用配置参数绘制能量点尾迹
                for j in range(1, self.energy_config['point_count'] + 1):
                    tail_t = (t - j * self.energy_config['point_spacing']) % 1.0
                    if tail_t < 0: continue
                    tail_point = self.cubic_bezier(p0, p1, p2, p3, tail_t)
                    
                    # 计算大小和透明度
                    size = max(self.energy_config['point_size_range'][0], 
                             self.energy_config['point_size_range'][1] - j)
                    alpha = max(self.energy_config['point_alpha_range'][0], 
                              self.energy_config['point_alpha_range'][1] - j * 40)
                    
                    if alpha > 0:
                        painter.setBrush(QBrush(QColor(255, 215, 0, alpha)))
                        painter.drawEllipse(tail_point, size, size)
            
            # 绘制喇叭天线
            antenna_left = antenna_x - antenna_w//2
            antenna_top = ny

            horn_width = antenna_w
            horn_height = antenna_h
            flare_angle = 15
            flare_length = horn_width * 0.6

            horn_path = QPainterPath()
            waveguide_width = horn_width - flare_length
            waveguide_left = antenna_left

            flare_top = antenna_top + (horn_height/2 - (flare_length * math.tan(math.radians(flare_angle))/2))
            flare_bottom = antenna_top + horn_height - (horn_height/2 - (flare_length * math.tan(math.radians(flare_angle))/2))

            horn_path.moveTo(antenna_left, flare_top)
            horn_path.lineTo(antenna_left + flare_length, antenna_top)
            horn_path.lineTo(antenna_left + horn_width, antenna_top)
            horn_path.lineTo(antenna_left + horn_width, antenna_top + horn_height)
            horn_path.lineTo(antenna_left + flare_length, antenna_top + horn_height)
            horn_path.lineTo(antenna_left, flare_bottom)
            horn_path.closeSubpath()

            if is_active:
                grad = QLinearGradient(antenna_left, antenna_top, 
                                    antenna_left + horn_width, antenna_top + horn_height)
                grad.setColorAt(0, QColor("#f1f3f4"))
                grad.setColorAt(1, QColor("#e0e2e4"))
                painter.setPen(QPen(highlight_color, 1.5))
            else:
                grad = QLinearGradient(antenna_left, antenna_top, 
                                    antenna_left + horn_width, antenna_top + horn_height)
                grad.setColorAt(0, QColor("#f8f9fa"))
                grad.setColorAt(1, QColor("#e8eaed"))
                painter.setPen(QPen(antenna_color, 1))

            painter.setBrush(grad)
            painter.drawPath(horn_path)

            # 绘制天线内部细节
            painter.setPen(QPen(antenna_color.darker(120), 0.8))
            guide_line_y = antenna_top + horn_height/2
            painter.drawLine(QPointF(waveguide_left + 2, guide_line_y),
                            QPointF(waveguide_left + waveguide_width - 2, guide_line_y))
            
            # 绘制文字标签
            text_pen = QPen(highlight_text if is_active else node_text, 1)
            painter.setPen(text_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawText(antenna_x + horn_width//2 + 8,
                           ny, 80, horn_height, 
                           Qt.AlignVCenter | Qt.AlignLeft, name)
            
            # ==================== 天线辐射效果 ====================
            if is_active and self.radiation_progress > 0 and self.source_on:  # 只有信号源开启时才显示辐射
                # 使用配置参数计算辐射效果
                min_radius, max_radius = self.radiation_config['ring_radius_range']
                radius = min_radius + (max_radius - min_radius) * self.radiation_progress
                
                radiation_center = QPointF(antenna_left + horn_width, antenna_top + horn_height/2)
                
                # 绘制辐射波(扇形)
                start_angle, end_angle = self.radiation_config['angle_range']
                angle_span = end_angle - start_angle
                
                for i in range(1, self.radiation_config['ring_count'] + 1):
                    r = radius * (i / self.radiation_config['ring_count'])
                    min_alpha, max_alpha = self.radiation_config['ring_alpha_range']
                    alpha = int(max_alpha * (1 - i / self.radiation_config['ring_count']))
                    
                    painter.setPen(QPen(QColor(radiation_color.red(), radiation_color.green(), 
                                    radiation_color.blue(), alpha), 2.0))
                    
                    # 绘制扇形
                    path = QPainterPath()
                    path.moveTo(radiation_center)
                    path.arcTo(radiation_center.x() - r, radiation_center.y() - r, 
                            r * 2, r * 2, 
                            start_angle, angle_span)
                    path.closeSubpath()
                    painter.drawPath(path)
                    
                    # 添加辐射线
                    for angle in range(start_angle, end_angle, self.radiation_config['angle_step']):
                        rad = math.radians(angle)
                        end_x = radiation_center.x() + r * math.cos(rad)
                        end_y = radiation_center.y() + r * math.sin(rad)
                        painter.drawLine(radiation_center, QPointF(end_x, end_y))

        painter.end()
    
    def cubic_bezier(self, p0, p1, p2, p3, t):
        """计算三次贝塞尔曲线上的点"""
        mt = 1 - t
        mt2 = mt * mt
        t2 = t * t
        
        x = mt2*mt*p0.x() + 3*mt2*t*p1.x() + 3*mt*t2*p2.x() + t2*t*p3.x()
        y = mt2*mt*p0.y() + 3*mt2*t*p1.y() + 3*mt*t2*p2.y() + t2*t*p3.y()
        
        return QPointF(x, y)
