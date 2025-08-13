# app/instruments/factory.py
import pyvisa
import json
import sys
from pathlib import Path
from typing import Dict, Optional
from .interfaces import SignalSource, PowerSensor
from .plasg_signal_source import PlasgT8G40G
from .nrp50s import NRP50S

class InstrumentFactory:
    _rm = None  # 类变量共享ResourceManager
    _config = None  # 类变量共享配置

    @classmethod
    def _get_resource_manager(cls):
        """获取共享的ResourceManager实例"""
        if cls._rm is None:
            cls._rm = pyvisa.ResourceManager()
        return cls._rm

    @classmethod
    def _load_instrument_config(cls) -> Dict:
        """加载仪器配置(单例模式)"""
        if cls._config is None:
            try:
                config_path = Path(__file__).parent.parent.parent / "config" / "instrument_commands.json"
                with open(config_path, 'r', encoding='utf-8') as f:
                    cls._config = json.load(f)
            except Exception as e:
                print(f"加载仪器配置失败: {str(e)}")
                cls._config = {}
        return cls._config

    @classmethod
    def _identify_instrument(cls, visa_address: str) -> Optional[Dict]:
        """识别仪器类型并返回详细信息"""
        rm = cls._get_resource_manager()
        inst = None
        try:
            inst = rm.open_resource(visa_address)
            inst.timeout = 1000  # 设置较短的超时用于识别
            idn = inst.query("*IDN?").strip().upper()
            
            # R&S NRP功率计的标准IDN格式
            if idn.startswith("ROHDE&SCHWARZ,NRP"):
                model = idn.split(',')[1]
                return {
                    'type': 'power_meter',
                    'model': model,
                    'idn': idn,
                    'config': cls._load_instrument_config().get(model, {})
                }
            elif "PLASG" in idn:
                model = "PLASG-T8G40G"  # 假设PLASG型号固定
                return {
                    'type': 'signal_source',
                    'model': model,
                    'idn': idn,
                    'config': cls._load_instrument_config().get(model, {})
                }
            return None
        except Exception as e:
            print(f"仪器识别失败: {str(e)}")
            return None
        finally:
            if inst is not None:
                inst.close()

    @classmethod
    def create_signal_source(cls, visa_address: str, instrument_name: str = None) -> Optional[SignalSource]:
        """创建信号源实例"""
        info = cls._identify_instrument(visa_address)
        if not info or info['type'] != 'signal_source':
            return None
            
        # 优先使用传入的仪表名称判断
        if instrument_name and "PLASG" in instrument_name.upper():
            return PlasgT8G40G(visa_address, config=info.get('config', {}))
        elif info and "PLASG" in info.get('idn', ''):
            return PlasgT8G40G(visa_address, config=info.get('config', {}))
        return None


    @classmethod
    def create_power_meter(cls, visa_address: str, instrument_name: str = None) -> Optional[PowerSensor]:
        """创建功率计实例"""
        info = cls._identify_instrument(visa_address)
        if not info or info['type'] != 'power_meter':
            return None
            
        # 优先使用传入的仪表名称判断
        if instrument_name and "NRP" in instrument_name.upper():
            return NRP50S(visa_address, config=info.get('config', {}))
        elif info and "NRP" in info.get('model', ''):
            return NRP50S(visa_address, config=info.get('config', {}))
        return None


    @classmethod
    def get_available_instruments(cls) -> Dict[str, str]:
        """获取所有可用的VISA仪器"""
        rm = cls._get_resource_manager()
        resources = {}
        for addr in rm.list_resources():
            info = cls._identify_instrument(addr)
            if info:
                resources[addr] = f"{info['model']} ({info['type']})"
            else:
                resources[addr] = f"Unknown Instrument ({addr})"
        return resources

    @classmethod
    def cleanup(cls):
        """清理资源管理器"""
        if cls._rm is not None:
            cls._rm.close()
            cls._rm = None
        cls._config = None  # 同时清理配置缓存

# 测试代码
# 在文件开头添加以下代码，确保在直接运行时能正确导入
if __name__ == "__main__":
    try:
        # 示例：列出所有可用仪器
        print("可用仪器:")
        instruments = InstrumentFactory.get_available_instruments()
        for addr, desc in instruments.items():
            print(f"- {addr}: {desc}")

        # 示例：创建功率计实例
        if instruments:
            first_addr = next(iter(instruments))
            print(f"\n尝试连接第一个仪器: {first_addr}")
            
            if "NRP" in instruments[first_addr]:
                pm = InstrumentFactory.create_power_meter(first_addr)
                if pm:
                    print(f"成功创建功率计实例: {pm.model}")
                    print(f"IDN: {pm.idn}")
            elif "PLASG" in instruments[first_addr]:
                sg = InstrumentFactory.create_signal_source(first_addr)
                if sg:
                    print(f"成功创建信号源实例: {sg.model}")
                    print(f"IDN: {sg.idn}")
    finally:
        InstrumentFactory.cleanup()
