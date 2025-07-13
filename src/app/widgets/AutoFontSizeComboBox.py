
from PyQt5.QtWidgets import QComboBox,QSizePolicy
from PyQt5.QtGui import  QFontMetrics

class AutoFontSizeComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._min_font_size = 8
        self._max_font_size = 14
        self._content_margin = 5
        
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
                      for i in range(self.count()))
        
        # 计算可用宽度
        available_width = view.width() - 2 * self._content_margin
        
        if max_width > available_width and available_width > 0:
            # 计算合适的字体大小
            ratio = available_width / max_width
            new_size = max(self._min_font_size,
                          min(self._max_font_size,
                              int(view.font().pointSize() * ratio)))
            
            font = view.font()
            font.setPointSize(new_size)
            view.setFont(font)
            
    def resizeEvent(self, event):
        # 主控件也调整字体
        self.adjust_main_font()
        super().resizeEvent(event)
        
    def adjust_main_font(self):
        metrics = QFontMetrics(self.font())
        text_width = metrics.horizontalAdvance(self.currentText())
        available_width = self.width() - 2 * self._content_margin
        
        if text_width > available_width and available_width > 0:
            ratio = available_width / text_width
            new_size = max(self._min_font_size,
                          min(self._max_font_size,
                              int(self.font().pointSize() * ratio)))
            
            font = self.font()
            font.setPointSize(new_size)
            self.setFont(font)
