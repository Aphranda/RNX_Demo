import json
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, 
    QGroupBox, QLabel, QLineEdit, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal
from typing import Dict, Any, Optional

class InstrumentConfigDialog(QDialog):
    config_updated = pyqtSignal(dict)  # 当配置更新时发出信号

    def __init__(self, config_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("仪器配置管理")
        self.setMinimumSize(800, 600)
        
        self.config_path = Path(config_path)
        self.original_config = self._load_config()
        self.current_config = self._deep_copy_config(self.original_config)
        
        self._init_ui()
        self._setup_connections()
        
    def _init_ui(self):
        main_layout = QVBoxLayout()
        
        # 顶部按钮区域
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存配置")
        self.reset_btn = QPushButton("重置更改")
        self.export_btn = QPushButton("导出配置")
        self.import_btn = QPushButton("导入配置")
        self.add_instrument_btn = QPushButton("添加仪器")
        self.remove_instrument_btn = QPushButton("移除仪器")
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.reset_btn)
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.add_instrument_btn)
        btn_layout.addWidget(self.remove_instrument_btn)
        
        # 仪器选择下拉框
        self.instrument_combo = QComboBox()
        self.instrument_combo.addItems(self.current_config.keys())
        
        # 主选项卡
        self.tab_widget = QTabWidget()
        
        # 基本信息选项卡
        self.basic_info_tab = self._create_basic_info_tab()
        # 命令配置选项卡
        self.commands_tab = self._create_commands_tab()
        # 高级配置选项卡
        self.advanced_tab = self._create_advanced_tab()
        
        self.tab_widget.addTab(self.basic_info_tab, "基本信息")
        self.tab_widget.addTab(self.commands_tab, "命令配置")
        self.tab_widget.addTab(self.advanced_tab, "高级配置")
        
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(QLabel("选择仪器:"))
        main_layout.addWidget(self.instrument_combo)
        main_layout.addWidget(self.tab_widget)
        
        self.setLayout(main_layout)
        
    def _setup_connections(self):
        self.save_btn.clicked.connect(self._save_config)
        self.reset_btn.clicked.connect(self._reset_config)
        self.export_btn.clicked.connect(self._export_config)
        self.import_btn.clicked.connect(self._import_config)
        self.add_instrument_btn.clicked.connect(self._add_instrument)
        self.remove_instrument_btn.clicked.connect(self._remove_instrument)
        self.instrument_combo.currentTextChanged.connect(self._update_tabs)
        
    def _create_basic_info_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout()
        
        # 基本信息组
        basic_group = QGroupBox("基本信息")
        basic_layout = QVBoxLayout()
        
        self.model_name_edit = QLineEdit()
        self.min_freq_edit = QLineEdit()
        self.max_freq_edit = QLineEdit()
        self.min_power_edit = QLineEdit()
        self.max_power_edit = QLineEdit()
        
        form_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        
        left_layout.addWidget(QLabel("仪器型号:"))
        left_layout.addWidget(self.model_name_edit)
        left_layout.addWidget(QLabel("最小频率(Hz):"))
        left_layout.addWidget(self.min_freq_edit)
        
        right_layout.addWidget(QLabel("最大频率(Hz):"))
        right_layout.addWidget(self.max_freq_edit)
        right_layout.addWidget(QLabel("最小功率(dBm):"))
        right_layout.addWidget(self.min_power_edit)
        right_layout.addWidget(QLabel("最大功率(dBm):"))
        right_layout.addWidget(self.max_power_edit)
        
        form_layout.addLayout(left_layout)
        form_layout.addLayout(right_layout)
        basic_group.setLayout(form_layout)
        
        layout.addWidget(basic_group)
        layout.addStretch()
        tab.setLayout(layout)
        
        return tab
    
    def _create_commands_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout()
        
        # 标准命令表
        self.commands_table = QTableWidget()
        self.commands_table.setColumnCount(2)
        self.commands_table.setHorizontalHeaderLabels(["命令名称", "SCPI命令"])
        self.commands_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        
        # 调制命令表
        self.mod_commands_table = QTableWidget()
        self.mod_commands_table.setColumnCount(2)
        self.mod_commands_table.setHorizontalHeaderLabels(["命令名称", "SCPI命令"])
        self.mod_commands_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        self.add_cmd_btn = QPushButton("添加命令")
        self.remove_cmd_btn = QPushButton("移除命令")
        self.add_mod_cmd_btn = QPushButton("添加调制命令")
        self.remove_mod_cmd_btn = QPushButton("移除调制命令")
        
        btn_layout.addWidget(self.add_cmd_btn)
        btn_layout.addWidget(self.remove_cmd_btn)
        btn_layout.addWidget(self.add_mod_cmd_btn)
        btn_layout.addWidget(self.remove_mod_cmd_btn)
        
        # 连接按钮信号
        self.add_cmd_btn.clicked.connect(lambda: self._add_command(self.commands_table))
        self.remove_cmd_btn.clicked.connect(lambda: self._remove_command(self.commands_table))
        self.add_mod_cmd_btn.clicked.connect(lambda: self._add_command(self.mod_commands_table))
        self.remove_mod_cmd_btn.clicked.connect(lambda: self._remove_command(self.mod_commands_table))
        
        # 分组
        commands_group = QGroupBox("标准命令")
        commands_group.setLayout(QVBoxLayout())
        commands_group.layout().addWidget(self.commands_table)
        
        mod_commands_group = QGroupBox("调制命令")
        mod_commands_group.setLayout(QVBoxLayout())
        mod_commands_group.layout().addWidget(self.mod_commands_table)
        
        layout.addWidget(commands_group)
        layout.addWidget(mod_commands_group)
        layout.addLayout(btn_layout)
        tab.setLayout(layout)
        
        return tab
    
    def _create_advanced_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout()
        
        # 这里可以添加更多高级配置选项
        self.advanced_text = QLabel("高级配置为定制化需求, 正在开发中...")
        self.advanced_text.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.advanced_text)
        layout.addStretch()
        tab.setLayout(layout)
        
        return tab
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载配置文件失败: {str(e)}")
            return {}
    
    def _save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.current_config, f, indent=4, ensure_ascii=False)
            
            self.original_config = self._deep_copy_config(self.current_config)
            self.config_updated.emit(self.current_config)
            QMessageBox.information(self, "成功", "配置已保存")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存配置失败: {str(e)}")
    
    def _reset_config(self):
        """重置为原始配置"""
        reply = QMessageBox.question(
            self, "确认", "确定要放弃所有更改并重置为原始配置吗?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.current_config = self._deep_copy_config(self.original_config)
            self._update_tabs(self.instrument_combo.currentText())
            QMessageBox.information(self, "成功", "配置已重置")
    
    def _export_config(self):
        """导出当前配置到文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出配置", "", "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.current_config, f, indent=4, ensure_ascii=False)
                QMessageBox.information(self, "成功", "配置已导出")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"导出配置失败: {str(e)}")
    
    def _import_config(self):
        """从文件导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入配置", "", "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported_config = json.load(f)
                
                # 验证导入的配置
                if not isinstance(imported_config, dict):
                    raise ValueError("无效的配置文件格式")
                
                self.current_config = imported_config
                self._update_instrument_combo()
                self._update_tabs(self.instrument_combo.currentText())
                QMessageBox.information(self, "成功", "配置已导入")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"导入配置失败: {str(e)}")
    
    def _add_instrument(self):
        """添加新仪器"""
        name, ok = QInputDialog.getText(
            self, "添加仪器", "输入新仪器型号名称:"
        )
        
        if ok and name:
            if name in self.current_config:
                QMessageBox.warning(self, "错误", "该仪器已存在")
                return
            
            # 创建默认配置
            self.current_config[name] = {
                "min_freq": 0,
                "max_freq": 0,
                "min_power": 0,
                "max_power": 0,
                "commands": {},
                "modulation_commands": {}
            }
            
            self._update_instrument_combo()
            self.instrument_combo.setCurrentText(name)
    
    def _remove_instrument(self):
        """移除当前选中的仪器"""
        current_instrument = self.instrument_combo.currentText()
        
        if not current_instrument:
            return
            
        reply = QMessageBox.question(
            self, "确认", f"确定要移除仪器 '{current_instrument}' 吗?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del self.current_config[current_instrument]
            self._update_instrument_combo()
    
    def _add_command(self, table: QTableWidget):
        """向指定表格添加命令"""
        current_instrument = self.instrument_combo.currentText()
        if not current_instrument:
            return
            
        cmd_name, ok1 = QInputDialog.getText(
            self, "添加命令", "输入命令名称:"
        )
        
        if not ok1 or not cmd_name:
            return
            
        cmd_value, ok2 = QInputDialog.getText(
            self, "添加命令", "输入SCPI命令:"
        )
        
        if ok2 and cmd_value:
            # 确定要添加到哪个配置部分
            config_section = "commands" if table == self.commands_table else "modulation_commands"
            
            # 更新配置
            self.current_config[current_instrument][config_section][cmd_name] = cmd_value
            
            # 更新表格
            self._update_commands_table()
    
    def _remove_command(self, table: QTableWidget):
        """从指定表格移除命令"""
        current_instrument = self.instrument_combo.currentText()
        if not current_instrument:
            return
            
        selected_row = table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "错误", "请先选择要移除的命令")
            return
            
        cmd_name = table.item(selected_row, 0).text()
        
        # 确定要从哪个配置部分移除
        config_section = "commands" if table == self.commands_table else "modulation_commands"
        
        # 更新配置
        if cmd_name in self.current_config[current_instrument][config_section]:
            del self.current_config[current_instrument][config_section][cmd_name]
            
        # 更新表格
        self._update_commands_table()
    
    def _update_instrument_combo(self):
        """更新仪器下拉框"""
        current_text = self.instrument_combo.currentText()
        self.instrument_combo.clear()
        self.instrument_combo.addItems(self.current_config.keys())
        
        if current_text in self.current_config:
            self.instrument_combo.setCurrentText(current_text)
    
    def _update_tabs(self, instrument_name: str):
        """更新所有选项卡以显示当前仪器的配置"""
        if instrument_name not in self.current_config:
            return
            
        config = self.current_config[instrument_name]
        
        # 更新基本信息选项卡
        self.model_name_edit.setText(instrument_name)
        self.min_freq_edit.setText(str(config.get("min_freq", 0)))
        self.max_freq_edit.setText(str(config.get("max_freq", 0)))
        self.min_power_edit.setText(str(config.get("min_power", 0)))
        self.max_power_edit.setText(str(config.get("max_power", 0)))
        
        # 更新命令选项卡
        self._update_commands_table()
    
    def _update_commands_table(self):
        """更新命令表格"""
        current_instrument = self.instrument_combo.currentText()
        if not current_instrument:
            return
            
        config = self.current_config[current_instrument]
        
        # 更新标准命令表
        self.commands_table.setRowCount(0)
        for cmd_name, cmd_value in config.get("commands", {}).items():
            row = self.commands_table.rowCount()
            self.commands_table.insertRow(row)
            self.commands_table.setItem(row, 0, QTableWidgetItem(cmd_name))
            self.commands_table.setItem(row, 1, QTableWidgetItem(cmd_value))
        
        # 更新调制命令表
        self.mod_commands_table.setRowCount(0)
        for cmd_name, cmd_value in config.get("modulation_commands", {}).items():
            row = self.mod_commands_table.rowCount()
            self.mod_commands_table.insertRow(row)
            self.mod_commands_table.setItem(row, 0, QTableWidgetItem(cmd_name))
            self.mod_commands_table.setItem(row, 1, QTableWidgetItem(cmd_value))
    
    def _deep_copy_config(self, config: Dict) -> Dict:
        """创建配置的深拷贝"""
        return json.loads(json.dumps(config))
    
    def closeEvent(self, event):
        """关闭窗口时检查是否有未保存的更改"""
        if self.current_config != self.original_config:
            reply = QMessageBox.question(
                self, "未保存的更改", 
                "您有未保存的更改，确定要退出吗?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                self._save_config()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
