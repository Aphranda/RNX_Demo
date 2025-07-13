
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QStatusBar, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout, 
    QSizePolicy, QMessageBox, QCheckBox, QToolBar, QAction, QFileDialog
)
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QFontMetrics, QTextCursor, QTextCharFormat, QIcon
from PyQt5.QtCore import Qt, QPointF, QThread, pyqtSignal, QMutex, QSize
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtCore import QRegExp
import sys, os, psutil
import socket, select
import datetime
import time
import atexit
import hashlib
import shutil
import json, struct
import math
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone


class SimpleLinkDiagram(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(600)   # 原600，放大1.2倍
        self.setMinimumWidth(500)    # 原500，放大1.2倍
        self.current_link = "FEED_X_THETA"

    def set_link(self, link_mode):
        # 确保链路模式与类中定义的名称一致
        normalized_link = link_mode.upper().replace("__", "_")  # 处理可能的双下划线
        self.current_link = normalized_link
        self.update()


    def paintEvent(self, a0):
        super().paintEvent(a0)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # Fluent风格配色
        node_color = QColor("#0078d7")
        node_border = QColor("#005fa1")
        node_text = QColor("#222222")
        line_color = QColor("#b0b0b0")
        highlight_color = QColor("#ff4b1f")
        highlight_text = QColor("#ff4b1f")
        shadow_color = QColor(0, 0, 0, 30)

        font = QFont("Segoe UI", 13)  # 原11，放大1.2倍
        painter.setFont(font)

        # 参数（全部放大1.2倍）
        start_x = int(100)
        start_y = int(20)
        node_w = int(48)
        node_h = int(28)
        gap_y = int(44)

        # 八个节点
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

        # 画COM节点阴影
        com_cx = start_x
        com_cy = start_y + (len(node_list) * (node_h + gap_y) - gap_y) // 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow_color)
        painter.drawEllipse(com_cx - node_w // 2 + 3, com_cy - node_h // 2 + 3, node_w, node_h)

        # 画COM节点
        painter.setPen(QPen(node_border, 2))
        painter.setBrush(node_color)
        painter.drawEllipse(com_cx - node_w // 2, com_cy - node_h // 2, node_w, node_h)
        painter.setPen(QPen(node_text, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawText(com_cx - node_w // 2 - int(60 * 1.2), com_cy - node_h // 2, int(56 * 1.2), node_h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "COM")

        # 画竖直排列的8个节点及连线
        node_x = com_cx + int(220 * 1.2)
        for i, (name, link_key) in enumerate(node_list):
            ny = start_y + i * (node_h + gap_y)
            # 连线
            if self.current_link == link_key:
                painter.setPen(QPen(highlight_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            else:
                painter.setPen(QPen(line_color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            # Fluent风格曲线
            ctrl1_x = com_cx + int(60 * 1.2)
            ctrl2_x = node_x - int(60 * 1.2)
            painter.drawPolyline(
                *[
                    QPointF(com_cx + node_w // 2, com_cy),
                    QPointF(ctrl1_x, com_cy),
                    QPointF(ctrl2_x, ny + node_h // 2),
                    QPointF(node_x - node_w // 2, ny + node_h // 2)
                ]
            )
            # 节点阴影
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow_color)
            painter.drawEllipse(node_x - node_w // 2 + 3, ny + 3, node_w, node_h)
            # 节点
            if self.current_link == link_key:
                painter.setPen(QPen(highlight_color, 2))
                painter.setBrush(QColor("white"))
            else:
                painter.setPen(QPen(node_border, 1))
                painter.setBrush(QColor("white"))
            painter.drawEllipse(node_x - node_w // 2, ny, node_w, node_h)
            # 文字
            if self.current_link == link_key:
                painter.setPen(QPen(highlight_text, 2))
            else:
                painter.setPen(QPen(node_text, 1))
            painter.drawText(node_x + node_w // 2 + 8, ny, int(100 * 1.2), node_h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)

        painter.end()
