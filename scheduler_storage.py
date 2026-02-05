"""
scheduler_storage.py - Storage engines (JSON & SQLite).
"""
import json
import shutil
import sqlite3
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

# IMPORTS FIXED: Added ModelEncoder here
from scheduler_models import (
    Project, Task, Contact, TaskStatus, ModelEncoder,
    task_from_dict, contact_from_dict, project_from_dict
)

class StorageStrategy(ABC):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir = self.base_dir / "projects"
        self.projects_dir.mkdir(exist_ok=True)
        self.exports_dir = self.base_dir / "exports"
        self.exports_dir.mkdir(exist_ok=True)

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

# --- JSON Implementation ---
class JsonFileStorage(StorageStrategy):
    def save_project(self, project: Project) -> None:
        path = self.projects_dir / f"{project.slug}.json"
        with open(path, "w", encoding="utf-8") as f:
            # FIXED: Using ModelEncoder without lambda fallback
            json.dump(project, f, cls=ModelEncoder, indent=2)

    def load_project(self, slug: str) -> Optional[Project]:
        path = self.projects_dir / f"{slug}.json"
        if not path.exists(): return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return project_from_dict(json.load(f))
        except (json.JSONDecodeError, IOError):
            return None

    def list_projects(self) -> List[str]:
        return [f.stem for f in self.projects_dir.glob("*.json")]

    def delete_project(self, slug: str) -> bool:
        path = self.projects_dir / f"{slug}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def rename_project(self, old_slug: str, new_slug: str) -> None:
        old_path = self.projects_dir / f"{old_slug}.json"
        new_path = self.projects_dir / f"{new_slug}.json"
        if old_path.exists():
            old_path.rename(new_path)
            proj = self.load_project(new_slug)
            if proj:
                proj.slug = new_slug
                self.save_project(proj)

    def load_project_raw(self, slug: str) -> Optional[dict]:
        path = self.projects_dir / f"{slug}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None
        
    def save_project_raw(self, slug: str, data: dict) -> None:
        path = self.projects_dir / f"{slug}.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

