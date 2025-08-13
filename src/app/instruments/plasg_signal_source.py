# app/instruments/plasg_signal_source.py
import json
import time
import pyvisa
from pathlib import Path
from typing import Dict, Optional

from app.instruments.interfaces import SignalSource
from app.core.exceptions.instrument import InstrumentCommandError
from app.core.exceptions.instrument import VisaCommandError
from app.core.exceptions.instrument import SignalSourceError


class PlasgT8G40G(SignalSource):
    """PLASG-T8G40G 信号发生器实现类"""
    
    def __init__(self, visa_address: str, timeout: int = 3000, config: dict = None):
        """
        初始化信号源
        Args:
            visa_address: VISA资源地址
            timeout: 通信超时(ms)
            config: 仪器配置字典
        """
        super().__init__(visa_address)
        self._inst.timeout = timeout
        self._config = config or {}
        self._calibration = {
            'freq_offset': 0.0,
            'power_offset': 0.0,
            'power_factor': 1.0
        }

        # 从配置中获取规格参数，如果没有则使用默认值
        self.MIN_FREQ = float(self._config.get("min_freq", 100e3))  # 默认100 kHz
        self.MAX_FREQ = float(self._config.get("max_freq", 40e9))   # 默认40 GHz
        self.MIN_POWER = float(self._config.get("min_power", -40)) # 默认-40 dBm
        self.MAX_POWER = float(self._config.get("max_power", 0))   # 默认0 dBm

        # 加载调制命令
        self._mod_commands = self._config.get("modulation_commands", {})

        # 添加模型和序列号属性
        self._model = "PLASG-T8G40G"
        self._serial_number = self._parse_serial_number()
        
        # 加载指令配置
        self._commands = self._load_commands()
        self._initialize_device()

    def _parse_serial_number(self) -> str:
        """从IDN响应中解析序列号"""
        try:
            idn_parts = self.idn.split(',')
            return idn_parts[2].strip() if len(idn_parts) >= 3 else "UNKNOWN"
        except:
            return "UNKNOWN"

    def _load_commands(self) -> Dict:
        """从JSON文件或传入配置加载指令配置"""
        if self._config and "commands" in self._config:
            return self._config["commands"]
        
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
                "set_frequency": ":FREQ {freq_hz:.3f}Hz",
                "get_frequency": ":FREQ?",
                "set_power": ":POW {power_dbm:.2f}dBm",
                "get_power": ":POW?",
                "set_output": ":OUTP:STATE {state}",
                "get_output": ":OUTP:STATE?",
                "get_errors": ":SYST:ERR?"
            }


    def _initialize_device(self):
        """初始化设备设置"""
        try:
            self._inst.write(self._commands["clear_status"])
            self._inst.write(self._commands["reset"])
            self._inst.write(self._commands["set_output"].format(state="OFF"))
            self._load_calibration()
        except pyvisa.VisaIOError as e:
            raise InstrumentCommandError(
                device=self._inst.resource_name,
                message=f"初始化失败: {str(e)}",
                command="*CLS/*RST/:OUTP:STATE OFF"
            )

    def _load_calibration(self):
        """加载校准数据(示例实现)"""
        pass

    def _save_calibration(self):
        """保存校准数据(示例实现)"""
        pass

    # ========== 基础控制接口 ==========
    def set_cw(self, freq_hz: float, power_dbm: float):
        """设置CW模式(实现接口方法)"""
        self.set_frequency(freq_hz)
        self.set_power(power_dbm)

    def reset(self):
        """重置设备(实现接口方法)"""
        self._inst.write(self._commands["reset"])
        self._inst.write(self._commands["set_output"].format(state="OFF"))

    # ========== 频率控制 ==========
    def set_frequency(self, freq_hz: float, *, apply_cal: bool = True):
        """设置精确频率值"""
        try:
            if not (self.MIN_FREQ <= freq_hz <= self.MAX_FREQ):
                raise SignalSourceError(
                    self._inst.resource_name,
                    "frequency",
                    freq_hz,
                    (self.MIN_FREQ, self.MAX_FREQ)
                )
                
            actual_freq = freq_hz + (self._calibration['freq_offset'] if apply_cal else 0)
            cmd = self._commands["set_frequency"].format(freq_hz=actual_freq)
            self._inst.write(cmd)
        except pyvisa.VisaIOError as e:
            raise VisaCommandError(
                self._inst.resource_name,
                cmd,
                str(e)
            )

    def get_frequency(self) -> float:
        """获取当前频率"""
        cmd = self._commands["get_frequency"]
        return float(self._inst.query(cmd))

    def set_frequency_offset(self, offset_hz: float):
        """设置频率校准偏移量"""
        self._calibration['freq_offset'] = float(offset_hz)
        self._save_calibration()

    # ========== 功率控制 ==========
    def set_power(self, power_dbm: float, *, apply_cal: bool = True):
        """设置精确功率值"""
        if not (self.MIN_POWER <= power_dbm <= self.MAX_POWER):
            raise ValueError(f"功率超出范围({self.MIN_POWER}-{self.MAX_POWER}dBm)")
            
        actual_power = power_dbm + (self._calibration['power_offset'] if apply_cal else 0)
        actual_power *= self._calibration['power_factor']
        cmd = self._commands["set_power"].format(power_dbm=actual_power)
        self._inst.write(cmd)

    def get_power(self) -> float:
        """获取当前功率设置"""
        cmd = self._commands["get_power"]
        return float(self._inst.query(cmd))

    def set_power_offset(self, offset_db: float):
        """设置功率校准偏移量"""
        self._calibration['power_offset'] = float(offset_db)
        self._save_calibration()

    def set_power_factor(self, factor: float):
        """设置功率校准因子"""
        if not 0.5 <= factor <= 2.0:
            raise ValueError("校准因子必须在0.5-2.0之间")
        self._calibration['power_factor'] = float(factor)
        self._save_calibration()

    # ========== 扫描功能 ==========
    def sweep_start(self, start_hz: float, stop_hz: float, 
                   step_hz: float, dwell_ms: int = 100):
        """启动频率扫描"""
        if not (self.MIN_FREQ <= start_hz <= stop_hz <= self.MAX_FREQ):
            raise ValueError(f"频率范围无效({self.MIN_FREQ}-{self.MAX_FREQ}Hz)")
            
        self._inst.write(self._commands["set_sweep_mode"])
        self._inst.write(self._commands["set_sweep_type"].format(type="STEP"))
        self._inst.write(self._commands["set_sweep_start"].format(start_hz=start_hz))
        self._inst.write(self._commands["set_sweep_stop"].format(stop_hz=stop_hz))
        self._inst.write(self._commands["set_sweep_step"].format(step_hz=step_hz))
        self._inst.write(self._commands["set_sweep_dwell"].format(dwell_ms=dwell_ms))
        self._inst.write(self._commands["set_sweep_mode_auto"])
        self._inst.write(self._commands["set_sweep_state"].format(state="ON"))

    def sweep_stop(self):
        """停止频率扫描"""
        self._inst.write(self._commands["set_sweep_state"].format(state="OFF"))

    # ========== 状态查询 ==========
    def get_status(self) -> Dict:
        """获取设备状态"""
        return {
            'frequency': self.get_frequency(),
            'power': self.get_power(),
            'output': "ON" in self._inst.query(self._commands["get_output"]).strip(),
            'sweep': "ON" in self._inst.query(self._commands["get_sweep_state"]).strip(),
            'calibration': self._calibration.copy()
        }

    def get_errors(self) -> list:
        """查询设备错误队列"""
        errors = []
        while True:
            err = self._inst.query(self._commands["get_errors"])
            if "0,No error" in err:
                break
            errors.append(err.strip())
        return errors

    # ========== 其他功能 ==========
    def set_output(self, state: bool):
        """设置RF输出状态"""
        cmd = self._commands["set_output"].format(state="ON" if state else "OFF")
        self._inst.write(cmd)

    def set_modulation(self, mod_type: str, state: bool):
        """设置调制功能"""
        mod_type = mod_type.upper()
        if mod_type not in ["AM", "FM", "PM", "PULSE"]:
            raise ValueError("无效的调制类型")
        
        if "set_modulation" not in self._mod_commands:
            raise NotImplementedError("该设备不支持调制功能")
            
        cmd = self._mod_commands["set_modulation"].format(
            mod_type=mod_type, 
            state="ON" if state else "OFF"
        )
        self._inst.write(cmd)

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
