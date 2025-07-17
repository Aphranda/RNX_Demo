# app/core/threads.py
from PyQt5.QtCore import QThread, pyqtSignal

class WorkerThread(QThread):
    """通用工作线程"""
    def __init__(self, task, on_finished=None, on_error=None):
        super().__init__()
        self._task = task
        self._on_finished = on_finished
        self._on_error = on_error

    def run(self):
        try:
            self._task()
            if self._on_finished:
                self._on_finished()
        except Exception as e:
            if self._on_error:
                self._on_error(e)
