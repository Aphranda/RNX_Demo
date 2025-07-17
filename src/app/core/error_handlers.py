# app/core/error_handlers.py
from PyQt5.QtWidgets import QMessageBox
from core.exceptions.base import RNXError

def handle_error(parent_window, exc: Exception):
    """统一错误处理入口"""
    if isinstance(exc, RNXError):
        title = f"系统错误 RNX-{exc.code}"
        detail = str(exc)
    else:
        title = "未知错误"
        detail = f"{type(exc).__name__}: {str(exc)}"
    
    QMessageBox.critical(
        parent_window,
        title,
        detail,
        buttons=QMessageBox.Ok,
        defaultButton=QMessageBox.Ok
    )
