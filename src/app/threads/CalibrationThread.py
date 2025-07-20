# app/services/calibration.py
import time
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from app.core.exceptions.instrument import InstrumentCommandError
from app.instruments.interfaces import SignalSource, PowerSensor

@dataclass
class CalibrationPoint:
    freq_hz: float
    expected_power: float
    measured_power: float
    delta: float
    timestamp: str

class CalibrationThread(QThread):
    """解耦后的校准线程类"""
    
    progress_updated = pyqtSignal(int, str)
    point_completed = pyqtSignal(CalibrationPoint)
    calibration_finished = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, 
                 signal_source: SignalSource,
                 power_meter: PowerSensor,
                 freq_list: List[float],
                 ref_power: float,
                 dwell_time: float = 0.2,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self.signal_source = signal_source
        self.power_meter = power_meter
        self.freq_list = freq_list
        self.ref_power = ref_power
        self.dwell_time = dwell_time
        self._is_running = False
        self._results = []
        
    def run(self):
        """执行校准流程"""
        self._is_running = True
        self._results = []
        total_points = len(self.freq_list)
        print(self.freq_list, total_points)
        # try:
        self._initialize_instruments()
        
        for idx, freq in enumerate(self.freq_list):
            if not self._is_running:
                break
                
            progress = int((idx + 1) / total_points * 100)
            self.progress_updated.emit(progress, f"正在校准 {freq/1e9:.3f}GHz...")
            
            point = self._calibrate_single_point(freq)
            self._results.append(point)
            self.point_completed.emit(point)
            
        if self._is_running:
            self.progress_updated.emit(100, "校准完成")
            self.calibration_finished.emit(self._results)
        else:
            self.progress_updated.emit(0, "校准已中止")
                
        # except Exception as e:
        #     self.error_occurred.emit(f"校准失败: {str(e)}")
        #     self.progress_updated.emit(0, f"错误: {str(e)}")
        # finally:
        #     self._cleanup_instruments()
        #     self._is_running = False
            
    def stop(self):
        """安全停止校准"""
        self._is_running = False
        
    def _initialize_instruments(self):
        """通过接口方法初始化仪器"""
        try:
            self.signal_source.reset()
            self.power_meter.reset()
            self.power_meter.set_frequency_correction(0.0)
            self.power_meter.set_averaging(10)
            self.signal_source.set_output(False)
            self.signal_source.set_power(self.ref_power)
        except Exception as e:
            raise InstrumentCommandError(
                device=f"{self.signal_source.__class__.__name__}/{self.power_meter.__class__.__name__}",
                message=f"仪器初始化失败: {str(e)}",
                command="reset/set_frequency_correction/set_averaging/set_output/set_power"
            )
            
    def _calibrate_single_point(self, freq_hz: float) -> CalibrationPoint:
        """通过接口方法执行单点校准"""
        try:
            self.signal_source.set_frequency(freq_hz)
            self.signal_source.set_output(True)
            time.sleep(self.dwell_time)
            
            measured_power = self._measure_power(freq_hz)
            
            self.signal_source.set_output(False)
            
            return CalibrationPoint(
                freq_hz=freq_hz,
                expected_power=self.ref_power,
                measured_power=measured_power,
                delta=measured_power - self.ref_power,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
            )
        except Exception as e:
            self.signal_source.set_output(False)
            raise InstrumentCommandError(
                device=self.signal_source.__class__.__name__,
                message=f"频率 {freq_hz/1e9:.3f}GHz 校准失败: {str(e)}",
                command=f"set_frequency/set_output"
            )
            
    def _measure_power(self, freq_hz: float) -> float:
        """通过接口方法测量功率"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self.power_meter.measure_power(freq_hz)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.1)
                
    def _cleanup_instruments(self):
        """清理仪器状态"""
        try:
            self.signal_source.set_output(False)
            self.signal_source.reset()
        except:
            pass
            
        try:
            self.power_meter.reset()
        except:
            pass

class CalibrationService:
    """校准服务管理类"""
    
    def __init__(self):
        self.thread = None
        
    def start_calibration(self,
                        signal_source: SignalSource,
                        power_meter: PowerSensor,
                        freq_list: List[float],
                        ref_power: float,
                        progress_callback: Callable,
                        point_callback: Callable,
                        finished_callback: Callable,
                        error_callback: Callable):
        """
        启动校准流程
        Args:
            signal_source: 信号源实例
            power_meter: 功率计实例
            freq_list: 频率列表(Hz)
            ref_power: 参考功率(dBm)
            progress_callback: 进度回调(progress, message)
            point_callback: 单点完成回调(CalibrationPoint)
            finished_callback: 完成回调(results)
            error_callback: 错误回调(error_message)
        """
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait()
            
        self.thread = CalibrationThread(
            signal_source=signal_source,
            power_meter=power_meter,
            freq_list=freq_list,
            ref_power=ref_power
        )
        
        # 连接信号
        self.thread.progress_updated.connect(progress_callback)
        self.thread.point_completed.connect(point_callback)
        self.thread.calibration_finished.connect(finished_callback)
        self.thread.error_occurred.connect(error_callback)
        
        self.thread.start()
        
    def stop_calibration(self):
        """停止校准流程"""
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait()
