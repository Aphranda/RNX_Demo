from PyQt5.QtWidgets import QComboBox, QSizePolicy
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtCore import Qt

class AutoFontSizeComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._min_font_size = 8
        self._max_font_size = 14
        self._content_margin = 5
        self._default_font_size = self.font().pointSize()
        
    def showPopup(self):
        # 在显示下拉菜单前调整字体大小
        self.adjust_popup_font()
        super().showPopup()
        
    def adjust_popup_font(self):
        # 获取下拉视图
        view = self.view()
        if not view:
            return
            
        # 计算最大文本宽度
        metrics = QFontMetrics(view.font())
        max_width = max(metrics.horizontalAdvance(self.itemText(i)) 
                      for i in range(self.count())) if self.count() > 0 else 0
        
        # 计算可用宽度
        available_width = view.width() - 2 * self._content_margin
        
        # 只有当文本宽度大于可用宽度时才缩小字体
        if max_width > available_width and available_width > 0:
            # 计算合适的字体大小
            ratio = available_width / max_width
            new_size = max(self._min_font_size, int(self._default_font_size * ratio))
            
            font = view.font()
            font.setPointSize(new_size)
            view.setFont(font)
        else:
            # 恢复默认字体大小
            font = view.font()
            font.setPointSize(self._default_font_size)
            view.setFont(font)
            
    def resizeEvent(self, event):
        # 主控件也调整字体
        self.adjust_main_font()
        super().resizeEvent(event)
        
    def adjust_main_font(self):
        current_text = self.currentText()
        if not current_text:
            return
            
        metrics = QFontMetrics(self.font())
        text_width = metrics.horizontalAdvance(current_text)
        available_width = self.width() - 2 * self._content_margin
        
        # 只有当文本宽度大于可用宽度时才缩小字体
        if text_width > available_width and available_width > 0:
            ratio = available_width / text_width
            new_size = max(self._min_font_size, int(self._default_font_size * ratio))
            
            font = self.font()
            font.setPointSize(new_size)
            self.setFont(font)
        else:
            # 恢复默认字体大小
            font = self.font()
            font.setPointSize(self._default_font_size)
            self.setFont(font)
