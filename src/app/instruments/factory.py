# app/instruments/factory.py
import pyvisa
from typing import Dict, Type

class InstrumentFactory:
    _model_map = {
        "NRP50S": "nrp50s.NRP50S",
        "PLASG-T8G40G": "plasg_t8g40g.PlasgT8G40G"
    }

    @classmethod
    def auto_detect(cls) -> Dict[str, str]:
        """返回{资源地址: 设备型号}的映射"""
        rm = pyvisa.ResourceManager()
        return {
            res: cls._identify_model(rm.open_resource(res))
            for res in rm.list_resources()
        }

    @classmethod
    def create(cls, visa_address: str) -> VisaInstrument:
        model = cls._identify_model(visa_address)
        module, class_name = cls._model_map[model].split('.')
        module = __import__(f"app.instruments.{module}", fromlist=[class_name])
        return getattr(module, class_name)(visa_address)
