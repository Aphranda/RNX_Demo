# app/instruments/plasg_t8g40g.py
from .interfaces import SignalSource

class PlasgT8G40G(SignalSource):
    def set_cw(self, freq_hz: float, power_dbm: float):
        self._inst.write(f":FREQ:CW {freq_hz}Hz;:POW {power_dbm}dBm")

    def sweep_start(self, start_hz: float, stop_hz: float, step_hz: float):
        self._inst.write(
            f":SWEEP:START {start_hz}Hz;STOP {stop_hz}Hz;STEP {step_hz}Hz"
        )

    def reset(self):
        self._inst.write("*RST;:OUTP OFF")
