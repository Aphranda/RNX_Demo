
from PyQt5.QtCore import Qt, QMutex, QUrl
from PyQt5.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox
from PyQt5.QtGui import QDesktopServices
import sys, os

# # 添加项目根目录到系统路径
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# sys.path.insert(0, BASE_DIR)

from resources.ui.main_window_ui import MainWindowUI

from app.threads.StatusQueryThread import StatusQueryThread
from app.core.scpi_commands import SCPICommands

class MainWindow(MainWindowUI):
    def __init__(self, Communicator, SignalUnitConverter, CalibrationFileManager):
        super().__init__()

        # 初始化外部类
        self.tcp_client = Communicator
        self.unit_converter = SignalUnitConverter
        self.calibrationFileManager = CalibrationFileManager

        self.comm_mutex = QMutex()
        self.status_thread = None
        self.calibration_thread = None  # 添加校准线程引用

        # 初始化标准SCPI库
        self.scpi = SCPICommands(self.tcp_client, self.comm_mutex)
        self.scpi.command_executed.connect(self._handle_scpi_response)

        self.status_panel.set_main_window(self)

        # 初始化状态缓存
        self._init_status_cache()
        
        # 初始化控制器
        self._init_controller()


    
    # region 初始化方法
    def _init_status_cache(self):
        """初始化状态缓存"""
        self.status_cache = {
            "motion": {axis: {"reach": "-", "home": "-", "speed": "-"} 
                      for axis in ["X", "KU", "K", "KA", "Z"]},
            "src": {"freq": "-", "power": "-", "rf": "-"}
        }
        self.compensation_enabled = False
        self.calibration_data = None
        self.cal_manager = None
        self.current_feed_mode = None
        self._is_freq_link_connected = False
        self.initing = False  # 初始化状态标志
    
    def _init_controller(self):
        """初始化控制器逻辑"""
        # 连接信号与槽
        self.eth_connect_btn.clicked.connect(self.connect_eth)
        self.eth_disconnect_btn.clicked.connect(self.disconnect_eth)

        # 系统初始化
        self.init_btn.clicked.connect(self.system_initialize)

        self.freq_feed_link_check.stateChanged.connect(self._on_freq_link_state_changed)
        self.link_set_btn.clicked.connect(self.send_link_cmd)
        self.link_query_btn.clicked.connect(self.query_link_cmd)
        self.freq_btn.clicked.connect(self.send_freq_cmd)
        self.freq_query_btn.clicked.connect(self.query_freq_cmd)
        self.power_btn.clicked.connect(self.send_power_cmd)
        self.power_query_btn.clicked.connect(self.query_power_cmd)
        self.output_btn.clicked.connect(self.send_output_cmd)
        self.output_query_btn.clicked.connect(self.query_output_cmd)
        self.home_btn.clicked.connect(self.send_home_cmd)
        self.home_query_btn.clicked.connect(self.query_home_cmd)
        self.feed_btn.clicked.connect(self.send_feed_cmd)
        self.feed_query_btn.clicked.connect(self.query_feed_cmd)
        self.speed_btn.clicked.connect(self.send_speed_cmd)
        self.speed_query_btn.clicked.connect(self.query_speed_cmd)
        self.status_panel.load_cal_btn.clicked.connect(self.load_calibration_file)
        self.status_panel._controller.motion_command.connect(self._send_motion_command)
        self.status_panel._controller.operation_completed.connect(self._handle_operation_completed)
        self.power_input.textChanged.connect(self.on_power_input_changed)
        self.raw_power_input.textChanged.connect(self.on_raw_power_input_changed)
        #工具栏校准按钮
        self.calibration_action.triggered.connect(self.show_calibration_panel)
        self.import_action.triggered.connect(self.merge_calibration_files) 
        self.help_action.triggered.connect(self.open_help_document)
        self.plot_action.triggered.connect(self.show_plot_widget)
        self.export_action.triggered.connect(self.open_code_link)
        self.settings_action.triggered.connect(self.show_software_info)

        # 状态栏初始信息
        self.show_status("系统就绪。")
        self.log("系统启动。", "INFO")

        # 清理日志
        self._init_log_cleanup()

        # endregion

    # 添加新的私有方法
    def _init_log_cleanup(self):
        """初始化日志清理功能"""
        # 延迟执行，避免影响主界面加载
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(3000, self._check_and_clean_logs)

    def _check_and_clean_logs(self):
        """检查并清理过期日志"""
        log_dir = "logs"  # 日志目录
        days_to_keep = 7  # 保留最近7天的日志
        
        # 确保日志目录存在
        if not os.path.exists(log_dir):
            return
        
        # 调用日志控制器的清理方法
        self.log_output.controller.clean_old_logs(log_dir, days_to_keep)

    # region 工具栏方法

    # 新增方法: 展示软件信息
    def show_software_info(self):
        """显示软件信息对话框"""
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("软件信息")
        dialog.setMinimumWidth(600)
        
        # 设置对话框布局
        layout = QVBoxLayout(dialog)
        
        # 软件信息
        software_info = QLabel("<h2>RNX Quantum Antenna Test System</h2>")
        software_info.setAlignment(Qt.AlignCenter)
        layout.addWidget(software_info)
        
        # 版本信息
        version_info = QLabel("<b>版本:</b> 2.1.0 (Build 2025.07.26)")
        layout.addWidget(version_info)
        
        # 开发团队信息
        team_info = QLabel("<b>开发团队:</b> GTS Wired Control Team")
        layout.addWidget(team_info)
        
        # 制作人信息
        author_info = QLabel("<b>电子工程师:</b> 董力")
        layout.addWidget(author_info)
        
        # 公司信息
        company_info = QLabel("<b>公司:</b> 深圳市通用测试系统有限公司")
        layout.addWidget(company_info)
        
        # 地址信息
        address_info = QLabel("<b>地址:</b> 深圳市南山区西丽街道创智云城A区7栋-8层")
        layout.addWidget(address_info)
        
        # 联系方式
        contact_info = QLabel("<b>技术支持:</b> li.dong@generaltest.com")
        layout.addWidget(contact_info)
        
        # 版权信息
        copyright_info = QLabel("<b>版权:</b> © 2025 GTS Technologies. 保留所有权利。")
        layout.addWidget(copyright_info)
        
        # 添加分隔线
        layout.addWidget(QLabel("<hr>"))
        
        # 系统信息
        system_info = QLabel("<b>系统信息:</b>")
        layout.addWidget(system_info)
        
        # 获取Python版本信息
        import platform
        python_version = f"Python {platform.python_version()}"
        
        # 获取PyQt版本信息
        from PyQt5.Qt import PYQT_VERSION_STR
        pyqt_version = f"PyQt {PYQT_VERSION_STR}"
        
        # 创建系统信息文本框
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setPlainText(
            f"操作系统: {platform.system()} {platform.release()}\n"
            f"处理器: {platform.processor()}\n"
            f"Python版本: {python_version}\n"
            f"PyQt版本: {pyqt_version}\n"
            f"安装路径: {os.path.abspath('.')}\n"
            f"校准文件路径: {os.path.abspath('.')}/src/calibration\n"
        )
        layout.addWidget(info_text)
        
        # 添加确定按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        # 应用主窗口样式
        if hasattr(self, 'styleSheet'):
            dialog.setStyleSheet(self.styleSheet())
        
        # 显示对话框
        dialog.exec_()
        
        self.log("查看软件信息", "INFO")

    def open_help_document(self):
        """打开帮助文档"""
        import os
        import subprocess
        from PyQt5.QtWidgets import QMessageBox
        
        # 文档路径列表
        doc_paths = [
            os.path.join("src", "docs", "RNX量子天线测试系统指令表.pdf"),
            os.path.join("src", "docs", "RNX_使用说明文档.pdf"),
        ]
        
        # 检查并打开所有找到的文档
        opened_count = 0
        for path in doc_paths:
            if os.path.exists(path):
                try:
                    # 根据不同平台使用适当的方式打开PDF
                    if os.name == 'nt':  # Windows
                        os.startfile(path)
                    elif os.name == 'posix':  # macOS or Linux
                        if os.uname().sysname == 'Darwin':  # macOS
                            subprocess.run(['open', path], check=True)
                        else:  # Linux
                            subprocess.run(['xdg-open', path], check=True)
                    opened_count += 1
                    self.log(f"已打开帮助文档: {path}", "INFO")
                except Exception as e:
                    QMessageBox.warning(self, "打开失败", f"无法打开帮助文档 {os.path.basename(path)}:\n{str(e)}")
                    self.log(f"打开帮助文档失败: {str(e)}", "ERROR")
        
        # 如果没有找到任何文档，显示警告
        if opened_count == 0:
            QMessageBox.warning(self, "文件未找到", "未找到任何帮助文档")
            self.log("未找到任何帮助文档", "ERROR")


    def show_calibration_panel(self):
        """显示或隐藏校准面板"""
        if self.calibration_panel.isVisible():
            self.calibration_panel.hide()
            self.calibration_action.setText("校准")  # 恢复按钮文本
        else:
            self.calibration_panel.show()
            self.calibration_action.setText("关闭校准")  # 更新按钮文本
            # 将校准面板置于前端
            self.calibration_panel.raise_()
            self.calibration_panel.activateWindow()

    # 新增方法
    def show_plot_widget(self):
        """显示或隐藏绘图窗口"""
        if self.plot_widget.isVisible():
            self.plot_widget.hide()
            self.plot_action.setText("数据绘图")
        else:
            self.plot_widget.show()
            self.plot_widget.raise_()
            self.plot_widget.activateWindow()
            self.plot_action.setText("关闭绘图")
    

    def open_code_link(self):
        """打开开源代码链接"""
        # 定义开源代码链接
        github_url = "https://github.com/Aphranda/RNX_Demo.git"
        
        # 创建询问对话框
        reply = QMessageBox.question(
            self,
            "打开开源代码",
            f"是否在浏览器中打开开源代码链接?\n{github_url}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 使用QDesktopServices打开链接
                QDesktopServices.openUrl(QUrl(github_url))
                self.log(f"已打开浏览器访问: {github_url}", "INFO")
            except Exception as e:
                self.log(f"打开链接失败: {str(e)}", "ERROR")
                QMessageBox.critical(
                    self,
                    "打开失败",
                    f"无法打开链接:\n{str(e)}\n请手动访问: {github_url}"
                )
        else:
            self.log("用户取消访问开源代码", "INFO")


    def merge_calibration_files(self):
        """合并多个校准文件，合并成功后询问是否导入"""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        from PyQt5.QtCore import Qt
        
        # 确保cal_manager已初始化
        if not hasattr(self, 'cal_manager') or self.cal_manager is None:
            self.cal_manager = self.calibrationFileManager(log_callback=self.log)
        
        # 打开文件选择对话框，允许多选
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter("校准文件 (*.csv *.bin);;所有文件 (*)")
        
        # 应用主窗口的样式表到文件对话框
        if hasattr(self, 'styleSheet'):
            file_dialog.setStyleSheet(self.styleSheet())
        
        if file_dialog.exec_():
            selected_files = file_dialog.selectedFiles()
            
            if len(selected_files) < 2:
                warning_box = QMessageBox(QMessageBox.Warning, "选择不足", 
                                    "请至少选择2个校准文件进行合并", 
                                    QMessageBox.Ok, self)
                # 应用样式表
                if hasattr(self, 'styleSheet'):
                    warning_box.setStyleSheet(self.styleSheet())
                warning_box.exec_()
                return
                
            try:
                # 调用CalibrationFileManager的合并方法
                merged_file = self.cal_manager.merge_calibration_files(selected_files)
                
                # 创建自定义消息框以确保样式一致
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("合并成功")
                msg_box.setText(f"成功合并{len(selected_files)}个校准文件\n保存为: {merged_file}")
                msg_box.setInformativeText("是否要导入合并后的校准数据?")
                msg_box.setIcon(QMessageBox.Information)
                msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg_box.setDefaultButton(QMessageBox.Yes)
                
                # 应用主窗口的样式表
                if hasattr(self, 'styleSheet'):
                    msg_box.setStyleSheet(self.styleSheet())
                
                # 确保对话框居中显示
                msg_box.setWindowModality(Qt.ApplicationModal)
                
                ret = msg_box.exec_()
                
                self.log(f"校准文件合并成功: {merged_file}", "SUCCESS")
                
                if ret == QMessageBox.Yes:
                    # 用户选择导入
                    self.load_calibration_file(merged_file)
                    self.log("已导入合并后的校准数据", "INFO")
                else:
                    self.log("用户选择不导入合并后的校准数据", "INFO")
                    
            except Exception as e:
                error_box = QMessageBox(QMessageBox.Critical, "合并失败", 
                                    f"合并校准文件时出错:\n{str(e)}", 
                                    QMessageBox.Ok, self)
                # 应用样式表
                if hasattr(self, 'styleSheet'):
                    error_box.setStyleSheet(self.styleSheet())
                error_box.exec_()
                self.log(f"合并校准文件失败: {str(e)}", "ERROR")


    # endregion

    
    # --- 标准SCPI ---
    def _handle_scpi_response(self, cmd: str, result: str):
        """处理SCPI命令执行结果"""
        if "失败" in result or "错误" in result:
            self.log(f"{cmd} {result}", "ERROR")
        else:
            self.log(f"{cmd} {result}", "INFO")

    # --- 日志方法 ---
    def log(self, message, level="INFO"):
        self.log_output.log(message, level)

    # --- 链路映射 ---
    def parse_link_response(self, response):
        """解析链路查询结果"""
        link_mapping = {
            "LF_PORT1,RF_COM": "FEED_X_THETA",
            "LF_PORT2,RF_COM": "FEED_X_PHI",
            "LF_PORT3,RF_COM": "FEED_KU_THETA",
            "LF_PORT4,RF_COM": "FEED_KU_PHI",
            "HF_PORT1,RF_COM": "FEED_K_THETA",
            "HF_PORT2,RF_COM": "FEED_K_PHI",
            "HF_PORT3,RF_COM": "FEED_KA_THETA",
            "HF_PORT4,RF_COM": "FEED_KA_PHI"
        }
        return link_mapping.get(response.strip(), "FEED_X_THETA")  # 默认返回X_THETA
    
    # region 网络连接方法
    def connect_eth(self):
        ip = self.eth_ip_input.text().strip() or self.eth_ip_input.placeholderText()
        port = self.eth_port_input.text().strip() or self.eth_port_input.placeholderText()
        
        self.show_status(f"正在连接：IP={ip}，Port={port}")
        self.log(f"尝试连接到 IP={ip}，Port={port}", "INFO")
        
        success, message = self.tcp_client.connect(ip, port)
        self.show_status(message)
        
        if success:
            self.log(f"已连接到 {ip}:{port}", "SUCCESS")
            self._start_status_thread(ip, port)
            self.query_link_cmd()
            self._update_connection_ui(True)
        else:
            self.log(f"连接失败: {message}", "ERROR")
            self._update_connection_ui(False)

    def disconnect_eth(self):
        if self.tcp_client.connected:
            self.tcp_client.close()
            self.show_status("已断开连接。")
            self.log("已断开连接。", "INFO")
            self.pause_status_thread()
            self._stop_status_thread()
            self._update_connection_ui(False)
        else:
            self.show_status("未连接到设备。")
            self.log("未连接到设备。", "WARNING")

    def _update_connection_ui(self, connected):
        """更新连接状态的UI"""
        if connected:
            self.eth_ip_input.setStyleSheet("border: 2px solid #4CAF50;")
            self.eth_port_input.setStyleSheet("border: 2px solid #4CAF50;")
            self.eth_connect_btn.setStyleSheet("background: #4CAF50; color: white;")
        else:
            self.eth_ip_input.setStyleSheet("")
            self.eth_port_input.setStyleSheet("")
            self.eth_connect_btn.setStyleSheet("")
    # endregion

    # region 系统初始化方法
    def system_initialize(self):
        """执行系统初始化操作"""
        if not self.tcp_client.connected:
            self.log("系统未连接，无法执行初始化", "ERROR")
            self.show_status("系统未连接")
            return
        
        # 禁用按钮防止重复点击
        self.init_btn.setEnabled(False)
        self.update_init_button_style("initializing")
        self.initing = True
                
        try:
            self.log("开始系统初始化...", "INFO")
            self.show_status("系统初始化中...")

            
            # 1. 复位设备并等待完成
            if not self.scpi.reset_and_wait():
                raise RuntimeError("设备复位失败")
            
            # 2. 清除状态寄存器
            self.scpi.clear_status()
            self.send_output_cmd()

            # 3. 关闭信号源
            cmd = f"SOURce:OUTPut OFF"
            self.send_and_log(cmd)
            
            # 4. 发送机械复位命令
            val = "ALL"
            self.status_panel._controller.request_home(val)
            
        except Exception as e:
            self.log(f"初始化过程中出错: {str(e)}", "ERROR")
            self.show_status(f"初始化失败: {str(e)}")
            self.update_init_button_style("error")
            self.init_btn.setEnabled(True)
    

    def _handle_operation_completed(self, axis, success):
        """处理操作完成信号"""
        if axis == "ALL" or axis == "Z":  # 假设ALL复位会映射到Z轴
            if success:
                self.log("系统复位完成", "SUCCESS")
                self.show_status("系统复位完成")
                self.update_init_button_style("initialized")
                self.initing = False
            else:
                self.log("系统复位失败", "ERROR")
                self.show_status("系统复位失败")
                self.update_init_button_style("error")
                self.initing = False
            
            # 恢复按钮可用状态
            self.init_btn.setEnabled(True)


    def update_init_button_style(self, status):
        """更新初始化按钮样式"""
        status_map = {
            "initializing": "初始化中...",
            "initialized": "初始化完成",
            "error": "初始化失败",
            "default": "系统初始化"
        }
        
        # 设置按钮文本
        self.init_btn.setText(status_map.get(status, status_map["default"]))
        
        # 设置按钮属性用于样式选择
        self.init_btn.setProperty("status", status)
        
        # 强制重新加载样式
        self.init_btn.style().unpolish(self.init_btn)
        self.init_btn.style().polish(self.init_btn)
    # endregion

    # region 线程操作方法
    def _start_status_thread(self, ip, port):
        """启动状态查询线程"""
        if self.status_thread:
            self.status_thread.stop()
        self.status_thread = StatusQueryThread(ip, port, self.comm_mutex)
        self.status_thread.status_signal.connect(self.update_status_panel)
        self.status_thread.start()

    def _stop_status_thread(self):
        """停止状态查询线程"""
        if self.status_thread:
            self.status_thread.stop()
            self.status_thread = None

    def pause_status_thread(self):
        """暂停状态查询线程"""
        if self.status_thread and self.status_thread.isRunning():
            self.status_thread.pause()
 
    def resume_status_thread(self):
        """恢复状态查询线程"""
        if self.status_thread and self.status_thread.isRunning():
            self.status_thread.resume()

    def update_status_panel(self, status):
        """Main method to update the status panel"""
        self._update_status_cache(status)

        # 获取信号源状态并更新链路图
        src_status = status.get("src", {})
        if "rf" in src_status.keys():
            rf_state = src_status.get("rf", "OFF").upper()  # 默认OFF状态
            self.link_diagram.set_source_state(rf_state == "ON")  # 明确传递布尔值
        
        # 判断初始化状态
        motion_status = status.get("motion", {})
        if "Z" in motion_status.keys():
            z_home_status = motion_status["Z"].get("home", "-")
            if z_home_status != "ALL OK":
                if not self.initing:
                    self.update_init_button_style("default")
                    self.log("模组未初始化，运动操作已经关闭，请先进行系统初始化", "WARNING")
        # 委托给StatusPanel处理更新逻辑
        self.status_panel._controller.update_motion_status(status.get("motion", {}))
        self.status_panel._controller.update_src_status(status.get("src", {}))
        self.status_panel._controller.update_operation_status(status.get("motion", {}))

    def _update_status_cache(self, status):
        """Update the internal status cache"""
        # Update motion status
        axes = ["X", "KU", "K", "KA", "Z"]
        for axis in axes:
            if axis in status.get("motion", {}):
                for key in ["reach", "home", "speed"]:
                    val = status["motion"][axis].get(key)
                    if val is not None:
                        self.status_cache["motion"][axis][key] = val
        
        # Update source status
        for key in ["freq", "power", "rf"]:
            val = status.get("src", {}).get(key)
            if val is not None:
                self.status_cache["src"][key] = val
    # endregion



    # region 频率联动方法
    def _on_freq_link_state_changed(self, state):
        """处理频率联动复选框状态变化"""
        if state == Qt.Checked and not self._is_freq_link_connected:
            self._is_freq_link_connected = True
            self.log("频率与馈源联动已启用", "WARNING")
            self.motion_group.setTitle("运动控制 (频率联动模式下禁用)")
            self.motion_group.setEnabled(False)
        elif state != Qt.Checked and self._is_freq_link_connected:
            self._is_freq_link_connected = False
            self.log("频率与馈源联动已禁用", "WARNING")
            self.motion_group.setTitle("运动控制")
            self.motion_group.setEnabled(True)
    
    def _update_feed_for_freq(self, mode):
        """根据频率更新馈源设置"""
        if not self.tcp_client.connected:
            return
        
        freq_ranges = {
            "FEED_X_THETA": (8.0, 12.0),
            "FEED_X_PHI": (8.0, 12.0),
            "FEED_KU_THETA": (12.0, 18.0),
            "FEED_KU_PHI": (12.0, 18.0),
            "FEED_K_THETA": (18.0, 26.5),
            "FEED_K_PHI": (18.0, 26.5),
            "FEED_KA_THETA": (26.5, 40.0),
            "FEED_KA_PHI": (26.5, 40.0)
        }
        
        if mode in freq_ranges:
            target_axis = mode.split("_")[1]
            self.status_panel._controller.request_feed(target_axis)

    def _control_feed_for_frequency(self, freq_str):
        """根据频率控制对应的馈源轴"""
        try:
            # 解析频率值
            freq_ghz = float(freq_str.replace("GHz", "").strip())
            
            # 确定目标馈源轴
            target_axis = self._determine_feed_axis(freq_ghz)
            if not target_axis:
                return
                
            # 获取当前链路模式
            current_link = self.parse_link_response(self.status_cache.get("src", {}).get("link", ""))
            
            # 构建新的链路模式
            if target_axis == "X":
                new_link = "FEED_X_THETA" if "THETA" in current_link else "FEED_X_PHI"
            elif target_axis == "KU":
                new_link = "FEED_KU_THETA" if "THETA" in current_link else "FEED_KU_PHI"
            elif target_axis == "K":
                new_link = "FEED_K_THETA" if "THETA" in current_link else "FEED_K_PHI"
            elif target_axis == "KA":
                new_link = "FEED_KA_THETA" if "THETA" in current_link else "FEED_KA_PHI"
            else:
                return
                
            # 更新当前馈源模式
            self.current_feed_mode = new_link
            
            # 使用状态机控制器请求达位
            self.status_panel._controller.request_feed(target_axis)
            
            # 发送链路切换命令
            self._send_link_command(new_link)
            
        except ValueError:
            self.log("无效的频率格式", "ERROR")

    def _determine_feed_axis(self, freq_ghz):
        """根据频率确定目标馈源轴"""
        freq_ranges = {
            "X": (8.0, 12.0),
            "KU": (12.0, 18.0),
            "K": (18.0, 26.5),
            "KA": (26.5, 40.0)
        }
        
        for axis, (min_freq, max_freq) in freq_ranges.items():
            if min_freq <= freq_ghz <= max_freq:
                return axis
        return None

    def _send_link_command(self, link_mode):
        """发送链路配置命令"""
        cmd = f"CONFigure:LINK {link_mode}"
        self.link_diagram.set_link(link_mode)  # 动态刷新链路图
        
        # 发送命令
        self.send_and_log(cmd)
    # endregion

    def is_valid_frequency(self, freq_str):
        """验证频率值是否有效"""
        if not freq_str or freq_str == "-":
            return False
        try:
            float(freq_str.replace("GHz", "").strip())
            return True
        except ValueError:
            return False

    def is_valid_power(self, text):
        """验证功率输入是否有效"""
        if not text.strip():
            return False
        try:
            float(text.replace("dBm", "").strip())
            return True
        except ValueError:
            return False

    def should_process_input(self, text):
        """判断是否应该处理输入"""
        text = text.strip()
        
        # 条件1: 长度不超过2时不处理
        if len(text) < 2:
            return False
        
        # 条件2: 如果最后输入的是符号(+/-)不处理
        if text[-1] in ('+', '-'):
            return False
        
        # 条件3: 检查是否为有效数字格式
        try:
            # 临时移除单位检查纯数字有效性
            num_part = text.replace("dBm", "").strip()
            if not num_part:  # 空字符串
                return False
            return True
        except ValueError:
            return False




    # region 功率输入处理
    def on_power_input_changed(self, text):
        """补偿后功率输入框变化时的处理"""
        # 防止递归触发
        if self.raw_power_input.signalsBlocked():
            return
        
        # 获取当前选择的功率单位
        target_unit = self.power_unit_combo.currentText()
        
        real_text = text + " " + target_unit

        try:
            # 验证并解析输入值
            valid, power_value, power_unit = self.unit_converter.validate_power(real_text)
            if not valid:
                return
                
            # 获取当前频率
            freq_str = self.status_cache["src"].get("freq", "0")
            if not self.is_valid_frequency(freq_str):
                self.show_status("当前频率无效，无法计算补偿", timeout=3000)
                return
                
            # 转换为GHz单位
            freq_ghz = float(freq_str.replace("GHz", "").strip()) if "GHz" in freq_str else float(freq_str)/1e9
            
            # 将输入值转换为dBm
            if power_unit in ['V/m', 'mV/m', 'µV/m', 'dBμV/m']:
                # 电场强度单位转换为dBm
                if power_unit == 'V/m':
                    power_dbm = self.unit_converter.v_m_to_dbm(power_value, freq_ghz*1e9)
                elif power_unit == 'mV/m':
                    power_dbm = self.unit_converter.v_m_to_dbm(power_value/1000, freq_ghz*1e9)
                elif power_unit == 'µV/m':
                    power_dbm = self.unit_converter.v_m_to_dbm(power_value/1e6, freq_ghz*1e9)
                elif power_unit == 'dBμV/m':
                    power_dbm = self.unit_converter.dbuV_m_to_dbm(power_value, freq_ghz*1e9)
            else:
                # 其他功率单位转换为dBm
                power_dbm, _ = self.unit_converter.convert_power(power_value, power_unit, 'dBm')
            
            # 计算补偿值
            compensation = self.get_compensation_value(freq_ghz) if self.compensation_enabled else 0.0
            raw_power = power_dbm - compensation

            # 根据目标单位转换补偿后的功率值
            if target_unit in ['V/m', 'mV/m', 'µV/m', 'dBμV/m']:
                # 转换为电场强度单位
                if target_unit == 'V/m':
                    power_value = self.unit_converter.dbm_to_v_m(raw_power, freq_ghz*1e9)
                elif target_unit == 'mV/m':
                    power_value = self.unit_converter.dbm_to_v_m(raw_power, freq_ghz*1e9) * 1000
                elif target_unit == 'µV/m':
                    power_value = self.unit_converter.dbm_to_v_m(raw_power, freq_ghz*1e9) * 1e6
                elif target_unit == 'dBμV/m':
                    power_value = self.unit_converter.dbm_to_dbuV_m(raw_power, freq_ghz*1e9)
            else:
                # 转换为其他功率单位
                power_value, _ = self.unit_converter.convert_power(raw_power, 'dBm', target_unit)
            
            # 更新原始功率输入框（不触发信号）
            self.raw_power_input.blockSignals(True)
            self.raw_power_input.setText(f"{power_value:.2f} {target_unit}")
            self.raw_power_input.blockSignals(False)
            
        except ValueError as e:
            self.log(f"功率转换错误: {str(e)}", "WARNING")

    def on_raw_power_input_changed(self, text):
        """原始功率输入框变化时的处理"""
        # 防止递归触发
        if self.power_input.signalsBlocked():
            return
            
        # 获取当前选择的功率单位
        target_unit = self.power_unit_combo.currentText()

        real_text = text + " " + target_unit
        
        try:
            # 验证并解析输入值
            valid, raw_power, power_unit = self.unit_converter.validate_power(real_text)
            if not valid:
                return
                
            # 获取当前频率
            freq_str = self.status_cache["src"].get("freq", "0")
            if not self.is_valid_frequency(freq_str):
                self.show_status("当前频率无效，无法计算补偿", timeout=3000)
                return
                
            # 转换为GHz单位
            freq_ghz = float(freq_str.replace("GHz", "").strip()) if "GHz" in freq_str else float(freq_str)/1e9

            # 将输入值转换为dBm
            if power_unit in ['V/m', 'mV/m', 'µV/m', 'dBμV/m']:
                # 电场强度单位转换为dBm
                if power_unit == 'V/m':
                    raw_power_dbm = self.unit_converter.v_m_to_dbm(raw_power, freq_ghz*1e9)
                elif power_unit == 'mV/m':
                    raw_power_dbm = self.unit_converter.v_m_to_dbm(raw_power/1000, freq_ghz*1e9)
                elif power_unit == 'µV/m':
                    raw_power_dbm = self.unit_converter.v_m_to_dbm(raw_power/1e6, freq_ghz*1e9)
                elif power_unit == 'dBμV/m':
                    raw_power_dbm = self.unit_converter.dbuV_m_to_dbm(raw_power, freq_ghz*1e9)
            else:
                # 其他功率单位转换为dBm
                raw_power_dbm, _ = self.unit_converter.convert_power(raw_power, power_unit, 'dBm')
            
            # 计算补偿值
            compensation = self.get_compensation_value(freq_ghz) if self.compensation_enabled else 0.0
            power_dbm = raw_power_dbm + compensation
            
            # 根据目标单位转换补偿后的功率值
            if target_unit in ['V/m', 'mV/m', 'µV/m', 'dBμV/m']:
                # 转换为电场强度单位
                if target_unit == 'V/m':
                    power_value = self.unit_converter.dbm_to_v_m(power_dbm, freq_ghz*1e9)
                elif target_unit == 'mV/m':
                    power_value = self.unit_converter.dbm_to_v_m(power_dbm, freq_ghz*1e9) * 1000
                elif target_unit == 'µV/m':
                    power_value = self.unit_converter.dbm_to_v_m(power_dbm, freq_ghz*1e9) * 1e6
                elif target_unit == 'dBμV/m':
                    power_value = self.unit_converter.dbm_to_dbuV_m(power_dbm, freq_ghz*1e9)
            else:
                # 转换为其他功率单位
                power_value, _ = self.unit_converter.convert_power(power_dbm, 'dBm', target_unit)
            
            # 更新补偿后功率输入框（不触发信号）
            self.power_input.blockSignals(True)
            self.power_input.setText(f"{power_value:.2f} {target_unit}")
            self.power_input.blockSignals(False)
            
        except ValueError as e:
            self.log(f"原始功率转换错误: {str(e)}", "WARNING")

    # endregion

    # region 校准及补偿方法
    
    def load_calibration_file(self, filepath: str):
        """加载校准文件"""
        from PyQt5.QtWidgets import QFileDialog
    
        # 确保cal_manager已初始化
        if self.cal_manager is None:
            self.cal_manager = self.calibrationFileManager(log_callback=self.log)
    
            # self.cal_manager.generate_default_calibration()
        # 获取最近校准文件目录
        cal_dir = "calibrations"  # 默认目录
        if hasattr(self, 'cal_manager'):
            cal_dir = self.cal_manager.base_dir
        
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择校准文件", 
            cal_dir, 
            "校准文件 (*.csv *.bin);;所有文件 (*)"
        )
    
        if file_path:
            self.status_panel.cal_file_input.setText(file_path)
            self.log(f"已选择校准文件: {file_path}", "INFO")
    
            # 使用CalibrationFileManager加载文件
            result = self.cal_manager.load_calibration_file(file_path)
    
            # 打印文件内容验证（不重新加载文件）
            self._print_cal_file_contents(file_path, loaded_data=result)
    
            if result:
                self.calibration_data = result['data']
                # 处理ref_power可能是列表的情况
                ref_power = result['meta'].get("base_param", {}).get("ref_power", -30.0)
                if isinstance(ref_power, list):
                    if len(ref_power) > 0:
                        self.log(f"检测到参考功率列表，{ref_power} dBm", "INFO")
                    else:
                        ref_power = -30.0  # 默认值
                        self.log("参考功率列表为空，使用默认值-30dBm", "WARNING")
                else:
                    # 如果不是列表，直接转换为float
                    ref_power = float(ref_power) if ref_power is not None else -30.0

                self.log(f"校准文件加载成功，参考功率(ref_power)为: {ref_power} dBm", "INFO")
                self.compensation_enabled = True

                self.calibration_data = result['data']
                self.compensation_enabled = True
                self.status_panel.update_src_status({"cal_file": "Calib Load"})

                self.status_panel.set_cal_file_style(
                    text="Calib Load",
                    state="loaded"  # 可以是 'loaded'/'missing'/'invalid'
                )

                self.log("校准文件加载成功，补偿功能已启用", "SUCCESS")
            else:
                self.compensation_enabled = False
                self.status_panel.update_src_status({"cal_file": "Calib Invalid"})
                self.status_panel.set_cal_file_style(
                    text="Calib Load",
                    state="invalid"  # 可以是 'loaded'/'missing'/'invalid'
                )
                self.log("校准文件加载失败", "ERROR")

    def _print_cal_file_contents(self, filepath: str, loaded_data=None):
        """打印校准文件内容用于验证数据正确性"""
        # 直接使用已加载的数据或self.cal_manager中的数据
        if loaded_data is not None:
            meta = loaded_data.get('meta', {})
            data_points = loaded_data.get('data', [])
        elif hasattr(self, 'cal_manager') and self.cal_manager:
            meta = self.cal_manager.current_meta
            data_points = self.cal_manager.data_points
        else:
            self.log("校准管理器未初始化", "ERROR")
            return
        
        # 显示文件格式信息
        self.log("\n=== 文件信息 ===", "INFO")
        try:
            file_size = os.path.getsize(filepath)
            self.log(f"文件大小: {file_size/1024:.2f} KB", "INFO")
            
            if filepath.lower().endswith('.bin'):
                self.log("文件格式: 二进制校准文件 (RNXC格式)", "INFO")
                self.log("数据编码: 每个数据点36字节(频率:4字节float + 8个参数:32字节)", "INFO")
            elif filepath.lower().endswith('.csv'):
                self.log("文件格式: CSV文本文件 (UTF-8编码)", "INFO")
                self.log("数据格式: 逗号分隔值,每行9个字段(频率+8个参数)", "INFO")
                
            # 显示文件完整路径
            self.log(f"文件路径: {os.path.abspath(filepath)}", "INFO")
        except Exception as e:
            self.log(f"获取文件信息失败: {str(e)}", "WARNING")
          
        self.log("\n=== 文件元数据 ===", "INFO")
        # 打印元数据
        if isinstance(meta, dict):
            self.log(f"创建时间: {meta.get('created', '未知')}", "INFO")
            self.log(f"操作员: {meta.get('operator', '未知')}", "INFO")
            if 'signal_gen' in meta:
                sg_info = meta['signal_gen']
                self.log(f"信号源: {sg_info[0]} (SN: {sg_info[1]})", "INFO")
            if 'spec_analyzer' in meta:
                sa_info = meta['spec_analyzer']
                self.log(f"频谱分析仪: {sa_info[0]} (SN: {sa_info[1]})", "INFO")
            if 'antenna' in meta:
                ant_info = meta['antenna']
                self.log(f"天线: {ant_info[0]} (SN: {ant_info[1]})", "INFO")
            if 'environment' in meta:
                env_info = meta['environment']
                self.log(f"环境: {env_info[0]}°C, {env_info[1]}%RH", "INFO")
            
            if 'freq_params' in meta:
                freq_params = meta['freq_params']
                self.log("\n=== 频率参数 ===", "INFO")
                self.log(f"起始频率: {freq_params.get('start_ghz', '未知')} GHz", "INFO")
                self.log(f"终止频率: {freq_params.get('stop_ghz', '未知')} GHz", "INFO")
                self.log(f"步进: {freq_params.get('step_ghz', '未知')} GHz", "INFO")
                self.log(f"点数: {meta.get('points', '未知')}", "INFO")
        
        
        self.log("\n=== 总结 ===", "INFO")
        self.log(f"总数据点数: {len(data_points)}", "INFO")
        if isinstance(meta, dict) and 'points' in meta:
            self.log(f"预期点数: {meta['points']}", "INFO")
            if len(data_points) == meta['points']:
                self.log("数据点数匹配", "SUCCESS")
            else:
                self.log("数据点数不匹配", "WARNING")

    def get_compensation_value(self, freq_ghz: float) -> float:
        """
        根据频率获取补偿值，已考虑参考功率(ref_power)
        :param freq_ghz: 频率(GHz)
        :return: 补偿值(dB)
        """
        if not self.compensation_enabled or not self.calibration_data:
            return 0.0
        
        # 检查频率是否在校准范围内
        freqs = [point['freq'] for point in self.calibration_data]
        if freq_ghz < min(freqs) or freq_ghz > max(freqs):
            self.log(f"警告：频率{freq_ghz}GHz超出校准范围({min(freqs)}-{max(freqs)}GHz)", "WARNING")
            return 0.0
        
        # 找到最接近的频率点
        closest_point = min(self.calibration_data, key=lambda x: abs(x['freq'] - freq_ghz))
        
        # 获取当前链路模式
        current_link = self.parse_link_response(self.status_cache.get("src", {}).get("link", ""))
        
        # 获取参考功率(从校准文件元数据中获取)
        ref_power = self.cal_manager.current_meta.get("base_param", {}).get("ref_power", -30.0)  # 默认-30dBm
        if isinstance(ref_power, list):
            if len(ref_power) == 1:
                ref_power = ref_power[0]
            else:
                ref_power = closest_point.get('reference_power', 0.0)
        
        # 根据链路模式选择使用Theta_corrected还是Phi_corrected，并减去参考功率
        if "THETA" in current_link:
            raw_comp = closest_point.get('theta_corrected', 0.0)
            compensation = raw_comp - ref_power
            self.log(f"补偿计算: THETA_raw={raw_comp}dB, ref_power={ref_power}dB, 最终补偿={compensation}dB", "DEBUG")
            return compensation
        elif "PHI" in current_link:
            raw_comp = closest_point.get('phi_corrected', 0.0)
            compensation = raw_comp - ref_power
            self.log(f"补偿计算: PHI_raw={raw_comp}dB, ref_power={ref_power}dB, 最终补偿={compensation}dB", "DEBUG")
            return compensation
        else:
            self.log("未知链路模式，使用默认补偿值0dB", "WARNING")
            return 0.0
    # endregion

    # region 链路控制方法
    # --- 指令组合与发送 ---
    # --- 链路切换，并且移动馈源位置。
    def send_link_cmd(self):
        """发送链路配置命令"""
        mode = self.link_mode_combo.currentText()
        cmd = f"CONFigure:LINK {mode}"
        self.link_diagram.set_link(mode)  # 动态刷新链路图
        
        # 发送命令
        self.send_and_log(cmd)
        
        # 如果频率联动已启用，则执行联动逻辑
        if self._is_freq_link_connected:
            self._update_feed_for_freq(mode)

    # --- 链路查询 ---
    def query_link_cmd(self):
        cmd = "READ:LINK:STATe?"
        # 暂停状态线程
        self.pause_status_thread()
        
        self.comm_mutex.lock()
        try:
            self.log(cmd, "SEND")
            success, msg = self.tcp_client.send(cmd + '\n')
            if not success:
                self.log(f"发送失败: {msg}", "ERROR")
                self.show_status(msg)
                return
            
            success, resp = self.tcp_client.receive()
            if success:
                self.log(resp, "RECV")
                current_link = self.parse_link_response(resp)
                self.link_diagram.set_link(current_link)
                self.show_status(f"当前链路: {current_link}")
            else:
                self.log(f"接收失败: {resp}", "ERROR")
                self.show_status(resp)
        finally:
            self.comm_mutex.unlock()
            # 恢复状态线程
            self.resume_status_thread()

    # endregion

    # region 信号源控制方法
    def send_freq_cmd(self):
        val = self.freq_input.text().strip() + " " + self.freq_unit_combo.currentText()
        if not val:
            self.show_status("请输入频率参数")
            return
        
        # 验证并解析频率
        valid, freq_value, freq_unit = self.unit_converter.validate_frequency(val)
        if not valid:
            self.show_status("无效的频率格式")
            self.log("无效的频率输入", "ERROR")
            return
        
        # 转换为GHz单位（假设设备使用GHz）
        freq_ghz, _ = self.unit_converter.convert_frequency(freq_value, freq_unit, "GHz")
        
        # 发送频率设置命令
        cmd = f"SOURce:FREQuency {freq_ghz}GHz"
        self.send_and_log(cmd)
        
        # 频率联动逻辑
        if self._is_freq_link_connected:
            self._control_feed_for_frequency(f"{freq_ghz}GHz")

    def query_freq_cmd(self):
        cmd = "READ:SOURce:FREQuency?"
        self.send_and_log(cmd)
    
    def send_power_cmd(self):
        val = self.power_input.text().strip() + " " + self.power_unit_combo.currentText()
        
        if not val:
            self.show_status("请输入功率参数")
            return
        
        try:
            # 解析输入的功率值和单位
            valid, power_value, power_unit = self.unit_converter.validate_power(val)
            if not valid:
                self.show_status("无效的功率参数")
                self.log("无效的功率输入", "ERROR")
                return
            # 获取当前频率，并且解析单位
            freq_str = self.status_cache["src"].get("freq", "0")
            freq_ghz = float(freq_str.replace("GHz", "").strip()) if "GHz" in freq_str else float(freq_str)/1e9

            
            # 如果是电场强度单位(V/m)，需要转换为dBm
            if power_unit in ['V/m', 'dBμV/m']:
               
                # 获取当前频率用于转换
                if not self.is_valid_frequency(freq_str):
                    self.show_status("当前频率无效，无法转换电场强度", timeout=3000)
                    return
                # 将电场强度转换为dBm
                if power_unit == 'V/m':
                    power_dbm = self.unit_converter.v_m_to_dbm(power_value, freq_ghz*1e9)
                elif power_unit == 'mV/m':
                    power_dbm = self.unit_converter.v_m_to_dbm(power_value/1000, freq_ghz*1e9)
                elif power_unit == 'µV/m':
                    power_dbm = self.unit_converter.v_m_to_dbm(power_value/1e6, freq_ghz*1e9)
                elif power_unit == 'dBμV/m':
                    power_dbm = self.unit_converter.dbuV_m_to_dbm(power_value, freq_ghz*1e9)
            else:
                # 其他功率单位直接转换为dBm
                power_dbm, _ = self.unit_converter.convert_power(power_value, power_unit, 'dBm')
            
            # 计算补偿值(已包含ref_power处理)
            compensation = self.get_compensation_value(freq_ghz) if self.compensation_enabled else 0.0
            
            # 计算实际需要设置的功率
            actual_power = power_dbm - compensation
            
            # 存储原始功率值
            self.current_power = power_dbm
            
            cmd = f"SOURce:POWer {actual_power:.2f}"
            self.send_and_log(cmd)
            
            # 增强日志信息
            log_msg = (f"功率转换详情:\n"
                    f"- 输入功率 = {power_value:.2f} {power_unit}\n"
                    f"- 转换为dBm = {power_dbm:.2f} dBm\n"
                    f"- 补偿值 = {compensation:.2f} dB (已考虑ref_power)\n"
                    f"- 实际设置 = {actual_power:.2f} dBm\n"
                    f"- 当前链路 = {self.parse_link_response(self.status_cache.get('src', {}).get('link', ''))}\n"
                    f"- 参考功率(ref_power) = {self.cal_manager.current_meta.get('ref_power', -30.0)} dBm")
            self.log(log_msg, "INFO")
        except ValueError as e:
            self.show_status(f"功率转换错误: {str(e)}")
            self.log(f"功率转换错误: {str(e)}", "ERROR")

    def query_power_cmd(self):
        cmd = "READ:SOURce:POWer?"
        target_unit = self.power_unit_combo.currentText()
        
        # 暂停状态线程
        self.pause_status_thread()
        
        self.comm_mutex.lock()
        try:
            self.log(cmd, "SEND")
            success, msg = self.tcp_client.send(cmd + '\n')
            if not success:
                self.log(f"发送失败: {msg}", "ERROR")
                self.show_status(msg)
                return
            
            success, resp = self.tcp_client.receive()
            if success:
                try:
                    # 解析查询到的功率值(假设设备返回dBm)
                    measured_power = float(resp.replace("dBm", "").strip())
                    
                    # 获取当前频率
                    freq_str = self.status_cache["src"].get("freq", "0")
                    freq_ghz = float(freq_str.replace("GHz", "").strip()) if "GHz" in freq_str else float(freq_str)/1e9
                    
                    # 计算补偿值
                    compensation = self.get_compensation_value(freq_ghz) if self.compensation_enabled else 0.0
                    actual_power = measured_power + compensation

                    # 默认
                    converted = 0
                    
                    # 转换为目标单位
                    if target_unit in ['V/m', 'mV/m', 'µV/m', 'dBμV/m']:
                        # 电场强度转换
                        if target_unit == 'V/m':
                            converted = self.unit_converter.dbm_to_v_m(actual_power, freq_ghz*1e9)
                        elif target_unit == 'mV/m':
                            converted = self.unit_converter.dbm_to_v_m(actual_power, freq_ghz*1e9) * 1000
                        elif target_unit == 'µV/m':
                            converted = self.unit_converter.dbm_to_v_m(actual_power, freq_ghz*1e9) * 1e6
                        elif target_unit == 'dBμV/m':
                            converted = self.unit_converter.dbm_to_dbuV_m(actual_power, freq_ghz*1e9)
                    else:
                        # 普通功率单位转换
                        converted, _ = self.unit_converter.convert_power(actual_power, 'dBm', target_unit)
                    
                    self.log(f"{resp} (补偿后: {converted:.2f}{target_unit})", "RECV")
                    self.show_status(f"查询功率: {converted:.2f}{target_unit} (补偿值: {compensation:.2f}dB)")
                except ValueError:
                    self.log(resp, "RECV")
                    self.show_status("查询功率")
            else:
                self.log(f"接收失败: {resp}", "ERROR")
                self.show_status(resp)
        finally:
            self.comm_mutex.unlock()
            # 恢复状态线程
            self.resume_status_thread()

    def send_output_cmd(self):
        val = self.output_combo.currentText()
        cmd = f"SOURce:OUTPut {val}"
        self.send_and_log(cmd)

    def query_output_cmd(self):
        cmd = "READ:SOURce:OUTPut?"
        self.send_and_log(cmd)

    # endregion

    # region 运动控制方法
    def send_home_cmd(self):
        val = self.home_combo.currentText()
        # 使用状态机控制器请求复位
        self.status_panel._controller.request_home(val)

    def query_home_cmd(self):
        val = self.home_combo.currentText()
        cmd = f"READ:MOTion:HOME? {val}"
        self.send_and_log(cmd)

    def send_feed_cmd(self):
        val = self.feed_combo.currentText()
        # 使用状态机控制器请求达位
        self.status_panel._controller.request_feed(val)

    def query_feed_cmd(self):
        val = self.feed_combo.currentText()
        cmd = f"READ:MOTion:FEED? {val}"
        self.send_and_log(cmd)

    def send_speed_cmd(self):
        mod = self.speed_mod_combo.currentText()
        speed = self.speed_combo.currentText()
        cmd = f"MOTion:SPEED {mod},{speed}"
        self.send_and_log(cmd)

    def query_speed_cmd(self):
        mod = self.speed_mod_combo.currentText()
        cmd = f"READ:MOTion:SPEED? {mod}"
        self.send_and_log(cmd)

    def _send_motion_command(self, cmd):
        """发送运动命令"""
        # 优先暂停状态线程，防止抢占
        self.pause_status_thread()
            
        self.comm_mutex.lock()
        try:
            self.log(cmd, "SEND")
            success, msg = self.tcp_client.send(cmd + '\n')
            if not success:
                self.log(f"发送失败: {msg}", "ERROR")
                self.show_status(msg)
                return
                
            # 对于运动命令，我们不期待响应，直接标记为成功
            # self.status_panel._controller._on_operation_complete(True)
            
        finally:
            self.comm_mutex.unlock()
            # 手动指令完成后重启状态线程
            self.resume_status_thread()

    # endregion

    # region 通用方法
    def send_and_log(self, cmd):
        # 优先暂停状态线程，防止抢占
        self.pause_status_thread()
        self.comm_mutex.lock()
        try:
            self.log(cmd, "SEND")
            # 判断是否为无返回值指令
            if cmd.strip().upper().startswith("CONFIGURE:LINK") or cmd.strip().upper().startswith("CONFIG:LINK"):
                success, msg = self.tcp_client.send(cmd + '\n')
                if success:
                    self.show_status("链路设置指令已发送。")
                else:
                    self.log(f"发送失败: {msg}", "ERROR")
                    self.show_status(msg)
                return
            # 其它指令正常收发
            success, msg = self.tcp_client.send(cmd + '\n')
            if not success:
                self.log(f"发送失败: {msg}", "ERROR")
                self.show_status(msg)
                return
            success, resp = self.tcp_client.receive()
            
            if success:
                self.log(resp, "RECV")
                self.show_status("指令已发送。")
            else:
                self.log(f"接收失败: {resp}", "ERROR")
                self.show_status(resp)
        finally:
            self.comm_mutex.unlock()
            # 手动指令完成后重启状态线程
            self.resume_status_thread()

    def show_status(self, message, timeout=0):
        self.status_bar.showMessage(message, timeout)

    def closeEvent(self, event):
        """重写关闭事件，确保安全关闭线程"""
        # 停止状态查询线程
        if self.status_thread and self.status_thread.isRunning():
            self.pause_status_thread()
            self.status_thread.stop()
            self.status_thread.wait(2000)  # 等待2秒
        
        # 停止校准线程
        if hasattr(self, 'calibration_thread') and self.calibration_thread and self.calibration_thread.isRunning():
            self.calibration_thread.stop()
            self.calibration_thread.wait(2000)
        
        # 关闭TCP连接
        if self.tcp_client.connected:
            self.tcp_client.close()
        
        # 确认关闭
        reply = QMessageBox.question(
            self, '确认退出',
            "确定要退出程序吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    # endregion