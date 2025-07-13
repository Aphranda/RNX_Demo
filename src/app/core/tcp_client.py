
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QStatusBar, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QLineEdit, QTextEdit, QGroupBox, QGridLayout, 
    QSizePolicy, QMessageBox, QCheckBox, QToolBar, QAction, QFileDialog
)
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QFontMetrics, QTextCursor, QTextCharFormat, QIcon
from PyQt5.QtCore import Qt, QPointF, QThread, pyqtSignal, QMutex, QSize
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtCore import QRegExp
import sys, os, psutil
import socket, select
import datetime
import time
import atexit
import hashlib
import shutil
import json, struct
import math
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone

class TcpClient:
    """带超时重发机制的TCP客户端"""
    def __init__(self):
        self.sock = None
        self.connected = False
        self.last_error = None  # 记录最后一次错误

    def connect(self, ip, port, timeout=3):
        self.close()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        try:
            self.sock.connect((ip, int(port)))
            self.connected = True
            self.last_error = None
            return True, "连接成功"
        except Exception as e:
            self.last_error = str(e)
            self.connected = False
            self.sock = None
            return False, f"连接失败: {e}"

    def send(self, msg, max_retries=3, base_timeout=1.0):
        """
        带超时重发机制的发送方法
        参数:
            msg: 要发送的消息字符串
            max_retries: 最大重试次数 (默认3次)
            base_timeout: 基础超时时间(秒)，会随重试次数增加 (默认1秒)
        返回:
            (是否成功, 状态信息)
        """
        if not self.connected or not self.sock:
            return False, "未连接"

        retry_count = 0
        last_exception = None
        
        while retry_count < max_retries:
            try:
                # 动态计算当前超时时间 (指数退避算法)
                current_timeout = min(base_timeout * (2 ** retry_count), 5.0)  # 最大不超过5秒
                self.sock.settimeout(current_timeout)
                
                # 发送数据
                self.sock.sendall(msg.encode('utf-8'))
                self.last_error = None
                return True, "发送成功"
                
            except (socket.timeout, ConnectionError) as e:
                last_exception = e
                retry_count += 1
                time.sleep(0.2 * retry_count)  # 重试等待时间递增
                
                # 尝试重建连接
                if isinstance(e, ConnectionError):
                    try:
                        ip, port = self.sock.getpeername()
                        self.connect(ip, port, current_timeout)
                    except:
                        pass
                
            except Exception as e:
                last_exception = e
                break  # 非网络错误立即退出
        
        # 所有重试失败后的处理
        self.last_error = str(last_exception) if last_exception else "未知错误"
        error_msg = f"发送失败(重试{retry_count}次)"
        if last_exception:
            error_msg += f": {str(last_exception)}"
        return False, error_msg

    def receive(self, bufsize=4096, max_retries=3, base_timeout=1.0):
        """
        带超时重发机制的接收方法
        参数:
            bufsize: 每次接收的缓冲区大小 (默认4096)
            max_retries: 最大重试次数 (默认3次)
            base_timeout: 基础超时时间(秒)，会随重试次数增加 (默认1秒)
        返回:
            (是否成功, 接收到的数据或错误信息)
        """
        if not self.connected or not self.sock:
            return False, "未连接"

        retry_count = 0
        last_exception = None
        
        while retry_count < max_retries:
            try:
                # 动态计算当前超时时间
                current_timeout = min(base_timeout * (2 ** retry_count), 5.0)
                self.sock.settimeout(current_timeout)
                
                chunks = []
                start_time = time.time()
                remaining_time = current_timeout
                
                while True:
                    try:
                        # 使用select检查可读性
                        ready = select.select([self.sock], [], [], min(0.1, remaining_time))
                        if not ready[0]:  # 超时
                            raise socket.timeout(f"接收超时 ({remaining_time:.1f}s)")
                        
                        data = self.sock.recv(bufsize)
                        if not data:  # 连接关闭
                            break
                            
                        chunks.append(data)
                        
                        # 检查是否收到完整消息（以换行符判断）
                        if b'\r\n' in data or b'\r' in data:
                            break
                            
                        # 更新剩余时间
                        remaining_time = current_timeout - (time.time() - start_time)
                        if remaining_time <= 0:
                            raise socket.timeout("总接收超时")
                            
                    except socket.timeout:
                        if chunks:  # 已有部分数据则返回
                            break
                        raise
                
                if not chunks:
                    raise ValueError("收到空响应")
                
                result = b''.join(chunks).decode('utf-8', errors='ignore').strip()
                self.last_error = None
                return True, result
                
            except (socket.timeout, ConnectionError) as e:
                last_exception = e
                retry_count += 1
                time.sleep(0.2 * retry_count)
                
                # 尝试重建连接
                if isinstance(e, ConnectionError):
                    try:
                        ip, port = self.sock.getpeername()
                        self.connect(ip, port, current_timeout)
                    except:
                        pass
                
            except Exception as e:
                last_exception = e
                break  # 非网络错误立即退出
        
        # 所有重试失败后的处理
        self.last_error = str(last_exception) if last_exception else "未知错误"
        error_msg = f"接收失败(重试{retry_count}次)"
        if last_exception:
            error_msg += f": {str(last_exception)}"
        return False, error_msg

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None
        self.connected = False
        self.last_error = None
