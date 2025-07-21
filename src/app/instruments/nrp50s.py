# app/instruments/nrp50s.py
import pyvisa
import time
from app.instruments.interfaces import PowerSensor

class NRP50S(PowerSensor):
    def __init__(self, visa_address: str, timeout: int = 5000):
        super().__init__(visa_address)  # 调用基类初始化，已经创建self._inst
        self._inst.timeout = timeout  # 设置超时

        # 添加模型和序列号属性
        self._model = "NRP50S"  # 改为实例变量
        self._serial_number = self._parse_serial_number()

        self.initialize_device()

    def _parse_serial_number(self) -> str:
        """从IDN响应中解析序列号"""
        try:
            idn_parts = self.idn.split(',')
            return idn_parts[2].strip() if len(idn_parts) >= 3 else "UNKNOWN"
        except:
            return "UNKNOWN"

    def set_frequency_correction(self, offset_db: float):
        """实现接口方法"""
        self._inst.write(f"SENS:FREQ:CORR {offset_db}")

    def set_averaging(self, count: int):
        """实现接口方法"""
        if not 1 <= count <= 1000:
            raise ValueError("平均次数必须在1-1000之间")
        self._inst.write(f"SENS:AVER:COUN {count}")

    @classmethod
    def is_nrp_device(cls, idn: str) -> bool:
        """检查是否是NRP系列功率计"""
        parts = idn.split(',')
        return (len(parts) >= 2 and 
                parts[0].upper() == "ROHDE&SCHWARZ" and 
                parts[1].upper().startswith("NRP"))
    
    def initialize_device(self):
        """Initialize device: clear errors, reset, set units and continuous mode"""
        try:
            self._inst.write("*CLS")
            self._inst.write("*RST")
            self._inst.write("UNIT:POW DBM")   # Set units to dBm
            self._inst.write("INIT:CONT ON")   # Continuous measurement mode
            self._inst.write("SENS:AVER:AUTO ON")  # Enable auto-averaging
            self._inst.write("INIT")
            time.sleep(0.5)
        except Exception as e:
            self.log_error(f"Initialization failed: {str(e)}")
    
    def measure_power(self, freq_ghz: float = None) -> float:
        """
        Measure power with optional frequency setting
        
        Args:
            freq_ghz: Frequency in GHz (optional)
            
        Returns:
            Measured power in dBm
        """
        try:
            # Set frequency if provided
            if freq_ghz is not None:
                # Convert GHz to Hz (instrument expects Hz)
                self._inst.write(f"SENS:FREQ {freq_ghz * 1e9}")
            
            # Fetch power measurement
            value = self._inst.query("FETC?").strip()
            return float(value)
        except Exception as e:
            self.log_error(f"Power measurement failed: {str(e)}")
            return float('nan')
    
    def reset(self):
        """Reset instrument to default state"""
        try:
            self._inst.write("*RST")
            self.initialize_device()
        except Exception as e:
            self.log_error(f"Reset failed: {str(e)}")
    
    def close(self):
        """Close instrument connection"""
        try:
            if hasattr(self, '_inst') and self._inst:
                self._inst.close()
        except Exception as e:
            self.log_error(f"Close connection failed: {str(e)}")
    
    def log_error(self, message: str):
        """Log error message (placeholder for actual logging implementation)"""
        print(f"[NRP50S ERROR] {message}")
    
    def __del__(self):
        """Destructor to ensure resources are released"""
        self.close()

    @property
    def model(self) -> str:
        """设备型号（只读）"""
        return self._model
 
    @property
    def serial_number(self) -> str:
        """设备序列号（只读）"""
        return self._serial_number



# Test function when run directly
if __name__ == "__main__":
    sensor = NRP50S(visa_address="USB0::0x0AAD::0x0161::101636::INSTR")
    
    # Set measurement parameters
    freq_ghz = 10.0  # 10 GHz
    print(f"Setting frequency to {freq_ghz} GHz")
    sensor.measure_power(freq_ghz=freq_ghz)
    
    # Perform measurement
    start_time = time.time()
    power = sensor.measure_power()
    elapsed = (time.time() - start_time) * 1000  # ms
    
    print(f"Measured power: {power:.2f} dBm")
    print(f"Measurement time: {elapsed:.2f} ms")
    
    # Close connection
    sensor.close()
