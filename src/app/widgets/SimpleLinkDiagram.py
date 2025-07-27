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
            'point_count': 3,        # 能量点数量
            'point_spacing': 0.08,   # 能量点间距(时间间隔)
            'point_size_range': (2, 3),  # 能量点大小范围(min, max)
            'point_alpha_range': (80, 200)  # 能量点透明度范围(min, max)
        }
        
        # 辐射效果配置
        self.radiation_config = {
            'angle_range': (-60, 60),  # 辐射角度范围(度)
            'ring_count': 10,          # 同心圆环数量
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
        
        # 信号源脉冲效果属性
        self.pulse_radius = 0
        self.pulse_alpha = 0
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self.update_pulse)
        self.pulse_timer.start(1500)  # 每1.5秒一个脉冲
        
        # 模式切换过渡属性
        self.transition_progress = 0  # 0-1表示过渡进度
        self.transition_timer = None
        self.old_link = None
        self.new_link = None
        
    def update_pulse(self):
        """更新信号源脉冲效果"""
        if self.source_on:
            self.pulse_radius = 10  # 初始半径
            self.pulse_alpha = 150  # 初始透明度
            # 启动脉冲动画
            self.pulse_animation_timer = QTimer(self)
            self.pulse_animation_timer.timeout.connect(self.animate_pulse)
            self.pulse_animation_timer.start(30)  # 30ms更新一次
    
    def animate_pulse(self):
        """执行脉冲动画"""
        self.pulse_radius += 1.5
        self.pulse_alpha -= 8
        
        if self.pulse_alpha <= 0:
            self.pulse_animation_timer.stop()
            self.pulse_radius = 0
            self.pulse_alpha = 0
        
        self.update()
        
    def update_animation(self):
        """更新动画进度"""
        self.animation_progress = (self.animation_progress + 0.02) % 1.0
        
        # 当能量点接近天线时(>0.95)开始辐射动画
        if self.animation_progress > 0.95 and self.source_on:  # 只有信号源开启时才显示辐射
            self.radiation_progress = (self.radiation_progress + 0.15) % 1.0
        else:
            self.radiation_progress = 0
        self.update()

    def set_link(self, link_mode):
        """设置链路模式并启动过渡动画"""
        normalized_link = link_mode.upper().replace("__", "_")
        
        # 如果是相同链路，直接返回
        if self.current_link == normalized_link:
            return
        
        # 启动过渡动画
        self.old_link = self.current_link
        self.new_link = normalized_link
        self.transition_progress = 0
        self.current_link = normalized_link  # 立即更新当前链路
        
        # 启动过渡动画定时器
        if self.transition_timer:
            self.transition_timer.stop()
        
        self.transition_timer = QTimer(self)
        self.transition_timer.timeout.connect(self.update_transition)
        self.transition_timer.start(20)  # 50 FPS
    
    def update_transition(self):
        """更新过渡动画进度"""
        self.transition_progress += 0.05
        if self.transition_progress >= 1:
            self.transition_progress = 1
            self.transition_timer.stop()
            self.old_link = None
            self.new_link = None
        
        self.update()
        
    def set_source_state(self, state):
        """设置信号源状态"""
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
        signal_source_color = QColor("#4285F4") if self.source_on else QColor("#9E9E9E")
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
        
        # 绘制信号源脉冲效果
        if self.source_on and self.pulse_alpha > 0:
            pulse_color = QColor(66, 133, 244, self.pulse_alpha)  # 蓝色脉冲
            painter.setPen(QPen(pulse_color, 1.5))
            painter.setBrush(Qt.NoBrush)
            pulse_rect = QRectF(
                com_cx - self.pulse_radius,
                com_cy - self.pulse_radius,
                self.pulse_radius * 2,
                self.pulse_radius * 2
            )
            painter.drawEllipse(pulse_rect)

        # ==================== 绘制天线节点和连线 ====================
        antenna_x = com_cx + 200
        for i, (name, link_key) in enumerate(node_list):
            ny = start_y + i * (antenna_h + gap_y)
            
            # 检查是否为旧链路
            is_old_link = self.old_link == link_key if self.old_link else False
            # 检查是否为新链路
            is_new_link = self.new_link == link_key if self.new_link else False
            # 检查是否为其他链路
            is_other_link = not is_old_link and not is_new_link
            
            # 确定链路状态
            is_active = False
            if is_old_link or is_new_link:
                # 在过渡状态中，只考虑新旧链路
                is_active = True
            else:
                # 非过渡状态，检查是否当前链路
                is_active = self.current_link == link_key
            
            # 绘制连线
            line_pen = None
            if is_old_link:
                # 旧链路：淡出效果
                old_alpha = int(255 * (1 - self.transition_progress))
                line_pen = QPen(highlight_color, 4)
                line_pen.setColor(QColor(
                    line_pen.color().red(),
                    line_pen.color().green(),
                    line_pen.color().blue(),
                    old_alpha
                ))
            elif is_new_link:
                # 新链路：淡入效果
                new_alpha = int(255 * self.transition_progress)
                line_pen = QPen(highlight_color, 4)
                line_pen.setColor(QColor(
                    line_pen.color().red(),
                    line_pen.color().green(),
                    line_pen.color().blue(),
                    new_alpha
                ))
            else:
                # 其他链路：正常显示
                line_pen = QPen(highlight_color if is_active else line_color, 
                            4 if is_active else 2.5)
            
            # 应用连线样式
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

            # 天线颜色根据状态变化
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
            if is_active and self.radiation_progress > 0 and self.source_on:
                # 使用配置参数计算辐射效果
                min_radius, max_radius = self.radiation_config['ring_radius_range']
                ring_radius_step = (max_radius - min_radius) / self.radiation_config['ring_count']
                
                # 计算当前最外环半径（动画效果）
                current_max_radius = min_radius + (max_radius - min_radius) * self.radiation_progress
                
                # 计算辐射角度范围
                start_angle = self.radiation_config['angle_range'][0]
                end_angle = self.radiation_config['angle_range'][1]
                angle_span = end_angle - start_angle
                
                # 绘制多个同心圆环
                for i in range(self.radiation_config['ring_count']):
                    # 计算当前圆环半径（从内到外）
                    ring_radius = min_radius + i * ring_radius_step
                    
                    # 只绘制在动画范围内的圆环
                    if ring_radius > current_max_radius:
                        continue
                        
                    # 计算透明度（内环更明显，外环更透明）
                    min_alpha, max_alpha = self.radiation_config['ring_alpha_range']
                    alpha = max_alpha - (max_alpha - min_alpha) * (ring_radius / max_radius)
                    
                    # 计算圆环粗细（外环更细）
                    ring_width = max(1, 3.0 - (ring_radius / max_radius) * 2.0)
                    
                    # 设置画笔属性
                    ring_color = QColor(radiation_color)
                    ring_color.setAlpha(int(alpha))
                    painter.setPen(QPen(ring_color, ring_width))
                    painter.setBrush(Qt.NoBrush)
                    
                    # 计算圆环位置
                    ring_center = QPointF(antenna_left + horn_width, antenna_top + horn_height/2)
                    
                    # 创建圆环的边界矩形
                    rect = QRectF(
                        ring_center.x() - ring_radius, 
                        ring_center.y() - ring_radius,
                        ring_radius * 2, 
                        ring_radius * 2
                    )
                    
                    # 绘制部分圆环（只在辐射角度内可见）
                    # Qt中的角度单位是1/16度，所以需要乘以16
                    painter.drawArc(rect, int(start_angle * 16), int(angle_span * 16))

        painter.end()
    
    def cubic_bezier(self, p0, p1, p2, p3, t):
        """计算三次贝塞尔曲线上的点"""
        mt = 1 - t
        mt2 = mt * mt
        t2 = t * t
        
        x = mt2*mt*p0.x() + 3*mt2*t*p1.x() + 3*mt*t2*p2.x() + t2*t*p3.x()
        y = mt2*mt*p0.y() + 3*mt2*t*p1.y() + 3*mt*t2*p2.y() + t2*t*p3.y()
        
        return QPointF(x, y)
