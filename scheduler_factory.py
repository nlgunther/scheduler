#!/usr/bin/env python3
"""
scheduler_factory.py - Configuration logic for storage selection.
"""
from pathlib import Path
from typing import Optional
from scheduler_storage import StorageStrategy

# NOTE: We do NOT import scheduler or scheduler_sqlite at the top level
# to avoid circular dependency loops during startup.

def get_storage_engine(base_dir: Optional[Path] = None, engine_type: str = "json") -> StorageStrategy:
    """Factory to return the configured storage backend."""
    
    # 1. Lazy import JsonFileStorage to break the cycle (scheduler -> factory -> scheduler)
    from scheduler import JsonFileStorage
    
    if engine_type == "sqlite":
        # 2. Lazy import SqliteStorage to avoid loading it before dependencies are ready
        try:
            from scheduler_sqlite import SqliteStorage
            return SqliteStorage(base_dir)
        except ImportError:
            print("Warning: SQLite engine requested but scheduler_sqlite.py not found. Falling back to JSON.")
            return JsonFileStorage(base_dir)
    
    return JsonFileStorage(base_dir)
