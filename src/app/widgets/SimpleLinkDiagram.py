from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import (QColor, QPainter, QPen, QFont, 
                         QLinearGradient, QPainterPath, QBrush)
from PyQt5.QtCore import Qt, QPointF, QRectF, QTimer
import math

class SimpleLinkDiagram(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(450)  # 增加高度以容纳信号源和标签
        self.setMinimumWidth(500)
        self.current_link = "FEED_X_THETA"
        self.setStyleSheet("background: transparent;")
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        
        # 动画相关属性
        self.animation_progress = 0
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(50)  # 20 FPS
        
    def update_animation(self):
        """更新动画进度"""
        self.animation_progress = (self.animation_progress + 0.05) % 1.0
        self.update()
        
    def set_link(self, link_mode):
        normalized_link = link_mode.upper().replace("__", "_")
        self.current_link = normalized_link
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
        signal_source_color = QColor("#4285F4")
        
        # 字体设置
        font = QFont("Segoe UI", 10, QFont.Medium)
        painter.setFont(font)

        # 布局参数
        start_x = 120  # 向右移动给标签留空间
        start_y = 20
        node_w = 40
        node_h = 24
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
        com_cy = start_y + (len(node_list) * (node_h + gap_y) - gap_y) // 2

        # ==================== 绘制信号源样式 ====================
        # 1. 信号源尺寸参数
        signal_w = 70  # 加宽信号源
        signal_h = 50  # 加高信号源
        signal_rect = QRectF(com_cx - signal_w//2, com_cy - signal_h//2, signal_w, signal_h)
        
        # 渐变填充
        grad = QLinearGradient(signal_rect.topLeft(), signal_rect.bottomRight())
        grad.setColorAt(0, QColor("#E8F0FE"))
        grad.setColorAt(1, QColor("#D2E3FC"))
        painter.setBrush(grad)
        painter.setPen(QPen(signal_source_color, 2))
        painter.drawRoundedRect(signal_rect, 8, 8)  # 增加圆角半径
        
        # 2. 绘制波形符号(正弦波) - 调整到矩形内部
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
        
        # 3. 绘制内部辐射线(完全在矩形内)
        painter.setPen(QPen(signal_source_color.lighter(130), 1.2))  # 细线
        inner_radius = min(signal_w, signal_h) * 0.35  # 内部半径
        
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            # 辐射线从中心到内边缘
            end_p = QPointF(com_cx + inner_radius * math.cos(rad), 
                           com_cy + inner_radius * math.sin(rad))
            painter.drawLine(QPointF(com_cx, com_cy), end_p)
        
        # 4. 信号源文字标签(向左移动并确保完整显示)
        label_rect = QRectF(com_cx - signal_w//2 - 120,  # 向左移动更多
                           com_cy - signal_h//2, 
                           110,  # 增加标签宽度
                           signal_h)
        
        painter.setPen(QPen(QColor("#0F1018"), 1))
        painter.drawText(label_rect, Qt.AlignVCenter | Qt.AlignRight, "SOURCE")  # 完整标签

        # ==================== 绘制节点和连线 ====================
        node_x = com_cx + 200  # 调整节点X位置
        for i, (name, link_key) in enumerate(node_list):
            ny = start_y + i * (node_h + gap_y)
            
            # 绘制连线(保持不变)
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
            ctrl2_x = node_x - 90
            ctrl2_y = ny + node_h//2
            
            path.cubicTo(
                QPointF(ctrl1_x, ctrl1_y),
                QPointF(ctrl2_x, ctrl2_y),
                QPointF(node_x - node_w//2, ny + node_h//2)
            )
            painter.drawPath(path)
            
            # 能量流动效果(保持不变)
            if is_active:
                t = self.animation_progress
                p0 = QPointF(com_cx + signal_w//2, com_cy)
                p1 = QPointF(ctrl1_x, ctrl1_y)
                p2 = QPointF(ctrl2_x, ctrl2_y)
                p3 = QPointF(node_x - node_w//2, ny + node_h//2)
                
                energy_point = self.cubic_bezier(p0, p1, p2, p3, t)
                
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(energy_color))
                painter.drawEllipse(energy_point, 3, 3)
                
                for j in range(1, 3):
                    tail_t = (t - j*0.15) % 1.0
                    if tail_t < 0: continue
                    tail_point = self.cubic_bezier(p0, p1, p2, p3, tail_t)
                    alpha = 200 - j*80
                    size = max(1, 3 - j)
                    if alpha > 0:
                        painter.setBrush(QBrush(QColor(255, 215, 0, alpha)))
                        painter.drawEllipse(tail_point, size, size)
            
            # 绘制节点(保持不变)
            if is_active:
                grad = QLinearGradient(node_x - node_w//2, ny, node_x + node_w//2, ny + node_h)
                grad.setColorAt(0, QColor("#ffffff"))
                grad.setColorAt(1, QColor("#f1f3f4"))
                painter.setPen(QPen(highlight_color, 2))
                painter.setBrush(grad)
            else:
                grad = QLinearGradient(node_x - node_w//2, ny, node_x + node_w//2, ny + node_h)
                grad.setColorAt(0, QColor("#ffffff"))
                grad.setColorAt(1, QColor("#f1f3f4"))
                painter.setPen(QPen(node_border, 1))
                painter.setBrush(grad)
            
            painter.drawEllipse(QRectF(node_x - node_w//2, ny, node_w, node_h))
    
            # 绘制文字(保持不变)
            text_pen = QPen(highlight_text if is_active else node_text, 1)
            painter.setPen(text_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawText(node_x + node_w//2 + 6, ny, 80, node_h, 
                        Qt.AlignVCenter | Qt.AlignLeft, name)
    
        painter.end()
    
    def cubic_bezier(self, p0, p1, p2, p3, t):
        """计算三次贝塞尔曲线上的点"""
        mt = 1 - t
        mt2 = mt * mt
        t2 = t * t
        
        x = mt2*mt*p0.x() + 3*mt2*t*p1.x() + 3*mt*t2*p2.x() + t2*t*p3.x()
        y = mt2*mt*p0.y() + 3*mt2*t*p1.y() + 3*mt*t2*p2.y() + t2*t*p3.y()
        
        return QPointF(x, y)
