"""
services/maintenance_service.py
Handles Backups, Restores, and DB Optimization.
"""
import shutil
import zipfile
import os
from pathlib import Path
from datetime import datetime
from ..storage.base import StorageStrategy

class MaintenanceService:
    def __init__(self, storage: StorageStrategy):
        self.storage = storage
        self.data_dir = storage.base_dir

    def backup(self, backup_name: str = None, compress: bool = False) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = backup_name or f"schedule_{timestamp}.bkp"
        
        target_path = Path(name).resolve()
        
        if compress:
            if not str(target_path).endswith(".zip"):
                target_path = target_path.with_suffix(".zip")
            
            with zipfile.ZipFile(target_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(self.data_dir):
                    for file in files:
                        abs_path = Path(root) / file
                        if file.endswith(".lock") or abs_path == target_path: continue
                        rel_path = abs_path.relative_to(self.data_dir)
                        zf.write(abs_path, rel_path)
            return target_path

        else:
            if target_path.exists():
                shutil.rmtree(target_path)
            shutil.copytree(self.data_dir, target_path, ignore=shutil.ignore_patterns("*.lock", "*.bkp", "*.zip"))
            return target_path

    def restore(self, source_path: str) -> None:
        src = Path(source_path).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Backup source '{src}' not found.")

        # FIX: Added microseconds (%f) to ensure unique folder names during fast tests
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_current = self.data_dir.parent / f".scheduler_pre_restore_{timestamp}"
        
        if self.data_dir.exists():
            self.data_dir.rename(backup_current)
        
        self.data_dir.mkdir(parents=True, exist_ok=True)

        try:
            if src.is_file() and (src.suffix == ".zip"):
                shutil.unpack_archive(str(src), str(self.data_dir))
            elif src.is_dir():
                shutil.copytree(src, self.data_dir, dirs_exist_ok=True)
            else:
                try:
                    shutil.unpack_archive(str(src), str(self.data_dir))
                except:
                    raise ValueError("Unsupported backup format.")
        except Exception as e:
            if self.data_dir.exists(): shutil.rmtree(self.data_dir)
            if backup_current.exists(): backup_current.rename(self.data_dir)
            raise e
            
    def optimize_database(self):
        self.storage.optimize()
