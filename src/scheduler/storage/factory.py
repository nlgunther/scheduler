"""
storage/factory.py
"""
from pathlib import Path
from typing import Optional
from .base import StorageStrategy
from .json_store import JsonFileStorage
from .sqlite_store import SqliteStorage

def get_storage_engine(base_dir: Path, engine_type: str = "json") -> StorageStrategy:
    if engine_type == "sqlite":
        return SqliteStorage(base_dir)
    return JsonFileStorage(base_dir)
