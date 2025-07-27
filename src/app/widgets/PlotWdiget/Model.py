import csv
import os
import re
from collections import defaultdict

class PlotModel:
    def __init__(self):
        self.data = defaultdict(list)
    
    def load_calibration_data(self, file_path):
        """从CSV文件加载校准数据"""
        if not os.path.exists(file_path):
            return False, f"文件不存在: {file_path}"
        
        try:
            # 自动检测文件编码
            encoding = self.detect_file_encoding(file_path)
            
            with open(file_path, 'r', encoding=encoding) as f:
                # 读取前几行确定文件格式
                lines = [f.readline() for _ in range(10)]
                f.seek(0)
                
                # 确定分隔符
                delimiter = self.detect_delimiter(lines)
                
                # 确定标题行位置
                header_row = self.find_header_row(lines)
                
                # 跳过注释行
                reader = csv.reader(f, delimiter=delimiter)
                for _ in range(header_row):
                    next(reader)
                
                # 读取标题行
                headers = next(reader)
                headers = [h.strip() for h in headers]
                
                # 查找频率列
                freq_idx = self.find_column_index(headers, ['频率', 'freq', 'frequency', 'ghz'])
                
                # 查找数据列
                data_columns = []
                for col_name in ['Theta', 'Phi', 'Theta_corrected', 'Phi_corrected', '增益', 'gain']:
                    idx = self.find_column_index(headers, [col_name])
                    if idx is not None:
                        data_columns.append((idx, col_name))
                
                if freq_idx is None or not data_columns:
                    return False, "未找到频率或增益数据列"
                
                # 读取数据行
                for row in reader:
                    if not row or row[0].startswith('!') or row[0].startswith('#'):
                        continue
                    
                    try:
                        # 提取频率值
                        freq_str = row[freq_idx].strip().lower()
                        freq = float(re.sub(r'[^\d.]', '', freq_str))
                        
                        # 提取数据值
                        for idx, col_name in data_columns:
                            value_str = row[idx].strip()
                            if value_str:
                                try:
                                    value = float(re.sub(r'[^\d.-]', '', value_str))
                                    self.data[col_name].append((freq, value))
                                except ValueError:
                                    continue
                    except (IndexError, ValueError) as e:
                        continue
                
                if not any(self.data.values()):
                    return False, "未找到有效数据"
                
                return True, "数据加载成功"
        except Exception as e:
            return False, f"加载校准数据失败: {str(e)}"
    
    def detect_file_encoding(self, file_path):
        """尝试检测文件编码"""
        try:
            import chardet
            with open(file_path, 'rb') as f:
                raw_data = f.read(4096)
                result = chardet.detect(raw_data)
                return result['encoding'] or 'utf-8'
        except:
            return 'utf-8'
    
    def detect_delimiter(self, lines):
        """检测CSV文件的分隔符"""
        delimiters = [',', ';', '\t', '|']
        delimiter_counts = {d: 0 for d in delimiters}
        
        for line in lines:
            for d in delimiters:
                delimiter_counts[d] += line.count(d)
        
        return max(delimiters, key=lambda d: delimiter_counts[d])
    
    def find_header_row(self, lines):
        """查找标题行位置"""
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in ['frequency', 'freq', '频率']):
                return i
        return 0
    
    def find_column_index(self, headers, keywords):
        """查找包含关键词的列索引"""
        for i, header in enumerate(headers):
            header_lower = header.lower()
            for keyword in keywords:
                if keyword.lower() in header_lower:
                    return i
        return None
    
    def add_custom_data(self, name, points):
        """添加自定义数据系列"""
        self.data[name] = points
    
    def clear_data(self):
        """清除所有数据"""
        self.data.clear()
    
    def get_data(self):
        """获取当前数据"""
        return self.data
