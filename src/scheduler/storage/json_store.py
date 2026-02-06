"""
storage/json_store.py - JSON Implementation
"""
import json
from .base import StorageStrategy
from ..models import Project, ModelEncoder, project_from_dict

class JsonFileStorage(StorageStrategy):
    def save_project(self, project: Project) -> None:
        path = self.projects_dir / f"{project.slug}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(project, f, cls=ModelEncoder, indent=2)

    def load_project(self, slug: str) -> None:
        path = self.projects_dir / f"{slug}.json"
        if not path.exists(): return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return project_from_dict(json.load(f))
        except: return None

    def list_projects(self) -> list:
        return [f.stem for f in self.projects_dir.glob("*.json")]

    def delete_project(self, slug: str) -> bool:
        path = self.projects_dir / f"{slug}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def rename_project(self, old_slug: str, new_slug: str) -> None:
        old_path = self.projects_dir / f"{old_slug}.json"
        if old_path.exists():
            proj = self.load_project(old_slug)
            if proj:
                proj.slug = new_slug
                self.save_project(proj)
                old_path.unlink()
