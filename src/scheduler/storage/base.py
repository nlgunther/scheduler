"""
storage/base.py - Abstract Base Class for Storage
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
from ..models import Project

class StorageStrategy(ABC):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir = self.base_dir / "projects"
        self.projects_dir.mkdir(exist_ok=True)

    @abstractmethod
    def save_project(self, project: Project) -> None: ...
    @abstractmethod
    def load_project(self, slug: str) -> Optional[Project]: ...
    @abstractmethod
    def list_projects(self) -> List[str]: ...
    @abstractmethod
    def delete_project(self, slug: str) -> bool: ...
    @abstractmethod
    def rename_project(self, old_slug: str, new_slug: str) -> None: ...
    
    def load_all_projects(self) -> List[Project]:
        return [p for s in self.list_projects() if (p := self.load_project(s))]

    def save_reminders(self, content: str) -> Path:
        path = self.base_dir / "reminders.md"
        path.write_text(content, encoding="utf-8")
        return path
    
    def optimize(self):
        """Optional maintenance method (e.g. VACUUM for SQL)"""
        pass
