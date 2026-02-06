"""
services/task_service.py
"""
from typing import List, Optional
from datetime import datetime, timedelta
import re
from uuid import uuid4
from ..models import Task, Project, Contact, TaskStatus
from ..storage.base import StorageStrategy

# --- Helper: Date Parsing ---
def parse_date(date_str: Optional[str]) -> Optional[str]:
    """Parses natural language dates (e.g., 'tomorrow', '+3')."""
    if not date_str: return None
    date_str = str(date_str).strip().lower()
    today = datetime.now().date()
    
    if date_str == "today": return today.isoformat()
    if date_str == "tomorrow": return (today + timedelta(days=1)).isoformat()
    if date_str == "yesterday": return (today - timedelta(days=1)).isoformat()
    
    # +N days
    if date_str.startswith("+") and date_str[1:].isdigit():
        return (today + timedelta(days=int(date_str))).isoformat()
    
    # Weekdays
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if date_str in weekdays:
        target_idx = weekdays.index(date_str)
        current_idx = today.weekday()
        days_ahead = (target_idx - current_idx) % 7
        if days_ahead == 0: days_ahead = 7
        return (today + timedelta(days=days_ahead)).isoformat()
        
    # Standard format check
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        pass
        
    # US format
    try:
        dt = datetime.strptime(date_str, "%m/%d/%Y")
        return dt.date().isoformat()
    except ValueError:
        pass

    return None

class TaskService:
    def __init__(self, storage: StorageStrategy):
        self.storage = storage

    def get_summary(self) -> dict:
        projects = self.storage.load_all_projects()
        return { "total_projects": len(projects), "total_active": sum(len(p.active_tasks) for p in projects) }

    def create_project(self, slug: str, name: str) -> Project:
        if self.storage.load_project(slug): raise ValueError("Slug taken")
        p = Project(slug, name)
        self.storage.save_project(p)
        return p

    def update_project(self, slug: str, name: str = None, desc: str = None) -> Project:
        p = self.storage.load_project(slug)
        if not p: raise ValueError("Project not found")
        if name: p.name = name
        if desc: p.description = desc
        self.storage.save_project(p)
        return p

    def rename_project(self, old: str, new: str) -> str:
        self.storage.rename_project(old, new)
        return new

    def delete_project(self, slug: str) -> bool:
        """Deletes a project and all its tasks/contacts."""
        return self.storage.delete_project(slug)

    def add_task(self, slug: str, title: str, assignee: str=None, due: str=None, tags: list=None, contact: str=None, notes: str=None) -> Task:
        p = self.storage.load_project(slug)
        if not p: raise ValueError("Project not found")
        
        parsed_due = parse_date(due) if due else None
        
        t = Task.create(title, assignee, parsed_due, tags)
        if notes: t.notes = notes
        if contact: t.contact_id = contact 
        p.tasks.append(t)
        self.storage.save_project(p)
        return t

    def update_task(self, slug: str, task_id: str, **kwargs) -> Task:
        p = self.storage.load_project(slug)
        if not p: raise ValueError("Project not found")
        t = next((x for x in p.tasks if x.id.startswith(task_id)), None)
        if not t: raise ValueError("Task not found")
        
        if "title" in kwargs: t.title = kwargs["title"]
        if "due_date" in kwargs: t.due_date = parse_date(kwargs["due_date"])
        if "assignee" in kwargs: t.assignee = kwargs["assignee"]
        if "notes" in kwargs: t.notes = kwargs["notes"]
        if "status" in kwargs:
            val = kwargs["status"]
            if isinstance(val, str):
                try: t.status = TaskStatus(val)
                except: pass 
        if "tags" in kwargs: t.tags = kwargs["tags"]
        
        self.storage.save_project(p)
        return t

    def add_contact(self, slug: str, name: str, role: str=None, note: str=None) -> Contact:
        p = self.storage.load_project(slug)
        if not p: raise ValueError("Project not found")
        c = Contact.create(name, role=role, notes=note)
        p.contacts.append(c)
        self.storage.save_project(p)
        return c
