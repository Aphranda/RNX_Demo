from PyQt5.QtWidgets import QLabel, QSizePolicy
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt

class AutoFontSizeLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._min_font_size = 6
        self._max_font_size = 20
        self._default_font_size = 20
        self._content_margin = 10
        self._fixed_height = 40  # 新增：固定高度值
        
        # 设置大小策略：水平扩展，垂直固定
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # 设置固定高度
        self.setFixedHeight(self._fixed_height)
        
        self.setAlignment(Qt.AlignCenter)
        self.setProperty("class", "AutoFontSizeLabel")
        
        # 初始调整
        self.adjust_font_size()

    def resizeEvent(self, event):
        # 保持高度不变，只处理宽度变化
        if event.oldSize().width() != event.size().width():
            self.adjust_font_size()
        super().resizeEvent(event)

    def setText(self, text):
        super().setText(text)
        self.adjust_font_size()

    def adjust_font_size(self):
        text = self.text()
        if not text or self.width() <= 10:
            return
        
        # 计算可用宽度（考虑边距）
        available_width = self.width() - 2 * self._content_margin
        
        # 1. 首先检查默认字体大小是否适配
        font = QFont(self.font())
        font.setPointSize(self._default_font_size)
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(text)
        
        # 如果默认字体大小完美适配
        if text_width <= available_width:
            # 2. 检查是否可以放大字体
            best_size = self._find_best_font_size(
                min_size=self._default_font_size, 
                max_size=self._max_font_size, 
                text=text, 
                available_width=available_width
            )
        else:
            # 3. 默认字体太大，需要缩小
            best_size = self._find_best_font_size(
                min_size=self._min_font_size, 
                max_size=self._default_font_size, 
                text=text, 
                available_width=available_width
            )
        
        # 应用最佳字体大小
        self._apply_font_size(best_size)
    
    def _find_best_font_size(self, min_size, max_size, text, available_width):
        """在指定范围内找到最佳字体大小"""
        font = QFont(self.font())
        low, high = min_size, max_size
        best_size = min_size
        
        while low <= high:
            mid = (low + high) // 2
            font.setPointSize(mid)
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(text)
            
            if text_width <= available_width:
                best_size = mid  # 当前大小可用
                low = mid + 1   # 尝试更大的字体
            else:
                high = mid - 1   # 尝试更小的字体
        
        return best_size
    
    def _apply_font_size(self, size):
        # 应用新字体
        self.setStyleSheet(f"""
            AutoFontSizeLabel {{
                font-size: {size}pt;
                background: {self.palette().color(self.backgroundRole()).name()};
                color: {self.palette().color(self.foregroundRole()).name()};
            }}
        """)