# --- SQLite Implementation ---
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_slug TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT,
    status TEXT,
    due_date TEXT,
    reminder_date TEXT,
    contact_id TEXT,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY(project_slug) REFERENCES projects(slug) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS task_tags (
    task_id TEXT,
    tag TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS contacts (
    id TEXT PRIMARY KEY,
    project_slug TEXT NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    role TEXT,
    notes TEXT,
    FOREIGN KEY(project_slug) REFERENCES projects(slug) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_slug);
CREATE INDEX IF NOT EXISTS idx_tags_task ON task_tags(task_id);
"""

class SqliteStorage(StorageStrategy):
    def __init__(self, base_dir: Path):
        super().__init__(base_dir)
        self.db_path = self.base_dir / "scheduler.db"
        self.sidecar_root = self.base_dir / "projects"
        self._init_db()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript(SCHEMA_SQL)

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_project(self, project: Project) -> None:
        project_dir = self.sidecar_root / project.slug
        project_dir.mkdir(parents=True, exist_ok=True)

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO projects (slug, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    updated_at=excluded.updated_at
            """, (project.slug, project.name, project.description, project.created_at, project.updated_at))

            conn.execute("DELETE FROM tasks WHERE project_slug = ?", (project.slug,))
            conn.execute("DELETE FROM contacts WHERE project_slug = ?", (project.slug,))
            
            for task in project.tasks:
                conn.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                             (task.id, project.slug, task.title, task.assignee, task.status.value, 
                              task.due_date, task.reminder_date, task.contact_id, task.created_at, task.updated_at))
                if task.tags:
                    conn.executemany("INSERT INTO task_tags VALUES (?, ?)", [(task.id, t) for t in task.tags])
                self._save_sidecar(project_dir, task)

            for c in project.contacts:
                conn.execute("INSERT INTO contacts VALUES (?, ?, ?, ?, ?, ?, ?)", 
                             (c.id, project.slug, c.name, c.phone, c.email, c.role, c.notes))

    def load_project(self, slug: str) -> Optional[Project]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
            if not row: return None
            
            project = Project(slug=row[0], name=row[1], description=row[2] or "", created_at=row[3], updated_at=row[4])
            
            for cr in conn.execute("SELECT * FROM contacts WHERE project_slug = ?", (slug,)):
                project.contacts.append(Contact(id=cr[0], name=cr[2], phone=cr[3], email=cr[4], role=cr[5], notes=cr[6]))

            tags_map = {}
            for tid, tag in conn.execute("SELECT task_id, tag FROM task_tags WHERE task_id IN (SELECT id FROM tasks WHERE project_slug=?)", (slug,)):
                tags_map.setdefault(tid, []).append(tag)

            project_dir = self.sidecar_root / slug
            for tr in conn.execute("SELECT * FROM tasks WHERE project_slug = ?", (slug,)):
                task = Task(id=tr[0], title=tr[2], assignee=tr[3], status=TaskStatus(tr[4]), 
                            due_date=tr[5], reminder_date=tr[6], contact_id=tr[7], created_at=tr[8], updated_at=tr[9], 
                            tags=tags_map.get(tr[0], []), notes=None, outcome=None)
                self._load_sidecar(project_dir, task)
                project.tasks.append(task)
            return project

    def delete_project(self, slug: str) -> bool:
        with self._get_conn() as conn:
            if not conn.execute("SELECT 1 FROM projects WHERE slug = ?", (slug,)).fetchone(): return False
            conn.execute("DELETE FROM projects WHERE slug = ?", (slug,))
        if (self.sidecar_root / slug).exists(): shutil.rmtree(self.sidecar_root / slug)
        return True

    def rename_project(self, old_slug: str, new_slug: str) -> None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT name, description, created_at, updated_at FROM projects WHERE slug = ?", (old_slug,)).fetchone()
            if not row: raise ValueError(f"Project '{old_slug}' not found")
            conn.execute("INSERT INTO projects (slug, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                         (new_slug, row[0], row[1], row[2], row[3]))
            conn.execute("UPDATE tasks SET project_slug = ? WHERE project_slug = ?", (new_slug, old_slug))
            conn.execute("UPDATE contacts SET project_slug = ? WHERE project_slug = ?", (new_slug, old_slug))
            conn.execute("DELETE FROM projects WHERE slug = ?", (old_slug,))
            
        old_path = self.sidecar_root / old_slug
        new_path = self.sidecar_root / new_slug
        if old_path.exists(): old_path.rename(new_path)

    def list_projects(self) -> List[str]:
        with self._get_conn() as conn:
            return [r[0] for r in conn.execute("SELECT slug FROM projects")]

    def _save_sidecar(self, project_dir: Path, task: Task):
        with open(project_dir / f"{task.id}.json", "w", encoding="utf-8") as f:
            json.dump({"notes": task.notes, "outcome": task.outcome}, f, indent=2, ensure_ascii=False)

    def _load_sidecar(self, project_dir: Path, task: Task):
        path = project_dir / f"{task.id}.json"
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                    task.notes, task.outcome = data.get("notes"), data.get("outcome")
            except (json.JSONDecodeError, IOError): pass

    def load_project_raw(self, slug: str) -> Optional[Dict[str, Any]]:
        p = self.load_project(slug)
        # Using ModelEncoder here too for consistency
        return json.loads(json.dumps(p, cls=ModelEncoder)) if p else None

    def save_project_raw(self, slug: str, data: Dict[str, Any]) -> None:
        p = project_from_dict(data)
        self.save_project(p)

def get_storage_engine(base_dir: Optional[Path] = None, engine_type: str = "json") -> StorageStrategy:
    if base_dir is None:
        from scheduler_config import get_data_dir
        base_dir = get_data_dir()
    if engine_type == "sqlite":
        return SqliteStorage(base_dir)
    return JsonFileStorage(base_dir)
