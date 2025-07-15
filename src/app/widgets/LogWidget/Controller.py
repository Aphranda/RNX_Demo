from PyQt5.QtCore import QTimer, QObject, pyqtSignal
from PyQt5.QtGui import QTextCursor, QTextDocument
from datetime import datetime
from PyQt5.QtWidgets import QFileDialog

class LogWidgetController(QObject):
    """日志控件的业务逻辑控制器"""
    
    # 定义日志级别
    LEVELS = {
        "DEBUG":    ("#666666", "Debug"),
        "INFO":     ("#000000", "Info"),
        "SUCCESS":  ("#228B22", "Success"),
        "WARNING":  ("#FF8C00", "Warning"),
        "ERROR":    ("#FF0000", "Error"),
        "CRITICAL": ("#8B0000", "Critical"),
        "SEND":     ("#0078D7", "Send"),
        "RECV":     ("#8E44AD", "Receive")
    }

    # 信号：当日志级别超过阈值时触发
    error_logged = pyqtSignal(str)

    def __init__(self, view):
        super().__init__()
        self.view = view
        self.max_lines = 5000
        self._auto_scroll = True
        self._show_timestamps = True
        self.enabled_levels = set(self.LEVELS.keys())
        
        self._init_view()
        self._connect_signals()

    def _init_view(self):
        """初始化视图状态"""
        self.view.set_levels(self.LEVELS)
        self.view.set_word_wrap(False)
        self.view.set_font_size(10)


    def _connect_signals(self):
        """连接视图信号到控制器槽"""
        self.view.level_combo.currentTextChanged.connect(lambda: self._update_log_level())  # 无参数传递
        self.view.font_size_changed.connect(self._handle_font_size_change)
        self.view.word_wrap_toggled.connect(self.view.set_word_wrap)
        self.view.timestamp_toggled.connect(lambda x: setattr(self, "_show_timestamps", x))
        self.view.search_requested.connect(self._search_text)
        self.view.clear_requested.connect(self.clear)
        self.view.export_requested.connect(self._export_log)
        self.view.copy_requested.connect(self.view.text_edit.copy)
        
        # 滚动条自动滚动检测
        scroll_bar = self.view.text_edit.verticalScrollBar()
        scroll_bar.valueChanged.connect(
            lambda: setattr(self, "_auto_scroll", 
            abs(scroll_bar.value() - scroll_bar.maximum()) < 10)
        )

    def _handle_font_size_change(self, size):
        """处理字体大小变化"""
        self.view.set_font_size(size)

    def log(self, message, level="INFO"):
        """记录日志"""
        if level not in self.LEVELS or level not in self.enabled_levels:
            return

        color, _ = self.LEVELS[level]
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        html = []
        if self._show_timestamps:
            html.append(f'<span style="color:gray;">[{timestamp}]</span>')
        html.append(f'<span style="color:{color};font-weight:bold;">[{level}]</span>')
        html.append(f'<span style="color:{color};">{message}</span>')
        
        self.view.append_html(" ".join(html))
        
        # 自动滚动
        if self._auto_scroll:
            QTimer.singleShot(10, self.view.scroll_to_bottom)
        
        # 限制最大行数
        if self.view.text_edit.document().blockCount() > self.max_lines:
            cursor = self.view.text_edit.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
        
        # 触发错误信号
        if level in ("ERROR", "CRITICAL"):
            self.error_logged.emit(message)

    def clear(self):
        """清空日志"""
        self.view.clear_content()

    def _update_log_level(self, level=None):
        """更新显示的日志级别
        
        Args:
            level (str, optional): 要设置的级别。如果为None则从UI获取
        """
        if level is None:
            level = self.view.level_combo.currentData()
        
        if level == "ALL":
            self.enabled_levels = set(self.LEVELS.keys())
        else:
            self.enabled_levels = {level}
        
        # 更新UI显示
        if level and level != "ALL":
            index = self.view.level_combo.findData(level)
            if index >= 0:
                self.view.level_combo.setCurrentIndex(index)


    def _search_text(self, search_str):
        """搜索文本并高亮"""
        self.view.clear_highlights()
        
        doc = self.view.text_edit.document()
        cursor = self.view.text_edit.textCursor()
        options = QTextDocument.FindCaseSensitively
        
        # 第一次搜索：从当前位置到文档末尾
        found_cursor = doc.find(search_str, cursor, options)
        
        # 第二次搜索：如果没找到，从文档开头再搜索
        if found_cursor.isNull():
            cursor = QTextCursor(doc)
            found_cursor = doc.find(search_str, cursor, options)
            if found_cursor.isNull():
                self.log(f"未找到: {search_str}", "WARNING")
                return
        
        # 高亮所有匹配项
        self.view.highlight_text(search_str, options)
        
        # 精确定位到匹配项
        self.view.text_edit.setTextCursor(found_cursor)
        self.view.text_edit.ensureCursorVisible()

    def _export_log(self, file_path):
        """导出日志到文件"""
        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(
                self.view, "导出日志", "", "文本文件 (*.txt);;HTML文件 (*.html)"
            )
            if not file_path:
                return
        
        try:
            if file_path.endswith(".html"):
                content = self.view.text_edit.toHtml()
            else:
                content = self.view.text_edit.toPlainText()
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            self.log(f"日志已导出到: {file_path}", "SUCCESS")
        except Exception as e:
            self.log(f"导出失败: {str(e)}", "ERROR")

    def set_max_lines(self, max_lines):
        """设置最大日志行数"""
        self.max_lines = max(100, int(max_lines))

    def set_auto_scroll(self, enabled):
        """设置是否自动滚动到底部"""
        self._auto_scroll = bool(enabled)
        if enabled:
            self.view.scroll_to_bottom()

