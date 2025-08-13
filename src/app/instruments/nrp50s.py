# app/instruments/nrp50s.py
import json
import time
from pathlib import Path
from typing import Optional

from app.instruments.interfaces import PowerSensor


class NRP50S(PowerSensor):
    def __init__(self, visa_address: str, timeout: int = 5000):
        super().__init__(visa_address)
        self._inst.timeout = timeout
        self._model = "NRP50S"
        self._serial_number = self._parse_serial_number()
        
        # 加载指令配置
        self._commands = self._load_commands()
        self.initialize_device()

    def _parse_serial_number(self) -> str:
        """从IDN响应中解析序列号"""
        try:
            idn_parts = self.idn.split(',')
            return idn_parts[2].strip() if len(idn_parts) >= 3 else "UNKNOWN"
        except:
            return "UNKNOWN"

    def _load_commands(self) -> dict:
        """从JSON文件加载指令配置"""
        try:
            config_path = Path(__file__).parent.parent.parent / "config" / "instrument_commands.json"
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get(self._model, {}).get("commands", {})
        except Exception as e:
            print(f"加载指令配置失败: {str(e)}")
            # 提供默认指令作为后备
            return {
                "reset": "*RST",
                "clear_status": "*CLS",
                "set_power_unit": "UNIT:POW DBM",
                "set_continuous_mode": "INIT:CONT ON",
                "set_auto_averaging": "SENS:AVER:AUTO ON",
                "initiate": "INIT",
                "set_frequency": "SENS:FREQ {freq_hz}",
                "set_frequency_correction": "SENS:FREQ:CORR {offset_db}",
                "set_averaging": "SENS:AVER:COUN {count}",
                "fetch_power": "FETC?",
                "get_errors": "SYST:ERR?"
            }

    def initialize_device(self):
        """使用配置的指令初始化设备"""
        try:
            self._inst.write(self._commands["clear_status"])
            self._inst.write(self._commands["reset"])
            self._inst.write(self._commands["set_power_unit"])
            self._inst.write(self._commands["set_continuous_mode"])
            self._inst.write(self._commands["set_auto_averaging"])
            self._inst.write(self._commands["initiate"])
            time.sleep(0.5)
        except Exception as e:
            self.log_error(f"Initialization failed: {str(e)}")

    def set_frequency_correction(self, offset_db: float):
        """实现接口方法"""
        cmd = self._commands["set_frequency_correction"].format(offset_db=offset_db)
        self._inst.write(cmd)

    def set_averaging(self, count: int):
        """实现接口方法"""
        if not 1 <= count <= 1000:
            raise ValueError("平均次数必须在1-1000之间")
        cmd = self._commands["set_averaging"].format(count=count)
        self._inst.write(cmd)

    def measure_power(self, freq_hz: Optional[float] = None) -> float:
        """
        测量功率
        Args:
            freq_hz: 频率(Hz)，可选
        Returns:
            测量功率值(dBm)
        """
        try:
            if freq_hz is not None:
                cmd = self._commands["set_frequency"].format(freq_hz=freq_hz)
                self._inst.write(cmd)
            
            cmd = self._commands["fetch_power"]
            value = self._inst.query(cmd).strip()
            return float(value)
        except Exception as e:
            self.log_error(f"Power measurement failed: {str(e)}")
            return float('nan')

    def reset(self):
        """重置设备"""
        self._inst.write(self._commands["reset"])
        self.initialize_device()

    def log_error(self, message: str):
        """记录错误信息"""
        print(f"[NRP50S ERROR] {message}")

    @property
    def model(self) -> str:
        """设备型号（只读）"""
        return self._model
 
    @property
    def serial_number(self) -> str:
        """设备序列号（只读）"""
        return self._serial_number

    def close(self):
        """关闭设备连接"""
        if hasattr(self, '_inst') and self._inst:
            self._inst.close()

    def __del__(self):
        """析构函数确保资源释放"""
        self.close()
