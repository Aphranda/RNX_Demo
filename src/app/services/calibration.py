# app/services/calibration.py
import time
from typing import Callable, Dict
from dataclasses import dataclass
from app.core.threads import WorkerThread
from app.instruments.factory import InstrumentFactory

@dataclass
class CalibrationPoint:
    freq_hz: float
    expected_power: float
    measured_power: float
    delta: float

class CalibrationService:
    def __init__(self):
        self._thread = None
        self._running = False

    def start_async(self, 
                   params: Dict,
                   progress_callback: Callable,
                   finished_callback: Callable):
        """启动异步校准线程"""
        self._thread = WorkerThread(
            task=lambda: self._calibrate(params, progress_callback),
            on_finished=lambda: finished_callback(True, "校准完成"),
            on_error=lambda e: finished_callback(False, str(e))
        )
        self._thread.start()

    def _calibrate(self, params: Dict, progress_cb: Callable):
        """实际校准流程"""
        steps = self._calculate_steps(params)
        results = []
        
        with InstrumentFactory.create_power_meter() as pm, \
             InstrumentFactory.create_signal_gen() as sg:
            
            for i, freq in enumerate(steps):
                if not self._running: 
                    break
                
                # 设置信号源并测量
                sg.set_cw(freq, params['ref_power'])
                time.sleep(0.1)  # 稳定时间
                measured = pm.measure_power(freq)
                
                # 记录结果
                point = CalibrationPoint(
                    freq_hz=freq,
                    expected_power=params['ref_power'],
                    measured_power=measured,
                    delta=measured - params['ref_power']
                )
                results.append(point)
                
                # 更新进度
                progress = int((i + 1) / len(steps) * 100)
                progress_cb(progress, f"正在校准 {freq/1e9:.2f}GHz...")
        
        return results

    def _calculate_steps(self, params: Dict) -> list:
        """生成频率步进序列"""
        return [
            params['start_hz'] + i * params['step_hz']
            for i in range(int((params['stop_hz'] - params['start_hz']) / params['step_hz']) + 1)
        ]
