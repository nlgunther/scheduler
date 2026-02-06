"""
storage/sqlite_store.py - SQLite Implementation with Optimization support
"""
import sqlite3
import json
import shutil
from contextlib import contextmanager
from .base import StorageStrategy
from ..models import Project, Task, Contact, TaskStatus, ModelEncoder

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (slug TEXT PRIMARY KEY, name TEXT, description TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, project_slug TEXT, title TEXT, assignee TEXT, status TEXT, due_date TEXT, reminder_date TEXT, contact_id TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS task_tags (task_id TEXT, tag TEXT);
CREATE TABLE IF NOT EXISTS contacts (id TEXT PRIMARY KEY, project_slug TEXT, name TEXT, phone TEXT, email TEXT, role TEXT, notes TEXT);
"""

class SqliteStorage(StorageStrategy):
    def __init__(self, base_dir):
        super().__init__(base_dir)
        self.db_path = self.base_dir / "scheduler.db"
        self.sidecar_root = self.base_dir / "projects"
        self._init_db()

    def _init_db(self):
        with self._get_conn() as conn: conn.executescript(SCHEMA_SQL)

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        try: yield conn; conn.commit()
        except: conn.rollback(); raise
        finally: conn.close()

    def optimize(self):
        """Runs VACUUM to reclaim space."""
        with self._get_conn() as conn:
            conn.execute("VACUUM")

    def save_project(self, project: Project) -> None:
        project_dir = self.sidecar_root / project.slug
        project_dir.mkdir(parents=True, exist_ok=True)
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO projects VALUES (?, ?, ?, ?, ?)", 
                         (project.slug, project.name, project.description, project.created_at, project.updated_at))
            conn.execute("DELETE FROM tasks WHERE project_slug = ?", (project.slug,))
            conn.execute("DELETE FROM contacts WHERE project_slug = ?", (project.slug,))
            for task in project.tasks:
                conn.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                             (task.id, project.slug, task.title, task.assignee, task.status.value, task.due_date, task.reminder_date, task.contact_id, task.created_at, task.updated_at))
                if task.tags: conn.executemany("INSERT INTO task_tags VALUES (?, ?)", [(task.id, t) for t in task.tags])
                self._save_sidecar(project_dir, task)
            for c in project.contacts:
                conn.execute("INSERT INTO contacts VALUES (?, ?, ?, ?, ?, ?, ?)", (c.id, project.slug, c.name, c.phone, c.email, c.role, c.notes))

    def load_project(self, slug: str) -> Project:
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
                task = Task(id=tr[0], title=tr[2], assignee=tr[3], status=TaskStatus(tr[4]), due_date=tr[5], reminder_date=tr[6], contact_id=tr[7], created_at=tr[8], updated_at=tr[9], tags=tags_map.get(tr[0], []))
                self._load_sidecar(project_dir, task)
                project.tasks.append(task)
            return project

    def list_projects(self) -> list:
        with self._get_conn() as conn: return [r[0] for r in conn.execute("SELECT slug FROM projects")]

    def delete_project(self, slug: str) -> bool:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM projects WHERE slug = ?", (slug,))
        if (self.sidecar_root / slug).exists(): shutil.rmtree(self.sidecar_root / slug)
        return True

    def rename_project(self, old_slug: str, new_slug: str) -> None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM projects WHERE slug=?", (old_slug,)).fetchone()
            if not row: return
            conn.execute("UPDATE projects SET slug=? WHERE slug=?", (new_slug, old_slug))
            conn.execute("UPDATE tasks SET project_slug=? WHERE project_slug=?", (new_slug, old_slug))
            conn.execute("UPDATE contacts SET project_slug=? WHERE project_slug=?", (new_slug, old_slug))
        old_path = self.sidecar_root / old_slug
        if old_path.exists(): old_path.rename(self.sidecar_root / new_slug)

    def _save_sidecar(self, p_dir, t):
        with open(p_dir / f"{t.id}.json", "w", encoding="utf-8") as f: json.dump({"notes": t.notes, "outcome": t.outcome}, f)

    def _load_sidecar(self, p_dir, t):
        try:
            with open(p_dir / f"{t.id}.json") as f: d = json.load(f); t.notes = d.get("notes"); t.outcome = d.get("outcome")
        except: pass
