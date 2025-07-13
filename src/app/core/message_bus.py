# file: core/message_bus.py
from PyQt5.QtCore import QObject, pyqtSignal

class MessageBus(QObject):
    """
    全局消息总线，使用信号槽机制实现发布/订阅模式
    """
    # 定义消息信号，str为消息类型，object为消息内容
    message_published = pyqtSignal(str, object)

    def __init__(self):
        super().__init__()
        self._subscribers = {}

    def subscribe(self, message_type, callback):
        """订阅特定类型的消息"""
        if message_type not in self._subscribers:
            self._subscribers[message_type] = []
        self._subscribers[message_type].append(callback)
        self.message_published.connect(
            lambda msg_type, data: callback(data) if msg_type == message_type else None
        )

    def publish(self, message_type, data=None):
        """发布消息"""
        self.message_published.emit(message_type, data)

# 创建全局消息总线实例
bus = MessageBus()
