from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QColor, QPainter, QPen, QFont
from PyQt5.QtCore import Qt, QPointF

class SimpleLinkDiagram(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 缩小尺寸
        self.setMinimumHeight(400)   # 从600缩小到400
        self.setMinimumWidth(350)    # 从500缩小到350
        self.current_link = "FEED_X_THETA"

    def set_link(self, link_mode):
        normalized_link = link_mode.upper().replace("__", "_")
        self.current_link = normalized_link
        self.update()

    def paintEvent(self, a0):
        super().paintEvent(a0)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 颜色定义
        node_color = QColor("#0078d7")
        node_border = QColor("#005fa1")
        node_text = QColor("#222222")
        line_color = QColor("#b0b0b0")
        highlight_color = QColor("#ff4b1f")
        highlight_text = QColor("#ff4b1f")
        shadow_color = QColor(0, 0, 0, 30)

        # 缩小字体大小
        font = QFont("Segoe UI", 10)  # 从13缩小到10
        painter.setFont(font)

        # 调整布局参数
        start_x = 70     # 从100缩小到70
        start_y = 15     # 从20缩小到15
        node_w = 40      # 从48缩小到40
        node_h = 24      # 从28缩小到24
        gap_y = 36       # 从44缩小到36

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

        # 画COM节点阴影
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow_color)
        painter.drawEllipse(com_cx - node_w // 2 + 2, com_cy - node_h // 2 + 2, node_w, node_h)

        # 画COM节点
        painter.setPen(QPen(node_border, 2))
        painter.setBrush(node_color)
        painter.drawEllipse(com_cx - node_w // 2, com_cy - node_h // 2, node_w, node_h)
        painter.setPen(QPen(node_text, 1))
        painter.drawText(com_cx - node_w // 2 - 45, com_cy - node_h // 2, 45, node_h, 
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "COM")

        # 画节点和连线
        node_x = com_cx + 160  # 从220缩小到160
        for i, (name, link_key) in enumerate(node_list):
            ny = start_y + i * (node_h + gap_y)
            
            # 连线
            line_pen = QPen(highlight_color if self.current_link == link_key else line_color, 
                           3 if self.current_link == link_key else 2)
            painter.setPen(line_pen)
            
            # 曲线控制点
            ctrl1_x = com_cx + 45  # 从60缩小到45
            ctrl2_x = node_x - 45  # 从60缩小到45
            painter.drawPolyline(
                QPointF(com_cx + node_w // 2, com_cy),
                QPointF(ctrl1_x, com_cy),
                QPointF(ctrl2_x, ny + node_h // 2),
                QPointF(node_x - node_w // 2, ny + node_h // 2)
            )

            # 节点阴影
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow_color)
            painter.drawEllipse(node_x - node_w // 2 + 2, ny + 2, node_w, node_h)

            # 节点
            if self.current_link == link_key:
                painter.setPen(QPen(highlight_color, 2))
                painter.setBrush(QColor("white"))
            else:
                painter.setPen(QPen(node_border, 1))
                painter.setBrush(QColor("white"))
            painter.drawEllipse(node_x - node_w // 2, ny, node_w, node_h)

            # 节点文字
            text_pen = QPen(highlight_text if self.current_link == link_key else node_text, 
                          2 if self.current_link == link_key else 1)
            painter.setPen(text_pen)
            painter.drawText(node_x + node_w // 2 + 6, ny, 80, node_h,  # 从100缩小到80
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)

        painter.end()
