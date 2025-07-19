# app/instruments/nrp50s.py
import pyvisa
import time
from .interfaces import PowerSensor

class NRP50S(PowerSensor):
    def __init__(self, visa_address: str, timeout: int = 5000):
        super().__init__(visa_address)
        self.rm = pyvisa.ResourceManager()
        self.instrument = self.rm.open_resource(visa_address)
        self.instrument.timeout = timeout
        self.initialize_device()
    
    def initialize_device(self):
        """Initialize device: clear errors, reset, set units and continuous mode"""
        try:
            self.instrument.write("*CLS")
            self.instrument.write("*RST")
            self.instrument.write("UNIT:POW DBM")   # Set units to dBm
            self.instrument.write("INIT:CONT ON")   # Continuous measurement mode
            self.instrument.write("SENS:AVER:AUTO ON")  # Enable auto-averaging
            self.instrument.write("INIT")
            time.sleep(0.5)
        except Exception as e:
            self.log_error(f"Initialization failed: {str(e)}")
    
    def measure_power(self, freq_hz: float = None) -> float:
        """
        Measure power with optional frequency setting
        
        Args:
            freq_hz: Frequency in Hz (optional)
            
        Returns:
            Measured power in dBm
        """
        try:
            # Set frequency if provided
            if freq_hz is not None:
                self.instrument.write(f"SENS:FREQ {freq_hz}")
            
            # Fetch power measurement
            value = self.instrument.query("FETC?").strip()
            return float(value)
        except Exception as e:
            self.log_error(f"Power measurement failed: {str(e)}")
            return float('nan')
    
    def reset(self):
        """Reset instrument to default state"""
        try:
            self.instrument.write("*RST")
            self.initialize_device()
        except Exception as e:
            self.log_error(f"Reset failed: {str(e)}")
    
    def close(self):
        """Close instrument connection"""
        try:
            if self.instrument:
                self.instrument.close()
            if self.rm:
                self.rm.close()
        except Exception as e:
            self.log_error(f"Close connection failed: {str(e)}")
    
    def log_error(self, message: str):
        """Log error message (placeholder for actual logging implementation)"""
        print(f"[NRP50S ERROR] {message}")
    
    def __del__(self):
        """Destructor to ensure resources are released"""
        self.close()


# Test function when run directly
if __name__ == "__main__":
    sensor = NRP50S(visa_address="USB0::0x0AAD::0x0161::101636::INSTR")
    
    # Set measurement parameters
    freq_mhz = 1000
    print(f"Setting frequency to {freq_mhz} MHz")
    sensor.measure_power(freq_hz=freq_mhz * 1e6)  # Convert MHz to Hz
    
    # Perform measurement
    start_time = time.time()
    power = sensor.measure_power()
    elapsed = (time.time() - start_time) * 1000  # ms
    
    print(f"Measured power: {power:.2f} dBm")
    print(f"Measurement time: {elapsed:.2f} ms")
    
    # Close connection
    sensor.close()
