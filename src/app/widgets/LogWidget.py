from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QToolBar, QTextEdit, QComboBox, 
    QLabel, QAction, QLineEdit, QMenu, QFileDialog
)
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor, QFont, QIcon
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from datetime import datetime
import sys

class LogWidget(QWidget):
    """
    综合日志控件，支持：
    - 多级日志显示（不同颜色）
    - 工具栏控制（字体、过滤、换行等）
    - 日志搜索与高亮
    - 右键菜单操作
    - 日志导出
    - 自动滚动控制
    """
    
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
    errorLogged = pyqtSignal(str)  # (error_message)

    def __init__(self, parent=None, max_lines=5000, default_level="INFO"):
        super().__init__(parent)
        self.max_lines = max_lines
        self._auto_scroll = True
        self._setup_ui()
        self._init_settings(default_level)
        self._connect_signals()

    def _setup_ui(self):
        """初始化UI组件"""
        # 主布局
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)

        # 工具栏
        self._setup_toolbar()
        
        # 文本编辑区域
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QTextEdit.NoWrap)
        self.text_edit.setFont(QFont("Consolas", 10))
        self.text_edit.setContextMenuPolicy(Qt.CustomContextMenu)
        
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.text_edit)

    def _setup_toolbar(self):
        """初始化工具栏"""
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)

        # 日志级别过滤
        self.level_combo = QComboBox()
        self.level_combo.addItem("ALL", "ALL")
        for level, (_, display_name) in self.LEVELS.items():
            self.level_combo.addItem(display_name, level)
        self.toolbar.addWidget(QLabel("级别:"))
        self.toolbar.addWidget(self.level_combo)

        # 字体大小
        self.font_combo = QComboBox()
        self.font_combo.addItems(map(str, range(8, 16)))
        self.font_combo.setCurrentText("10")
        self.toolbar.addWidget(QLabel("字体:"))
        self.toolbar.addWidget(self.font_combo)

        # 自动换行
        self.wrap_action = QAction(QIcon.fromTheme("format-justify-fill"), "自动换行", self)
        self.wrap_action.setCheckable(True)
        self.toolbar.addAction(self.wrap_action)

        # 时间戳
        self.timestamp_action = QAction(QIcon.fromTheme("clock"), "时间戳", self)
        self.timestamp_action.setCheckable(True)
        self.timestamp_action.setChecked(True)
        self.toolbar.addAction(self.timestamp_action)

        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索...")
        self.search_edit.setMaximumWidth(200)
        self.toolbar.addWidget(self.search_edit)
        self.search_action = QAction(QIcon.fromTheme("edit-find"), "搜索", self)
        self.toolbar.addAction(self.search_action)

        # 清空按钮
        self.clear_action = QAction(QIcon.fromTheme("edit-clear"), "清空", self)
        self.toolbar.addAction(self.clear_action)

    def _init_settings(self, default_level):
        """初始化默认设置"""
        self.current_level = default_level
        self.enabled_levels = set(self.LEVELS.keys())
        self._highlight_format = QTextCharFormat()
        self._highlight_format.setBackground(QColor("#FFFF00"))

    def _connect_signals(self):
        """连接信号与槽"""
        # 工具栏信号
        self.level_combo.currentTextChanged.connect(self._update_log_level)
        self.font_combo.currentTextChanged.connect(self._update_font_size)
        self.wrap_action.toggled.connect(self._toggle_word_wrap)
        self.timestamp_action.toggled.connect(lambda x: setattr(self, "_show_timestamps", x))
        self.search_action.triggered.connect(self._search_text)
        self.search_edit.returnPressed.connect(self._search_text)
        self.clear_action.triggered.connect(self.clear)

        # 文本编辑区域信号
        self.text_edit.customContextMenuRequested.connect(self._show_context_menu)
        self.text_edit.verticalScrollBar().valueChanged.connect(
            lambda: setattr(self, "_auto_scroll", 
            self.text_edit.verticalScrollBar().value() == self.text_edit.verticalScrollBar().maximum())
        )

    # -------------------- 核心功能 --------------------
    def log(self, message, level="INFO"):
        """
        记录日志
        :param message: 日志消息
        :param level: 日志级别 (DEBUG/INFO/SUCCESS/WARNING/ERROR/CRITICAL/SEND/RECV)
        """
        if level not in self.LEVELS or level not in self.enabled_levels:
            return

        color, _ = self.LEVELS[level]
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        html = []
        if hasattr(self, "_show_timestamps") and self._show_timestamps:
            html.append(f'<span style="color:gray;">[{timestamp}]</span>')
        html.append(f'<span style="color:{color};font-weight:bold;">[{level}]</span>')
        html.append(f'<span style="color:{color};">{message}</span>')
        
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(" ".join(html) + "<br>")
        
        # 自动滚动
        if self._auto_scroll:
            self.text_edit.ensureCursorVisible()
        
        # 限制最大行数
        if self.text_edit.document().blockCount() > self.max_lines:
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
        
        # 触发错误信号
        if level in ("ERROR", "CRITICAL"):
            self.errorLogged.emit(message)

    def clear(self):
        """清空日志"""
        self.text_edit.clear()

    # -------------------- 工具栏功能 --------------------
    def _update_log_level(self):
        """更新显示的日志级别"""
        level = self.level_combo.currentData()
        if level == "ALL":
            self.enabled_levels = set(self.LEVELS.keys())
        else:
            self.enabled_levels = {level}

    def _update_font_size(self, size):
        """更新字体大小"""
        font = self.text_edit.font()
        font.setPointSize(int(size))
        self.text_edit.setFont(font)

    def _toggle_word_wrap(self, enabled):
        """切换自动换行"""
        self.text_edit.setLineWrapMode(QTextEdit.WidgetWidth if enabled else QTextEdit.NoWrap)

    def _search_text(self):
        """搜索文本并高亮"""
        text = self.search_edit.text().strip()
        if not text:
            return
        
        # 清除旧的高亮
        self._clear_highlights()
        
        # 搜索并高亮
        cursor = self.text_edit.document().find(text)
        while not cursor.isNull():
            cursor.mergeCharFormat(self._highlight_format)
            cursor = self.text_edit.document().find(text, cursor)

    def _clear_highlights(self):
        """清除所有高亮"""
        cursor = self.text_edit.textCursor()
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(QTextCharFormat())

    # -------------------- 右键菜单 --------------------
    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        
        # 标准操作
        copy_action = menu.addAction("复制")
        copy_action.triggered.connect(self._copy_selected)
        
        select_all_action = menu.addAction("全选")
        select_all_action.triggered.connect(self.text_edit.selectAll)
        
        menu.addSeparator()
        
        # 导出操作
        export_action = menu.addAction("导出日志...")
        export_action.triggered.connect(self._export_log)
        
        menu.exec_(self.text_edit.mapToGlobal(pos))

    def _copy_selected(self):
        """复制选中文本"""
        self.text_edit.copy()

    def _export_log(self):
        """导出日志到文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", "", "文本文件 (*.txt);;HTML文件 (*.html)"
        )
        if not file_path:
            return
        
        try:
            if file_path.endswith(".html"):
                content = self.text_edit.toHtml()
            else:
                content = self.text_edit.toPlainText()
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            self.log(f"日志已导出到: {file_path}", "SUCCESS")
        except Exception as e:
            self.log(f"导出失败: {str(e)}", "ERROR")

    # -------------------- 实用方法 --------------------
    def set_max_lines(self, max_lines):
        """设置最大日志行数"""
        self.max_lines = max(100, int(max_lines))

    def set_auto_scroll(self, enabled):
        """设置是否自动滚动到底部"""
        self._auto_scroll = bool(enabled)
        if enabled:
            self.text_edit.ensureCursorVisible()
