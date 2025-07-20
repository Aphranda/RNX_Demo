# app/instruments/plasg_signal_source.py
import pyvisa
from typing import Optional, Dict, Tuple



from app.instruments.interfaces import SignalSource
from app.core.exceptions.instrument import InstrumentCommandError
from app.core.exceptions.instrument import VisaCommandError
from app.core.exceptions.instrument import SignalSourceError


class PlasgT8G40G(SignalSource):
    """PLASG-T8G40G 信号发生器实现类"""
    
    # 仪器规格常量
    MIN_FREQ = 100e3  # 100 kHz
    MAX_FREQ = 40e9   # 40 GHz
    MIN_POWER = -120  # -120 dBm
    MAX_POWER = 20    # 20 dBm
    

    @property
    def model(self) -> str:
        """设备型号（只读）"""
        return self._model
 
    @property
    def serial_number(self) -> str:
        """设备序列号（只读）"""
        return self._serial_number

    @classmethod
    def is_plasg_device(cls, idn: str) -> bool:
        """检查是否是PLASG系列信号源"""
        return "PLASG" in idn.upper()

    def __init__(self, visa_address: str, timeout: int = 3000):
        """
        初始化信号源
        Args:
            visa_address: VISA资源地址
            timeout: 通信超时(ms)
        """
        super().__init__(visa_address)
        self._inst.timeout = timeout
        self._calibration = {
            'freq_offset': 0.0,
            'power_offset': 0.0,
            'power_factor': 1.0
        }

        # 添加模型和序列号属性
        self._inst.timeout = timeout
        self._model = "PLASG-T8G40G"  # 改为实例变量
        self._serial_number = self._parse_serial_number()
        self._initialize_device()

    def _parse_serial_number(self) -> str:
        """从IDN响应中解析序列号"""
        try:
            idn_parts = self.idn.split(',')
            return idn_parts[2].strip() if len(idn_parts) >= 3 else "UNKNOWN"
        except:
            return "UNKNOWN"

    def _initialize_device(self):
        """初始化设备设置"""
        try:
            self._inst.write("*CLS")  # 清除状态
            self._inst.write("*RST")  # 复位设备
            self._inst.write(":OUTP:STATE OFF")  # 关闭输出
            self._load_calibration()  # 加载校准数据
        except pyvisa.VisaIOError as e:
            raise InstrumentCommandError(
                device=self._inst.resource_name,
                message=f"初始化失败: {str(e)}",
                command="*CLS/*RST/:OUTP:STATE OFF"
            )

    def _load_calibration(self):
        """加载校准数据(示例实现)"""
        # 实际项目中应从配置文件或仪器内存加载
        pass

    def _save_calibration(self):
        """保存校准数据(示例实现)"""
        # 实际项目中应保存到配置文件或仪器内存
        pass

    # ========== 基础控制接口 ==========
    def set_cw(self, freq_hz: float, power_dbm: float):
        """设置CW模式(实现接口方法)"""
        self.set_frequency(freq_hz)
        self.set_power(power_dbm)
        # self._inst.write(":FUNC:MODE CW")

    def reset(self):
        """重置设备(实现接口方法)"""
        self._inst.write("*RST;:OUTP:STATE OFF")

    # ========== 增强的频率控制 ==========
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
            print(f":FREQ {actual_freq:.3f}Hz")
            self._inst.write(f":FREQ {actual_freq:.3f}Hz")
        except pyvisa.VisaIOError as e:
            raise VisaCommandError(
                self._inst.resource_name,
                f":FREQ {actual_freq:.3f}Hz",
                str(e)
            )

    def get_frequency(self) -> float:
        """获取当前频率"""
        return float(self._inst.query(":FREQ?"))

    def set_frequency_offset(self, offset_hz: float):
        """设置频率校准偏移量"""
        self._calibration['freq_offset'] = float(offset_hz)
        self._save_calibration()

    # ========== 增强的功率控制 ==========
    def set_power(self, power_dbm: float, *, apply_cal: bool = True):
        """设置精确功率值
        Args:
            power_dbm: 目标功率(dBm)
            apply_cal: 是否应用功率校准
        """
        if not (self.MIN_POWER <= power_dbm <= self.MAX_POWER):
            raise ValueError(f"功率超出范围({self.MIN_POWER}-{self.MAX_POWER}dBm)")
            
        actual_power = power_dbm + (self._calibration['power_offset'] if apply_cal else 0)
        actual_power *= self._calibration['power_factor']
        self._inst.write(f":POW {actual_power:.2f}dBm")

    def get_power(self) -> float:
        """获取当前功率设置"""
        return float(self._inst.query(":POW?"))

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

    # ========== 扫描功能增强 ==========
    def sweep_start(self, start_hz: float, stop_hz: float, 
                   step_hz: float, dwell_ms: int = 100):
        """启动频率扫描(增强版)
        Args:
            start_hz: 起始频率
            stop_hz: 终止频率
            step_hz: 步进频率
            dwell_ms: 驻留时间(ms)
        """
        if not (self.MIN_FREQ <= start_hz <= stop_hz <= self.MAX_FREQ):
            raise ValueError(f"频率范围无效({self.MIN_FREQ}-{self.MAX_FREQ}Hz)")
            
        self._inst.write(":FUNC:MODE SWEP")
        self._inst.write(":STYLSWEP:TYPE STEP")
        self._inst.write(f":STYLSWEP:START {start_hz}Hz")
        self._inst.write(f":STYLSWEP:STOP {stop_hz}Hz")
        self._inst.write(f":STYLSWEP:STEP {step_hz}Hz")
        self._inst.write(f":STYLSWEP:DWELL {dwell_ms}ms")
        self._inst.write(":STYLSWEP:MODE AUTO")
        self._inst.write(":STYLSWEP:STAT ON")

    def sweep_stop(self):
        """停止频率扫描"""
        self._inst.write(":STYLSWEP:STAT OFF")

    # ========== 状态查询 ==========
    def get_status(self) -> Dict:
        """获取设备状态"""
        print(self._inst.query(":OUTP:STATE?").strip())
        return {
            'frequency': self.get_frequency(),
            'power': self.get_power(),
            'output': "ON" in self._inst.query(":OUTP:STATE?").strip(),
            'sweep': "ON" in self._inst.query(":STYL:SWEP:STAT?").strip(),
            'calibration': self._calibration.copy()
        }

    def get_errors(self) -> list:
        """查询设备错误队列"""
        errors = []
        while True:
            err = self._inst.query(":SYST:ERR?")
            if "0,No error" in err:
                break
            errors.append(err.strip())
        return errors

    # ========== 其他功能 ==========
    def set_output(self, state: bool):
        """设置RF输出状态"""
        print(f":OUTP:STATE {'ON' if state else 'OFF'}")
        self._inst.write(f":OUTP:STATE {'ON' if state else 'OFF'}")

    def set_modulation(self, mod_type: str, state: bool):
        """设置调制功能"""
        mod_type = mod_type.upper()
        if mod_type not in ["AM", "FM", "PM", "PULSE"]:
            raise ValueError("无效的调制类型")
        self._inst.write(f":MOD:{mod_type} {'ON' if state else 'OFF'}")

    def close(self):
        """关闭设备连接"""
        if hasattr(self, '_inst') and self._inst:
            self._inst.close()

