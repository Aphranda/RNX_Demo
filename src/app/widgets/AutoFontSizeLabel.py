
from PyQt5.QtWidgets import QLabel,QSizePolicy
from PyQt5.QtGui import QFont, QFontMetrics

class AutoFontSizeLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._min_font_size = 6
        self._max_font_size = 72  # 增大最大值
        self._content_margin = 10  # 增加边距
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setProperty("class", "AutoFontSizeLabel")
        
        # 初始调整
        self.adjust_font_size()
 
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_font_size()
 
    def setText(self, text):
        super().setText(text)
        self.adjust_font_size()
 
    def adjust_font_size(self):
        text = self.text()
        if not text or self.width() <= 10:
            return
 
        # 计算可用空间（考虑边距和样式表padding）
        available_width = self.width() - 2 * self._content_margin
        available_height = self.height() - 2 * self._content_margin
        
        # 动态计算基准大小（基于控件高度）
        base_size = min(self._max_font_size, 
                      max(self._min_font_size, 
                          int(self.height() * 0.5)))  # 高度50%作为基准
 
        # 二进制搜索最佳大小
        low, high = self._min_font_size, self._max_font_size
        best_size = base_size
        font = QFont(self.font())
        
        while low <= high:
            mid = (low + high) // 2
            font.setPointSize(mid)
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(text)
            text_height = metrics.height()
            
            if text_width <= available_width and text_height <= available_height:
                best_size = mid
                low = mid + 1
            else:
                high = mid - 1
 
        # 应用新字体（同时设置font和样式表）
        font.setPointSize(best_size)
        self.setFont(font)
        
        # 关键步骤：通过样式表叠加修改（不影响其他样式）
        self.setStyleSheet(f"""
            AutoFontSizeLabel {{
                font-size: {best_size}pt;
                border: 2px solid #42a5f5;
                border-radius: 8px;
                background: #f5faff;
                background: {self.palette().color(self.backgroundRole()).name()};
                padding: 4px 10px;
                min-width: 60px;
                min-height: 24px;
                font-weight: bold;
                color: #42a5f5;
                color: {self.palette().color(self.foregroundRole()).name()};
            }}
        """)
