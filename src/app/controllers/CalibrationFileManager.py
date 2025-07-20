import os
import hashlib
import shutil
import json
import struct
import threading
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

class CalibrationFileManager:
    """
    校准文件全生命周期管理类
    功能涵盖：创建、写入、验证、版本控制、自动归档、数据完整性检查
    """
    
    def __init__(self, base_dir: str = "calibrations", log_callback: Optional[callable] = None):
        """
        初始化校准文件管理器
        
        :param base_dir: 校准文件存储根目录
        :param log_callback: 日志回调函数，格式为 func(msg: str, level: str)
        """
        self.base_dir = os.path.abspath(base_dir)
        self.active_file: Optional[str] = None
        self.current_meta: Dict = {}
        self.data_points: List = []
        self._file_lock = threading.Lock()
        self.points = 0
        
        os.makedirs(self.base_dir, exist_ok=True)
        
        # 初始化日志系统
        self.log = log_callback if callable(log_callback) else self._default_logger
        
        # 创建必要的子目录
        for subdir in ["archive", "backup"]:
            os.makedirs(os.path.join(self.base_dir, subdir), exist_ok=True)

    def _default_logger(self, msg: str, level: str = "INFO"):
        """默认日志记录器"""
        print(f"[CAL {level}] {msg}")

    def _generate_bin_filename(self, csv_path: str) -> str:
        """根据CSV路径生成对应的BIN文件名"""
        base, ext = os.path.splitext(csv_path)
        return base + ".bin"
    
    def _write_bin_file(self, csv_path: str):
        """将CSV数据写入BIN文件"""
        bin_path = self._generate_bin_filename(csv_path)
        
        # 二进制文件结构：
        # 头部: 4字节幻数(0x524E5843 'RNXC') + 1字节版本(1)
        # 元数据: JSON格式的字符串(UTF-8编码)
        # 数据: 每个数据点9个float32(频率 + 8个参数)
        
        try:
            with open(bin_path, 'wb') as f:
                # 写入头部
                f.write(b'RNXC')  # 幻数
                f.write(bytes([1]))  # 版本号
                
                # 写入元数据
                meta_json = json.dumps(self.current_meta).encode('utf-8')
                f.write(len(meta_json).to_bytes(4, 'little'))  # 元数据长度
                f.write(meta_json)  # 元数据内容
                
                # 写入数据点
                for point in self._data_points:
                    freq = round(point['freq'], 6)  # 确保频率保留6位小数
                    data = [
                        point['x_theta'], point['x_phi'],
                        point['ku_theta'], point['ku_phi'],
                        point['k_theta'], point['k_phi'],
                        point['ka_theta'], point['ka_phi']
                    ]
                    # 写入频率(1个float32)和8个参数(8个float32)
                    f.write(struct.pack('f', freq))
                    f.write(struct.pack('8f', *data))
                
            self.log(f"已生成二进制校准文件: {os.path.basename(bin_path)}", "INFO")
            return bin_path
        except Exception as e:
            self.log(f"生成二进制文件失败: {str(e)}", "ERROR")
            return None

        
    def generate_default_calibration(self, freq_range: Tuple[float, float] = (8.0, 40.0), 
                                step: float = 0.01, freq_list: Optional[List[float]] = None) -> str:
        """
        生成默认校准文件（所有参数为0），支持频点列表或频率范围
        
        :param freq_range: 频率范围(GHz) (start, stop) - 当freq_list为None时使用
        :param step: 频率步进(GHz) - 当freq_list为None时使用
        :param freq_list: 自定义频点列表(GHz)，优先级高于freq_range和step
        :return: 生成的校准文件路径
        """
        # 默认设备元数据
        default_meta = {
            'operator': 'SYSTEM',
            'signal_gen': ('DEFAULT_SG', 'SN00000'),
            'spec_analyzer': ('DEFAULT_SA', 'SN00000'),
            'antenna': ('DEFAULT_ANT', 'SN00000'),
            'environment': (25.0, 50.0)  # 25°C, 50%RH
        }
        
        # 根据输入参数确定频率参数
        if freq_list is not None:
            # 使用自定义频点列表
            if not isinstance(freq_list, list) or len(freq_list) == 0:
                raise ValueError("freq_list必须是非空列表")
            
            # 确保所有频点都是数字且在合理范围内
            valid_freqs = []
            for freq in freq_list:
                try:
                    freq_float = float(freq)
                    if 0.1 <= freq_float <= 100.0:  # 假设合理频率范围是0.1-100GHz
                        valid_freqs.append(round(freq_float, 6))
                    else:
                        self.log(f"忽略超出范围的频率: {freq}GHz", "WARNING")
                except ValueError:
                    self.log(f"忽略无效的频率值: {freq}", "WARNING")
            
            if not valid_freqs:
                raise ValueError("没有有效的频率点")
            
            # 对频点进行排序并去重
            valid_freqs = sorted(list(set(valid_freqs)))
            freq_params = {
                'start_ghz': min(valid_freqs),
                'stop_ghz': max(valid_freqs),
                'step_ghz': 0.1,  # 使用0表示自定义频点
                'custom_freqs': valid_freqs  # 存储自定义频点
            }
            self.points = len(valid_freqs)
        else:
            # 使用频率范围和步进
            start_ghz = min(freq_range)
            stop_ghz = max(freq_range)
            step = abs(step)  # 确保步进为正
            
            # 计算精确的点数，避免浮点误差
            points = int(round((stop_ghz - start_ghz) / step)) + 1
            freq_params = {
                'start_ghz': start_ghz,
                'stop_ghz': stop_ghz,
                'step_ghz': step,
                'custom_freqs': None
            }
        
        # 创建新校准文件
        filepath = self.create_new_calibration(
            equipment_meta=default_meta,
            freq_params=freq_params,
            version_notes="系统生成的默认校准文件（所有参数为0）" + 
                        (" [自定义频点]" if freq_list is not None else "")
        )
        
        # 填充0值数据
        if freq_list is not None:
            # 使用自定义频点
            for freq in valid_freqs:
                zero_data = {
                    'x_theta': 1.0, 'x_phi': 1.0,
                    'ku_theta': 1.0, 'ku_phi': 1.0,
                    'k_theta': 1.0, 'k_phi': 1.0,
                    'ka_theta': 1.0, 'ka_phi': 1.0
                }
                self.add_data_point(freq, zero_data)
        else:
            # 使用频率范围和步进
            for i in range(points):
                freq = start_ghz + i * step
                # 处理浮点精度问题，确保最后一个点是stop_ghz
                if i == points - 1:
                    freq = stop_ghz
                    
                zero_data = {
                    'x_theta': 1.0, 'x_phi': 1.0,
                    'ku_theta': 1.0, 'ku_phi': 1.0,
                    'k_theta': 1.0, 'k_phi': 1.0,
                    'ka_theta': 1.0, 'ka_phi': 1.0
                }
                self.add_data_point(round(freq, 6), zero_data)  # 保留6位小数避免浮点误差
        
        # 完成校准
        archived_path = self.finalize_calibration("系统自动生成的默认校准文件")
        
        return archived_path


    def create_new_calibration(self, 
                             equipment_meta: Dict, 
                             freq_params: Dict, 
                             version_notes: Optional[str] = None) -> str:
        """
        创建新校准文件
        
        :param equipment_meta: 设备元数据
        :param freq_params: 频率参数
        :param version_notes: 版本说明
        :return: 创建的校准文件路径
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
        
        # 计算总点数
        if self.points == 0:
            points = int((freq_params['stop_ghz'] - freq_params['start_ghz']) / freq_params['step_ghz']) + 1
        else:
            points = self.points
        
        # 生成文件名
        filename = (
            f"RNX_Cal_DualPol_"
            f"{freq_params['start_ghz']}to{freq_params['stop_ghz']}GHz_"
            f"step{freq_params['step_ghz']}_{timestamp}.csv"
        )
        
        self.active_file = os.path.join(self.base_dir, filename)
        self.active_bin_file = self._generate_bin_filename(self.active_file)
        self.current_meta = {
            **equipment_meta,
            'freq_params': freq_params,
            'created': timestamp,
            'points': points,
            'version_notes': version_notes,
            'file_format': 'csv+bin'  # 标记文件格式
        }
        self._data_points = []  # 重置数据点
        
        # 写入文件头
        with self._file_lock, open(self.active_file, 'w', encoding='utf-8') as f:
            f.write(self._generate_header())
            if version_notes:
                f.write(f"!VersionNotes: {version_notes}\n")
        
        self.log(f"创建新校准文件: {filename}", "INFO")
        return self.active_file

    def _generate_header(self) -> str:
        """生成标准文件头"""
        meta = self.current_meta
        freq = meta['freq_params']
        
        header_lines = [
            "!RNX Dual-Polarized Feed Calibration Data",
            f"!Created: {meta['created'].replace('_', 'T')}Z",
            f"!Operator: {meta['operator']}",
            "!Equipment:",
            f"!  Signal_Generator: {meta['signal_gen'][0]}_SN:{meta['signal_gen'][1]}",
            f"!  Spectrum_Analyzer: {meta['spec_analyzer'][0]}_SN:{meta['spec_analyzer'][1]}",
            f"!  Antenna: {meta['antenna'][0]}_SN:{meta['antenna'][1]}",
            f"!Environment: {meta['environment'][0]}C, {meta['environment'][1]}%RH",
            "!Frequency:",
            f"!  Start: {freq['start_ghz']} GHz",
            f"!  Stop: {freq['stop_ghz']} GHz",
            f"!  Step: {freq['step_ghz']} GHz",
            f"!  Points: {meta['points']}",
            "!Data Columns:",
            "!  1: Frequency(GHz)",
            "!  2: X_Theta(dB)",
            "!  3: X_Phi(dB)",
            "!  4: Ku_Theta(dB)",
            "!  5: Ku_Phi(dB)",
            "!  6: K_Theta(dB)",
            "!  7: K_Phi(dB)",
            "!  8: Ka_Theta(dB)",
            "!  9: Ka_Phi(dB)",
            "Frequency(GHz),X_Theta,X_Phi,Ku_Theta,Ku_Phi,K_Theta,K_Phi,Ka_Theta,Ka_Phi"
        ]
        return '\n'.join(header_lines) + '\n'

    def add_data_point(self, freq_ghz: float, data: Dict) -> bool:
        """
        添加单频点数据
        
        :param freq_ghz: 当前频率(GHz)
        :param data: 测量数据
        :return: 是否成功添加
        """
        if not self.active_file:
            raise RuntimeError("没有活动的校准文件")
        
        # 验证数据范围
        for key, value in data.items():
            if not isinstance(value, (int, float)):
                self.log(f"无效数据格式: {key}={value}", "ERROR")
                return False
            if not (-100 <= value <= 100):  # 假设合理范围是-100到100 dB
                self.log(f"数据超出范围: {key}={value}", "WARNING")
        
        # 存储数据点用于BIN文件
        self._data_points.append({
            'freq': round(freq_ghz, 6),  # 确保频率保留6位小数
            **data
        })
        
        # 格式化数据行 - 修改这里，将:.3f改为:.6f
        data_row = (
            f"{freq_ghz:.6f},"  # 修改为保留6位小数
            f"{data.get('x_theta', -99.99):.2f},"
            f"{data.get('x_phi', -99.99):.2f},"
            f"{data.get('ku_theta', -99.99):.2f},"
            f"{data.get('ku_phi', -99.99):.2f},"
            f"{data.get('k_theta', -99.99):.2f},"
            f"{data.get('k_phi', -99.99):.2f},"
            f"{data.get('ka_theta', -99.99):.2f},"
            f"{data.get('ka_phi', -99.99):.2f}\n"
        )
        
        # 写入数据（线程安全）
        with self._file_lock, open(self.active_file, 'a', encoding='utf-8') as f:
            f.write(data_row)
        
        return True

    
    def finalize_calibration(self, notes: str = "") -> Tuple[str, str]:
        """
        完成校准并添加校验信息
        
        :param notes: 附加说明
        :return: (归档后的CSV文件路径, BIN文件路径)
        """
        if not self.active_file:
            raise RuntimeError("没有活动的校准文件")
        
        # 添加结束标记
        with self._file_lock, open(self.active_file, 'a', encoding='utf-8') as f:
            f.write(f"!EndOfData: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n")
            if notes:
                f.write(f"!Notes: {notes}\n")
        
        # 生成MD5校验
        file_hash = self._calculate_file_hash()
        with open(self.active_file, 'a', encoding='utf-8') as f:
            f.write(f"!MD5: {file_hash}\n")
        
        # 生成BIN文件
        bin_path = self._write_bin_file(self.active_file)
        
        self.log(f"校准完成: {os.path.basename(self.active_file)}", "SUCCESS")
        
        # 归档文件
        archived_csv = self._archive_file()  # 归档CSV
        archived_bin = self._archive_file(bin_path) if bin_path else None  # 归档BIN
        
        self.active_file = None
        self.active_bin_file = None
        self.current_meta = {}
        self._data_points = []
        
        return archived_csv, archived_bin

    def load_calibration_file(self, filepath: str) -> Optional[Dict]:
        """
        加载校准文件(支持CSV和BIN格式)
        
        :param filepath: 文件路径
        :return: 包含元数据和数据的字典，None表示失败
        """
        if not os.path.exists(filepath):
            self.log(f"文件不存在: {filepath}", "ERROR")
            return None
        
        # 根据扩展名选择加载方式
        if filepath.lower().endswith('.bin'):
            return self._load_bin_file(filepath)
        else:
            return self._load_csv_file(filepath)
        
    def _load_bin_file(self, bin_path: str) -> Optional[Dict]:
        """
        加载BIN格式校准文件
        1. 先验证文件有效性
        2. 再读取文件内容
        """
        # 先验证文件
        if not self._validate_bin_file(bin_path):
            self.log(f"BIN文件验证失败: {bin_path}", "ERROR")
            return None
        
        # 验证通过后读取内容
        return self._read_bin_content(bin_path)

    def _validate_bin_file(self, filepath: str) -> bool:
        """
        验证BIN格式校准文件结构是否有效
        不解析具体内容，只检查文件格式和完整性
        """
        try:
            with open(filepath, 'rb') as f:
                # 验证头部
                magic = f.read(4)
                if magic != b'RNXC':
                    self.log("无效的二进制文件格式", "WARNING")
                    return False
                
                version = ord(f.read(1))
                if version != 1:
                    self.log(f"不支持的版本号: {version}", "WARNING")
                    return False
                
                # 读取元数据长度
                meta_len = int.from_bytes(f.read(4), 'little')
                # 跳过元数据
                f.seek(meta_len, 1)
                
                # 检查数据点数量
                file_size = os.path.getsize(filepath)
                header_size = 4 + 1 + 4 + meta_len  # 幻数+版本+长度+元数据
                data_size = file_size - header_size
                
                if data_size % 36 != 0:  # 每个数据点36字节(4+32)
                    self.log("数据大小不匹配", "WARNING")
                    return False
                
                return True
                
        except Exception as e:
            self.log(f"验证二进制文件失败: {str(e)}", "ERROR")
            return False
        
    def _read_bin_content(self, bin_path: str) -> Optional[Dict]:
        """
        读取已验证的BIN文件内容
        假设文件已经通过验证，直接解析内容
        """
        try:
            with open(bin_path, 'rb') as f:
                # 跳过已验证的头部
                f.read(4)  # 幻数
                f.read(1)  # 版本
                meta_len = int.from_bytes(f.read(4), 'little')
                meta_json = f.read(meta_len).decode('utf-8')
                meta = json.loads(meta_json)
                
                # 读取数据点
                data_points = []
                while True:
                    freq_bytes = f.read(4)
                    if not freq_bytes:
                        break
                    
                    freq = struct.unpack('f', freq_bytes)[0]
                    data = struct.unpack('8f', f.read(32))  # 8个float32=32字节
                    
                    data_points.append({
                        'freq': freq,
                        'x_theta': data[0], 'x_phi': data[1],
                        'ku_theta': data[2], 'ku_phi': data[3],
                        'k_theta': data[4], 'k_phi': data[5],
                        'ka_theta': data[6], 'ka_phi': data[7]
                    })
                self.current_meta = meta
                self.data_points = data_points
                return {
                    'meta': meta,
                    'data': data_points
                }
        except Exception as e:
            self.log(f"读取二进制文件内容失败: {str(e)}", "ERROR")
            return None

    def _load_csv_file(self, csv_path: str) -> Optional[Dict]:
        """
        加载CSV格式校准文件
        1. 先验证文件有效性
        2. 再读取文件内容
        """
        # 先验证文件
        if not self._validate_csv_file(csv_path):
            self.log(f"CSV文件验证失败: {csv_path}", "ERROR")
            return None
        
        # 验证通过后读取内容
        return self._read_csv_content(csv_path)

    def _validate_csv_file(self, filepath: str) -> bool:
        """
        验证CSV格式校准文件结构是否有效
        不解析具体数据值，只检查文件结构和元数据
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 检查文件头
            if not lines or not lines[0].startswith("!RNX Dual-Polarized Feed Calibration Data"):
                self.log("无效的文件头", "WARNING")
                return False
                
            # 定义必需的头字段
            REQUIRED_HEADERS = {
                "!Created:", "!Operator:", "!  Signal_Generator:", 
                "!  Spectrum_Analyzer:", "!  Antenna:", "!Environment:",
                "!  Start:", "!  Stop:", "!  Step:", "!  Points:", "!Data Columns:"
            }
            
            # 检查所有必需字段是否存在
            header_lines = [line.strip() for line in lines if line.startswith("!")]
            missing_headers = [h for h in REQUIRED_HEADERS if not any(l.startswith(h) for l in header_lines)]
            
            if missing_headers:
                self.log(f"文件头缺少必需字段: {', '.join(missing_headers)}", "WARNING")
                return False
            
            # 检查数据部分标题行
            data_lines = [line for line in lines if not line.startswith("!") and line.strip()]
            if not data_lines or not data_lines[0].startswith("Frequency(GHz),"):
                self.log("缺少或无效的数据标题行", "WARNING")
                return False
                
            # 检查结束标记
            if not any(line.startswith("!EndOfData:") for line in lines[-3:]):
                self.log("缺少结束标记", "WARNING")
                return False
                
            if not any(line.startswith("!MD5:") for line in lines[-3:]):
                self.log("缺少MD5校验", "WARNING")
                return False
                
            return True
            
        except Exception as e:
            self.log(f"验证CSV文件失败: {str(e)}", "ERROR")
            return False

    def _read_csv_content(self, csv_path: str) -> Optional[Dict]:
        """
        读取已验证的CSV文件内容
        假设文件已经通过验证，直接解析内容
        
        返回包含完整元数据和数据点的字典:
        {
            'meta': {
                'file_format': str,
                'header': list,
                'created': str,
                'operator': str,
                'signal_gen': (model, sn),
                'spec_analyzer': (model, sn),
                'antenna': (model, sn),
                'environment': (temp, humidity),
                'freq_params': {
                    'start_ghz': float,
                    'stop_ghz': float,
                    'step_ghz': float
                },
                'points': int,
                'version_notes': str,
                'end_of_data': str,
                'md5': str
            },
            'data': list  # 数据点列表
        }
        """
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 初始化元数据字典
            meta = {
                'file_format': 'csv',
                'header': [],
                'signal_gen': ('未知', '未知'),
                'spec_analyzer': ('未知', '未知'),
                'antenna': ('未知', '未知'),
                'environment': (0.0, 0.0),
                'freq_params': {
                    'start_ghz': 0.0,
                    'stop_ghz': 0.0,
                    'step_ghz': 0.0
                }
            }
            
            data_start = 0
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('!'):
                    meta['header'].append(line)
                    
                    # 解析创建时间
                    if line.startswith('!Created:'):
                        meta['created'] = line.split(':', 1)[1].strip()
                    
                    # 解析操作员
                    elif line.startswith('!Operator:'):
                        meta['operator'] = line.split(':', 1)[1].strip()
                    
                    # 解析信号源信息
                    elif line.startswith('!  Signal_Generator:'):
                        parts = line.split('_SN:')
                        model = parts[0].split(':', 1)[1].strip()
                        sn = parts[1].strip() if len(parts) > 1 else '未知'
                        meta['signal_gen'] = (model, sn)
                    
                    # 解析频谱分析仪信息
                    elif line.startswith('!  Spectrum_Analyzer:'):
                        parts = line.split('_SN:')
                        model = parts[0].split(':', 1)[1].strip()
                        sn = parts[1].strip() if len(parts) > 1 else '未知'
                        meta['spec_analyzer'] = (model, sn)
                    
                    # 解析天线信息
                    elif line.startswith('!  Antenna:'):
                        parts = line.split('_SN:')
                        model = parts[0].split(':', 1)[1].strip()
                        sn = parts[1].strip() if len(parts) > 1 else '未知'
                        meta['antenna'] = (model, sn)
                    
                    # 解析环境信息
                    elif line.startswith('!Environment:'):
                        env_parts = line.split(':', 1)[1].strip().split(',')
                        temp = float(env_parts[0].replace('C', '').strip())
                        humidity = float(env_parts[1].replace('%RH', '').strip())
                        meta['environment'] = (temp, humidity)
                    
                    # 解析频率参数
                    elif line.startswith('!  Start:'):
                        meta['freq_params']['start_ghz'] = float(line.split(':', 1)[1].replace('GHz', '').strip())
                    elif line.startswith('!  Stop:'):
                        meta['freq_params']['stop_ghz'] = float(line.split(':', 1)[1].replace('GHz', '').strip())
                    elif line.startswith('!  Step:'):
                        meta['freq_params']['step_ghz'] = float(line.split(':', 1)[1].replace('GHz', '').strip())
                    elif line.startswith('!  Points:'):
                        meta['points'] = int(line.split(':', 1)[1].strip())
                    
                    # 解析版本说明
                    elif line.startswith('!VersionNotes:'):
                        meta['version_notes'] = line.split(':', 1)[1].strip()
                    
                    # 解析结束标记
                    elif line.startswith('!EndOfData:'):
                        meta['end_of_data'] = line.split(':', 1)[1].strip()
                    
                    # 解析MD5校验
                    elif line.startswith('!MD5:'):
                        meta['md5'] = line.split(':', 1)[1].strip()
                
                else:
                    data_start = i
                    break
            
            # 跳过标题行（第一个非注释行）
            data_lines = [line.strip() for line in lines[data_start:] if line.strip() and not line.startswith('!')]
            if not data_lines:
                self.log("没有有效数据行", "WARNING")
                return None
                
            # 确认标题行
            header_line = data_lines[0]
            if not header_line.startswith("Frequency(GHz),"):
                self.log(f"无效的数据标题行: {header_line}", "WARNING")
                return None
                
            # 处理数据行（跳过标题行）
            data_points = []
            for line in data_lines[1:]:
                if not line or line.startswith('!'):
                    continue
                    
                parts = line.split(',')
                if len(parts) != 9:
                    self.log(f"数据行格式错误，应有9列，实际{len(parts)}列: {line}", "WARNING")
                    continue
                
                try:
                    freq = float(parts[0])
                    # 验证频率值范围 (假设在0.1-100 GHz之间)
                    if not (0.1 <= freq <= 100.0):
                        self.log(f"频率值{freq}GHz超出有效范围(0.1-100GHz)", "WARNING")
                        continue
                    
                    # 验证补偿值范围 (假设在-100到100 dB之间)
                    compensation_values = []
                    for val in parts[1:9]:
                        try:
                            num = float(val)
                            if not (-100 <= num <= 100):
                                self.log(f"补偿值超出有效范围(-100-100dB): {val}", "WARNING")
                                break
                            compensation_values.append(num)
                        except ValueError:
                            self.log(f"无效数值格式: {val}", "WARNING")
                            break
                    
                    if len(compensation_values) != 8:
                        continue  # 跳过无效行
                        
                    data_points.append({
                        'freq': freq,
                        'x_theta': compensation_values[0],
                        'x_phi': compensation_values[1],
                        'ku_theta': compensation_values[2],
                        'ku_phi': compensation_values[3],
                        'k_theta': compensation_values[4],
                        'k_phi': compensation_values[5],
                        'ka_theta': compensation_values[6],
                        'ka_phi': compensation_values[7]
                    })
                except ValueError as e:
                    self.log(f"数据行解析失败: {line} - {str(e)}", "WARNING")
                    continue
            
            # 更新实例变量
            self.current_meta = meta
            self.data_points = data_points
            
            return {
                'meta': meta,
                'data': data_points
            }
            
        except Exception as e:
            self.log(f"读取CSV文件内容失败: {str(e)}", "ERROR")
            return None


    def _calculate_file_hash(self) -> str:
        """计算文件MD5校验值"""
        hash_md5 = hashlib.md5()
        with open(self.active_file, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _archive_file(self, filepath: Optional[str] = None) -> str:
        """将文件移动到归档目录
        :param filepath: 要归档的文件路径，如果为None则使用self.active_file
        :return: 归档后的文件路径
        """
        archive_dir = os.path.join(self.base_dir, "archive")
        os.makedirs(archive_dir, exist_ok=True)
        
        src = filepath if filepath is not None else self.active_file
        if src is None:
            raise ValueError("没有指定要归档的文件")
        
        filename = os.path.basename(src)
        dst = os.path.join(archive_dir, filename)
        
        shutil.move(src, dst)
        return dst

    def _backup_file(self) -> bool:
        """创建备份文件"""
        if not self.active_file:
            return False
            
        backup_dir = os.path.join(self.base_dir, "backup")
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(
            backup_dir, 
            f"backup_{os.path.basename(self.active_file)}_{timestamp}"
        )
        
        try:
            with self._file_lock:
                shutil.copy2(self.active_file, backup_file)
            self.log(f"创建备份: {backup_file}", "INFO")
            return True
        except Exception as e:
            self.log(f"备份失败: {str(e)}", "ERROR")
            return False

    def get_recent_calibrations(self, days: int = 7) -> List[Dict]:
        """
        获取最近校准记录
        
        :param days: 查询最近多少天的记录
        :return: 校准文件信息列表 [{
                'filename': str,
                'path': str,
                'modified': datetime,
                'size': int
            }]
        """
        recent_files = []
        cutoff_time = datetime.now() - datetime.timedelta(days=days)
        
        # 搜索主目录和归档目录
        search_dirs = [self.base_dir, os.path.join(self.base_dir, "archive")]
        
        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue
                
            for root, _, files in os.walk(search_dir):
                for file in files:
                    if file.startswith("RNX_Cal_DualPol_") and file.endswith(".csv"):
                        filepath = os.path.join(root, file)
                        try:
                            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                            if mtime > cutoff_time:
                                recent_files.append({
                                    'filename': file,
                                    'path': filepath,
                                    'modified': mtime,
                                    'size': os.path.getsize(filepath),
                                    'is_archived': "archive" in root
                                })
                        except Exception as e:
                            self.log(f"处理文件{file}失败: {str(e)}", "WARNING")
        
        # 按修改时间排序
        recent_files.sort(key=lambda x: x['modified'], reverse=True)
        return recent_files

    def get_version_history(self, filepath: str) -> List[str]:
        """
        获取文件的版本历史
        
        :param filepath: 校准文件路径
        :return: 版本说明列表
        """
        versions = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith("!VersionNotes:"):
                        versions.append(line.split(":", 1)[1].strip())
        except Exception as e:
            self.log(f"获取版本历史失败: {str(e)}", "ERROR")
        return versions
