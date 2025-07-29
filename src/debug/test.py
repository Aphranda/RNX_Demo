import pyvisa
import time

class NRP50SPowerSensor:
    def __init__(self, visa_address="USB0::0x0AAD::0x0161::101636::INSTR", timeout=5000):
        self.visa_address = visa_address
        self.rm = pyvisa.ResourceManager()
        self.instrument = self.rm.open_resource(visa_address)
        self.instrument.timeout = timeout
        self.initialize_device()

    def initialize_device(self):
        """初始化设备：清除错误、复位、设置单位和连续模式"""
        self.instrument.write("*CLS")
        self.instrument.write("*RST")
        self.instrument.write("UNIT:POW DBM")   # 设置单位为 dBm
        self.instrument.write("INIT:CONT ON")   # 连续测量模式
        self.instrument.write("SENS:AVER:AUTO ON")  # 默认使用自动平均
        self.instrument.write("INIT")
        time.sleep(0.5)

    def set_freq(self, freq_Mhz):
        """设置测量信号频率（单位 Hz）"""
        try:
            self.instrument.write(f"SENS:FREQ {freq_Mhz * 1e6}")
        except Exception as e:
            print(f"[NRP50S ERROR] 设置信号频率失败: {e}")

    def get_freq(self):
        """查询当前设置信号频率（单位 MHz）"""
        try:
            value = self.instrument.query("SENS:FREQ?").strip()
            return float(value) / 1e6
        except Exception as e:
            print(f"[NRP50S ERROR] 获取频率失败: {e}")
            return None

    def set_time(self, sample_time_ms):
        """
        设置采样时间（近似方式）：通过设置平均次数来控制采样持续时间
        注意：不同频率和功率下平均一次的时间会变化，此方法为经验估算
        """
        try:
            approx_time_per_avg = 1.5  # 每次平均约 1.5ms（经验值）
            # avg_count = max(1, int(sample_time_ms / approx_time_per_avg))
            self.instrument.write("SENS:AVER:AUTO ON")
            # self.instrument.write(f"SENS:AVER:COUN {avg_count}")
        except Exception as e:
            print(f"[NRP50S ERROR] 设置采样时间失败: {e}")

    def meas_power(self):
        """获取功率值，返回 (None, power_dBm) 形式，兼容其他测量接口"""
        try:
            value = self.instrument.query("FETC?").strip()
            return None, float(value)
        except Exception as e:
            print(f"[NRP50S ERROR] 无法获取功率值: {e}")
            return None, None

    def close(self):
        """关闭仪器连接"""
        if self.instrument:
            self.instrument.close()
        if self.rm:
            self.rm.close()

    def __del__(self):
        """析构时自动关闭资源"""
        try:
            self.close()
        except:
            pass


if __name__ == "__main__":
    NRP50S = NRP50SPowerSensor()
    NRP50S.set_time(10)
    NRP50S.set_freq(30000)

    time_start = time.time()
    _, power = NRP50S.meas_power()
    time_used = time.time() - time_start

    print(power)
    print(time_used)

