from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QToolBar, QTextEdit, QComboBox,
    QLabel, QAction, QLineEdit, QMenu
)
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor, QFont, QIcon
from PyQt5.QtCore import Qt, pyqtSignal

class LogWidgetView(QWidget):
    """日志控件的纯UI部分，不包含业务逻辑"""
    
    # 定义UI交互信号
    level_changed = pyqtSignal(str)  # 日志级别改变
    font_size_changed = pyqtSignal(str)  # 字体大小改变
    word_wrap_toggled = pyqtSignal(bool)  # 自动换行切换
    timestamp_toggled = pyqtSignal(bool)  # 时间戳显示切换
    search_requested = pyqtSignal(str)  # 搜索请求
    clear_requested = pyqtSignal()  # 清空请求
    export_requested = pyqtSignal(str)  # 导出请求(文件路径)
    copy_requested = pyqtSignal()  # 复制请求

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_internal_signals()

    def _setup_ui(self):
        """初始化UI组件"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)

        # 工具栏
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)

        # 日志级别过滤
        self.level_combo = QComboBox()
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

        # 文本编辑区域
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QTextEdit.NoWrap)
        self.text_edit.setFont(QFont("Consolas", 10))
        self.text_edit.setContextMenuPolicy(Qt.CustomContextMenu)

        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.text_edit)

    def _connect_internal_signals(self):
        """连接内部UI信号"""
        self.level_combo.currentTextChanged.connect(self.level_changed)
        self.font_combo.currentTextChanged.connect(self.font_size_changed)
        self.wrap_action.toggled.connect(self.word_wrap_toggled)
        self.timestamp_action.toggled.connect(self.timestamp_toggled)
        self.search_action.triggered.connect(self._on_search_requested)
        self.search_edit.returnPressed.connect(self._on_search_requested)
        self.clear_action.triggered.connect(self.clear_requested)
        self.text_edit.customContextMenuRequested.connect(self._show_context_menu)

    def _on_search_requested(self):
        """触发搜索信号"""
        search_str = self.search_edit.text().strip()
        if search_str:
            self.search_requested.emit(search_str)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        copy_action = menu.addAction("复制")
        copy_action.triggered.connect(self.copy_requested)
        select_all_action = menu.addAction("全选")
        select_all_action.triggered.connect(self.text_edit.selectAll)
        menu.addSeparator()
        export_action = menu.addAction("导出日志...")
        export_action.triggered.connect(self._on_export_requested)
        menu.exec_(self.text_edit.mapToGlobal(pos))

    def _on_export_requested(self):
        """触发导出信号"""
        self.export_requested.emit("")  # 空路径由控制器处理

    # -------------------- 公共方法 --------------------
    def append_html(self, html_content):
        """追加HTML内容到日志"""
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html_content + "<br>")

    def clear_content(self):
        """清空日志内容"""
        self.text_edit.clear()

    def set_word_wrap(self, enabled):
        """设置自动换行"""
        self.text_edit.setLineWrapMode(QTextEdit.WidgetWidth if enabled else QTextEdit.NoWrap)

    def set_font_size(self, size):
        """最终可靠的字体大小设置方法"""
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                font-family: Consolas;
                font-size: {size}pt !important;
            }}
        """)
        # 保留程序设置作为备份
        self.text_edit.setFont(QFont("Consolas", int(size)))


    def scroll_to_bottom(self):
        """滚动到底部"""
        self.text_edit.ensureCursorVisible()

    def set_levels(self, levels):
        """设置可选的日志级别"""
        self.level_combo.clear()
        self.level_combo.addItem("ALL", "ALL")
        for level, (_, display_name) in levels.items():
            self.level_combo.addItem(display_name, level)

    def highlight_text(self, search_str, options):
        """高亮匹配文本"""
        doc = self.text_edit.document()
        cursor = QTextCursor(doc)
        
        format = QTextCharFormat()
        format.setBackground(QColor(255, 255, 0, 100))
        format.setFontWeight(QFont.Bold)
        
        while True:
            cursor = doc.find(search_str, cursor, options)
            if cursor.isNull():
                break
            cursor.mergeCharFormat(format)

    def clear_highlights(self):
        """清除所有高亮"""
        cursor = self.text_edit.textCursor()
        original_position = cursor.position()
        cursor.movePosition(QTextCursor.Start)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        format = QTextCharFormat()
        format.setBackground(Qt.transparent)
        cursor.mergeCharFormat(format)
        cursor.setPosition(original_position)
        self.text_edit.setTextCursor(cursor)
