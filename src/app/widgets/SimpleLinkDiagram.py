from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import (QColor, QPainter, QPen, QFont, 
                         QLinearGradient, QPainterPath, QBrush)
from PyQt5.QtCore import Qt, QPointF, QRectF, QTimer

class SimpleLinkDiagram(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(400)
        self.setMinimumWidth(400)
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
        energy_color = QColor(255, 215, 0, 200)  # 金色能量点
        
        # 字体设置
        font = QFont("Segoe UI", 10, QFont.Medium)
        painter.setFont(font)

        # 布局参数
        start_x = 70
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

        # 画COM节点
        painter.setPen(QPen(node_border, 1.5))
        painter.drawEllipse(QRectF(com_cx - node_w//2, com_cy - node_h//2, node_w, node_h))

        # COM节点文字
        painter.setPen(QPen(QColor("#0F1018"), 1))
        painter.drawText(com_cx - node_w//2 - 100, com_cy - node_h//2, 100, node_h, 
                        Qt.AlignVCenter | Qt.AlignRight, "COM")

        # 画节点和连线
        node_x = com_cx + 160
        for i, (name, link_key) in enumerate(node_list):
            ny = start_y + i * (node_h + gap_y)
            
            # 1. 绘制连线
            is_active = self.current_link == link_key
            line_pen = QPen(highlight_color if is_active else line_color, 
                        4 if is_active else 2.5)
            line_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(line_pen)
            painter.setBrush(Qt.NoBrush)
            
            # 创建贝塞尔曲线路径 - 使用统一的控制点设置
            path = QPainterPath()
            path.moveTo(com_cx + node_w//2, com_cy)
            
            # 统一控制点设置，使所有曲线保持相似的平直度
            ctrl1_x = com_cx + 80
            ctrl1_y = com_cy
            ctrl2_x = node_x - 80
            ctrl2_y = ny + node_h//2
            
            path.cubicTo(
                QPointF(ctrl1_x, ctrl1_y),
                QPointF(ctrl2_x, ctrl2_y),
                QPointF(node_x - node_w//2, ny + node_h//2)
            )
            painter.drawPath(path)
            
            # 如果是当前活动链接，绘制能量流动效果
            if is_active:
                # 计算能量点位置
                t = self.animation_progress
                p0 = QPointF(com_cx + node_w//2, com_cy)
                p1 = QPointF(ctrl1_x, ctrl1_y)
                p2 = QPointF(ctrl2_x, ctrl2_y)
                p3 = QPointF(node_x - node_w//2, ny + node_h//2)
                
                # 贝塞尔曲线上的点
                energy_point = self.cubic_bezier(p0, p1, p2, p3, t)
                
                # 绘制能量点
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(energy_color))
                
                # 主能量点(3px)
                painter.drawEllipse(energy_point, 3, 3)
                
                # 拖尾效果
                for j in range(1, 3):
                    tail_t = (t - j*0.15) % 1.0
                    if tail_t < 0: continue
                    tail_point = self.cubic_bezier(p0, p1, p2, p3, tail_t)
                    alpha = 200 - j*80
                    size = max(1, 3 - j)
                    if alpha > 0:
                        painter.setBrush(QBrush(QColor(255, 215, 0, alpha)))
                        painter.drawEllipse(tail_point, size, size)
            
            # 2. 绘制节点
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
    
            # 3. 绘制文字
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
