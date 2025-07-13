# file: widgets/factory.py
from core.message_bus import bus
from .AutoFontSizeComboBox import AutoFontSizeComboBox
from .AutoFontSizeLabel import AutoFontSizeLabel

class WidgetFactory:
    def __init__(self):
        bus.subscribe("create_autofont_widgets", self.create_widgets)
        
    def create_widgets(self, params):
        """响应创建控件的消息"""
        parent = params.get("parent")
        layout = params.get("layout")
        
        combo = AutoFontSizeComboBox(parent)
        label = AutoFontSizeLabel(parent)
        
        layout.addWidget(combo)
        layout.addWidget(label)
