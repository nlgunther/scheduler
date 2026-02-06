"""
config.py - Configuration management
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional

@dataclass
class ConfigData:
    data_dir: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=lambda: {"storage_engine": "json"})

class SchedulerConfig:
    def __init__(self):
        # The config file ALWAYS lives in ~/.scheduler/config.json
        self.home_dir = Path.home() / ".scheduler"
        self.config_path = self.home_dir / "config.json"
        self._data = ConfigData()
        self.load()

    def load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    # Filter keys to ensure valid ConfigData
                    raw = json.load(f)
                    valid_keys = ConfigData.__annotations__.keys()
                    clean = {k: v for k, v in raw.items() if k in valid_keys}
                    self._data = ConfigData(**clean)
            except: pass

    def save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(asdict(self._data), f, indent=2)

    @property
    def preferences(self): return self._data.preferences
    
    @property
    def data_dir(self) -> Path:
        # 1. Environment Variable (Highest Priority)
        env = os.environ.get("SCHEDULER_DATA_DIR")
        if env: return Path(env)
        
        # 2. Config File Setting
        if self._data.data_dir: return Path(self._data.data_dir)
        
        # 3. Default (~/.scheduler)
        return self.home_dir

    def set_data_dir(self, path: str):
        self._data.data_dir = str(path)
        self.save()

    def set_preference(self, key: str, value: Any):
        self._data.preferences[key] = value
        self.save()

_instance = None
def get_config():
    global _instance
    if not _instance: _instance = SchedulerConfig()
    return _instance
