#!/usr/bin/env python3
"""
scheduler_config.py - Configuration manager for Smart Scheduler.
"""
import os
import json
import shutil
import sys
import socket
from pathlib import Path
from typing import Optional, Any, Dict
from dataclasses import dataclass, asdict, field
from uuid import uuid4

# --- Internal Helpers (Exposed for Testing) ---

def _resolve(path_str: str) -> Path:
    """Expand user/vars and resolve absolute path."""
    return Path(os.path.expandvars(os.path.expanduser(path_str))).resolve()

def _get_config_dir() -> Path:
    """Return the directory where config.json lives."""
    # Standard: ~/.scheduler
    return Path.home() / ".scheduler"

def _get_default_data_dir() -> Path:
    """Return the default data storage directory."""
    return _get_config_dir()

def _get_default_config_path() -> Path:
    return _get_config_dir() / "config.json"

# --- Data Classes ---

@dataclass
class MoveResult:
    success: bool
    message: str = ""
    error: str = ""
    env_command: str = ""

@dataclass
class ConfigData:
    version: int = 1
    device_id: str = ""
    data_dir: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=lambda: {"storage_engine": "json"})

    def __post_init__(self):
        if not self.device_id:
            self.device_id = f"{socket.gethostname()}-{uuid4().hex[:6]}"
        if self.preferences is None:
            self.preferences = {"storage_engine": "json"}

# --- Main Class ---

class SchedulerConfig:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or _get_default_config_path()
        self.data_dir_source = "default" # Tracking where config came from
        self._data = ConfigData()
        self.load()
        # Re-evaluate source after load
        self._determine_source()

    def _determine_source(self):
        if os.environ.get("SCHEDULER_DATA_DIR"):
            self.data_dir_source = "environment"
        elif self._data.data_dir:
            self.data_dir_source = "config"
        else:
            self.data_dir_source = "default"

    def load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    raw = json.load(f)
                    known_keys = ConfigData.__annotations__.keys()
                    clean = {k: v for k, v in raw.items() if k in known_keys}
                    self._data = ConfigData(**clean)
            except Exception:
                pass 

    def save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(asdict(self._data), f, indent=2)

    @property
    def preferences(self):
        return self._data.preferences

    @property
    def data_dir(self) -> Path:
        # 1. Environment Variable
        env = os.environ.get("SCHEDULER_DATA_DIR")
        if env: return Path(env)
        # 2. Config Setting
        if self._data.data_dir: return Path(self._data.data_dir)
        # 3. Default
        return _get_default_data_dir()

    @property
    def device_id(self):
        return self._data.device_id

    def set_data_dir(self, path: Path):
        self._data.data_dir = str(path)
        self.data_dir_source = "config"

    def set_preference(self, key: str, value: Any):
        self._data.preferences[key] = value

    def reset(self):
        """Reset preferences but keep ID."""
        old_id = self.device_id
        self._data = ConfigData(device_id=old_id)
        self.save()

    def format_info(self) -> str:
        s = ["Configuration Info", "="*20]
        s.append(f"Config File: {self.config_path}")
        s.append(f"Data Dir:    {self.data_dir} ({self.data_dir_source})")
        s.append(f"Device ID:   {self.device_id}")
        s.append(f"Preferences: {json.dumps(self.preferences, indent=2)}")
        return "\n".join(s)

    def get_env_command(self) -> str:
        s = str(self.data_dir)
        if sys.platform == "win32":
            return f'set SCHEDULER_DATA_DIR={s}'
        return f'export SCHEDULER_DATA_DIR="{s}"'

    def move_data_to(self, target: str, keep_copy: bool = False) -> MoveResult:
        src = self.data_dir
        dst = Path(target)
        
        if src.resolve() == dst.resolve():
             return MoveResult(False, error="Source and destination are the same.")
        
        if not src.exists():
             # If source doesn't exist, just point config to new place
             self.set_data_dir(dst)
             self.save()
             dst.mkdir(parents=True, exist_ok=True)
             return MoveResult(True, message=f"Set data directory to {dst}", env_command=self.get_env_command())

        if (dst / "projects").exists() or (dst / "scheduler.db").exists():
             return MoveResult(False, error="Destination already contains scheduler data.")

        try:
            if keep_copy:
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.move(str(src), str(dst))
            
            self.set_data_dir(dst)
            self.save()
            return MoveResult(True, message=f"Moved data to {dst}", env_command=self.get_env_command())
        except Exception as e:
            return MoveResult(False, error=str(e))

# Singleton accessor
_instance = None
def get_config():
    global _instance
    if not _instance:
        _instance = SchedulerConfig()
    return _instance

def get_data_dir():
    return get_config().data_dir


# Exported flag for scheduler.py check
HAS_CONFIG = True
