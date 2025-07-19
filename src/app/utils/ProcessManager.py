import os
import sys
import atexit
import psutil

from PyQt5.QtWidgets import (
    QApplication, QMessageBox
)
from PyQt5.QtGui import QIcon


class ProcessManager:
    """进程管理单例类，负责检测和防止重复运行"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self.current_pid = os.getpid()
            self.script_path = os.path.abspath(sys.argv[0])
            self.lock_file = os.path.join(
                os.path.dirname(self.script_path),
                f".{os.path.basename(self.script_path)}.lock"
            )
            self.lock_fd = None
    
    def check_duplicate_instance(self):
        """检查是否有重复实例运行（支持跨平台）"""
        # 方法1：使用进程名检测（适用于所有平台）
        duplicate_count = self._count_process_instances()
        
        # 方法2：使用文件锁（防止终端多开）
        if not self._acquire_file_lock():
            duplicate_count += 1
        
        if duplicate_count > 2:
            self._show_warning_dialog()
            return True
        return False
    
    def _count_process_instances(self):
        """统计当前脚本的运行实例数"""
        count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # 跨平台兼容性处理
                cmdline = proc.info.get('cmdline', [])
                if (cmdline and 
                    os.path.abspath(cmdline[0]) == self.script_path and
                    proc.info['pid'] != self.current_pid):
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, IndexError):
                continue
        return count
    
    def _acquire_file_lock(self):
        """使用文件锁机制（支持Windows和Linux）"""
        try:
            if os.name == 'nt':  # Windows
                self.lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            else:  # Unix-like
                self.lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o644)
            atexit.register(self._release_file_lock)
            return True
        except OSError:
            return False
    
    def _release_file_lock(self):
        """释放文件锁"""
        if self.lock_fd:
            os.close(self.lock_fd)
            try:
                os.unlink(self.lock_file)
            except:
                pass
            self.lock_fd = None
    
    def _show_warning_dialog(self):
        """显示重复运行警告对话框"""
        app = QApplication.instance() or QApplication(sys.argv)
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("程序已运行")
        msg.setText("检测到程序已在运行中！")
        msg.setInformativeText("请勿重复启动本程序。")
        msg.setStandardButtons(QMessageBox.Ok)
        
        # 添加程序图标
        if hasattr(sys, '_MEIPASS'):  # PyInstaller打包环境
            icon_path = os.path.join(sys._MEIPASS, 'app.ico')
        else:
            icon_path = os.path.join(os.path.dirname(__file__), 'app.ico')
        
        if os.path.exists(icon_path):
            msg.setWindowIcon(QIcon(icon_path))
        
        # 居中显示对话框
        screen = QApplication.primaryScreen()
        msg.move(
            screen.geometry().center() - msg.rect().center()
        )
        msg.exec_()
        sys.exit(1)