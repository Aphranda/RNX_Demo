from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import (QColor, QPainter, QPen, QFont, 
                         QLinearGradient, QPainterPath)
from PyQt5.QtCore import Qt, QPointF, QRectF

class SimpleLinkDiagram(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(380)
        self.setMinimumWidth(360)
        self.current_link = "FEED_X_THETA"
        self.setStyleSheet("background: transparent;")

        # 新增：声明不透明绘制
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def set_link(self, link_mode):
        normalized_link = link_mode.upper().replace("__", "_")
        self.current_link = normalized_link
        self.update()

    def paintEvent(self, a0):
        super().paintEvent(a0)
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        
        # 配色方案
        node_color = QColor("#4285f4")
        node_border = QColor("#3367d6")
        node_text = QColor("#202124")
        line_color = QColor("#dadce0")
        highlight_color = QColor("#ea4335")
        highlight_text = QColor("#ea4335")
        
        # 字体设置
        font = QFont("Segoe UI", 10, QFont.Medium)
        painter.setFont(font)

        # 布局参数
        start_x = 60
        start_y = 15
        node_w = 40
        node_h = 24
        gap_y = 36

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
        node_x = com_cx + 150
        for i, (name, link_key) in enumerate(node_list):
            ny = start_y + i * (node_h + gap_y)
            
            # 1. 先绘制连线（此时不设置任何画刷）
            line_pen = QPen(highlight_color if self.current_link == link_key else line_color, 
                        3 if self.current_link == link_key else 2)
            line_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(line_pen)
            painter.setBrush(Qt.NoBrush)  # 明确禁用画刷
            
            path = QPainterPath()
            path.moveTo(com_cx + node_w//2, com_cy)
            ctrl1_x = com_cx + 50
            ctrl2_x = node_x - 50
            path.cubicTo(
                QPointF(ctrl1_x, com_cy),
                QPointF(ctrl2_x, ny + node_h//2),
                QPointF(node_x - node_w//2, ny + node_h//2)
            )
            painter.drawPath(path)
    
            # 2. 再绘制节点（此时才设置渐变画刷）
            if self.current_link == link_key:
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
    
            # 3. 最后绘制文字（重置画刷）
            text_pen = QPen(highlight_text if self.current_link == link_key else node_text, 1)
            painter.setPen(text_pen)
            painter.setBrush(Qt.NoBrush)  # 文字不需要画刷
            painter.drawText(node_x + node_w//2 + 6, ny, 80, node_h, 
                        Qt.AlignVCenter | Qt.AlignLeft, name)
    
        painter.end()