# 主函数入口，用于调试
if __name__ == "__main__":
    import time
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))  # 调整路径层级
    
    # 替换为你的实际VISA地址
    VISA_ADDRESS = "TCPIP0::192.168.1.10::inst0::INSTR"
    
    try:
        print("=== PLASG-T8G40G 信号源测试 ===")
        
        # 创建信号源实例
        sig_gen = PlasgT8G40G(VISA_ADDRESS)
       
        print(f"已连接: {sig_gen.model} (SN: {sig_gen.serial_number})")
        
        # 测试CW模式
        print("\n测试CW模式:")
        freq_ghz = 10.0  # 10 GHz
        power_dbm = -30.0  # -10 dBm
        print(f"设置频率: {freq_ghz} GHz, 功率: {power_dbm} dBm")
        sig_gen.set_cw(freq_ghz * 1e9, power_dbm)  # 转换为Hz
        sig_gen.set_output(True)
        
        # 获取状态
        status = sig_gen.get_status()
        print(f"当前状态 - 频率: {status['frequency']/1e9:.3f} GHz, "
              f"功率: {status['power']} dBm, "
              f"输出: {'ON' if status['output'] else 'OFF'}")
        
        # # 测试扫描模式
        # print("\n测试扫描模式:")
        # start_ghz = 9.5
        # stop_ghz = 10.5
        # step_mhz = 100
        # print(f"设置扫描: {start_ghz}-{stop_ghz} GHz, 步进: {step_mhz} MHz")
        # sig_gen.sweep_start(start_ghz * 1e9, stop_ghz * 1e9, step_mhz * 1e6)
        # time.sleep(2)  # 等待扫描运行
        
        # # 停止扫描
        # sig_gen.sweep_stop()
        # print("扫描已停止")

        # # 获取状态
        # status = sig_gen.get_status()
        # print(f"当前状态 - 频率: {status['frequency']/1e9:.3f} GHz, "
        #       f"功率: {status['power']} dBm, "
        #       f"输出: {'ON' if status['output'] else 'OFF'}")
        
        # # 关闭输出
        # sig_gen.set_output(False)
        # print("输出已关闭")
        
        # # 检查错误
        # errors = sig_gen.get_errors()
        # if errors:
        #     print("\n仪器错误:")
        #     for err in errors:
        #         print(f"- {err}")
        # else:
        #     print("\n仪器无错误")
            
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
    finally:
        # 确保连接关闭
        if 'sig_gen' in locals():
            sig_gen.close()
            print("\n连接已关闭")
        
    print("\n测试完成")