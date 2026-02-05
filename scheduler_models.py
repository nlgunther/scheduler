"""
scheduler_models.py - Data definitions for Smart Scheduler.
"""
import json
from dataclasses import dataclass, field
from typing import List, Optional, Set
from enum import Enum
from datetime import date
from uuid import uuid4

class TaskStatus(Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    DONE = "done"
    CANCELLED = "cancelled"

    @property
    def icon(self):
        return {
            "todo": "○", "in_progress": "▶", "waiting": "⏳",
            "done": "✓", "cancelled": "✗"
        }.get(self.value, "?")

class ModelEncoder(json.JSONEncoder):
    """
    Robust JSON Encoder that handles:
    1. Enums (TaskStatus)
    2. Sets (Tags)
    3. Objects (Project, Task, Contact) via __dict__
    """
    def default(self, obj):
        if isinstance(obj, TaskStatus):
            return obj.value
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)

@dataclass
class Contact:
    id: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def create(cls, name: str, phone: str = None, role: str = None, email: str = None):
        return cls(id=f"c{uuid4().hex[:5]}", name=name, phone=phone, role=role, email=email)

    def matches_search(self, query: str) -> bool:
        return query.lower() in self.name.lower()

@dataclass
class Task:
    id: str
    title: str
    assignee: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    due_date: Optional[str] = None
    reminder_date: Optional[str] = None
    contact_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    outcome: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_overdue(self) -> bool:
        if self.status in (TaskStatus.DONE, TaskStatus.CANCELLED) or not self.due_date:
            return False
        try:
            return date.fromisoformat(self.due_date) < date.today()
        except ValueError:
            return False

    @property
    def is_active(self) -> bool:
        return self.status not in (TaskStatus.DONE, TaskStatus.CANCELLED)

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def matches_search(self, query: str) -> bool:
        q = query.lower()
        if q in self.title.lower(): return True
        if self.assignee and q in self.assignee.lower(): return True
        return False

    @classmethod
    def create(cls, title: str, assignee: str = None, due_date: str = None, tags: List[str] = None):
        from datetime import datetime
        now = datetime.now().isoformat()
        return cls(
            id=f"t{uuid4().hex[:5]}",
            title=title,
            assignee=assignee,
            due_date=due_date,
            tags=tags or [],
            created_at=now,
            updated_at=now
        )

@dataclass
class Project:
    slug: str
    name: str
    description: str = ""
    tasks: List[Task] = field(default_factory=list)
    contacts: List[Contact] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    @property
    def active_tasks(self) -> List[Task]:
        return [t for t in self.tasks if t.is_active]

    @property
    def all_tags(self) -> Set[str]:
        tags = set()
        for t in self.tasks:
            tags.update(t.tags)
        return tags

# Serialization Helpers
def task_from_dict(data: dict) -> Task:
    data = data.copy()
    if "status" in data and isinstance(data["status"], str):
        try:
            data["status"] = TaskStatus(data["status"])
        except ValueError:
            data["status"] = TaskStatus.TODO
    return Task(**{k: v for k, v in data.items() if k in Task.__annotations__})

def contact_from_dict(data: dict) -> Contact:
    return Contact(**{k: v for k, v in data.items() if k in Contact.__annotations__})

def project_from_dict(data: dict) -> Project:
    p_data = {k: v for k, v in data.items() if k in Project.__annotations__}
    p = Project(**p_data)
    p.tasks = [task_from_dict(t) for t in data.get("tasks", [])]
    p.contacts = [contact_from_dict(c) for c in data.get("contacts", [])]
    return p
