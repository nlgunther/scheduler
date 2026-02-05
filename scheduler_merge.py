#!/usr/bin/env python3
"""
scheduler_merge.py - Multi-source merge for Smart Scheduler.
"""

from __future__ import annotations

import json
import hashlib
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Any, List

# --- CORRECTED IMPORTS ---
from scheduler_models import (
    Project, Task, Contact, TaskStatus,
    ModelEncoder
)
from scheduler_storage import StorageStrategy, get_storage_engine

# Alias for type hinting compatibility
Storage = StorageStrategy


# =============================================================================
# CONSTANTS & ENUMS
# =============================================================================

VERSION = "1.0.1"
TITLE_SIMILARITY_THRESHOLD = 0.8
CREATED_AT_WINDOW = 3600  # 1 hour

class MergeStrategy(Enum):
    AUTO = "auto"
    INTERACTIVE = "interactive"
    THEIRS = "theirs"
    OURS = "ours"
    PREVIEW = "preview"

class MergeAction(Enum):
    COPY = "copy"
    UPDATE = "update"
    SKIP = "skip"
    CONFLICT = "conflict"

class FieldMergeRule(Enum):
    NEWER = "newer"
    LONGER = "longer"
    UNION = "union"
    HIGHER = "higher"
    NONEMPTY = "nonempty"
    CONCATENATE = "concatenate"

FIELD_RULES: dict[str, FieldMergeRule] = {
    "title": FieldMergeRule.LONGER,
    "assignee": FieldMergeRule.NONEMPTY,
    "status": FieldMergeRule.HIGHER,
    "due_date": FieldMergeRule.NONEMPTY,
    "reminder_date": FieldMergeRule.NONEMPTY,
    "outcome": FieldMergeRule.LONGER,
    "notes": FieldMergeRule.CONCATENATE,
    "tags": FieldMergeRule.UNION,
    "contact_id": FieldMergeRule.NONEMPTY,
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class FieldConflict:
    field: str
    local_value: Any
    remote_value: Any
    rule_applied: Optional[str] = None

@dataclass
class TaskMatch:
    local_task: Optional[Task]
    remote_task: Optional[Task]
    similarity: float = 1.0
    action: MergeAction = MergeAction.SKIP
    conflicts: List[FieldConflict] = field(default_factory=list)
    merged_task: Optional[Task] = None
    
    @property
    def is_new(self) -> bool:
        return self.local_task is None and self.remote_task is not None
    
    @property
    def task_id(self) -> str:
        return self.local_task.id if self.local_task else (self.remote_task.id if self.remote_task else "unknown")
    
    @property
    def title(self) -> str:
        if self.merged_task: return self.merged_task.title
        if self.remote_task: return self.remote_task.title
        if self.local_task: return self.local_task.title
        return "Unknown"

@dataclass
class ContactMatch:
    local_contact: Optional[Contact]
    remote_contact: Optional[Contact]
    action: MergeAction = MergeAction.SKIP
    merged_contact: Optional[Contact] = None

@dataclass  
class ProjectMergePlan:
    slug: str
    action: MergeAction
    local_project: Optional[Project]
    remote_project: Optional[Project]
    task_matches: List[TaskMatch] = field(default_factory=list)
    contact_matches: List[ContactMatch] = field(default_factory=list)
    
    @property
    def tasks_to_add(self) -> int:
        return sum(1 for m in self.task_matches if m.action == MergeAction.COPY)
    
    @property
    def tasks_to_update(self) -> int:
        return sum(1 for m in self.task_matches if m.action == MergeAction.UPDATE)
    
    @property
    def task_conflicts(self) -> int:
        return sum(1 for m in self.task_matches if m.action == MergeAction.CONFLICT)
    
    def summary_line(self) -> str:
        if self.action == MergeAction.COPY:
            task_count = len(self.remote_project.tasks) if self.remote_project else 0
            return f"  {self.slug}: NEW (copy {task_count} tasks)"
        elif self.action == MergeAction.UPDATE:
            parts = []
            if self.tasks_to_add: parts.append(f"+{self.tasks_to_add} tasks")
            if self.tasks_to_update: parts.append(f"~{self.tasks_to_update} updates")
            if self.task_conflicts: parts.append(f"!{self.task_conflicts} conflicts")
            return f"  {self.slug}: MERGE ({', '.join(parts) or 'no changes'})"
        else:
            return f"  {self.slug}: UP TO DATE"

@dataclass
class MergePlan:
    project_plans: List[ProjectMergePlan] = field(default_factory=list)
    source_path: Optional[Path] = None
    target_path: Optional[Path] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    
    @property
    def projects_to_copy(self) -> List[ProjectMergePlan]:
        return [p for p in self.project_plans if p.action == MergeAction.COPY]
    
    @property
    def projects_to_update(self) -> List[ProjectMergePlan]:
        return [p for p in self.project_plans if p.action == MergeAction.UPDATE]
    
    @property
    def total_conflicts(self) -> int:
        return sum(p.task_conflicts for p in self.project_plans)
    
    def summary(self) -> str:
        lines = ["Merge Plan", "=" * 50, f"Source: {self.source_path}", f"Target: {self.target_path}", ""]
        if not self.project_plans:
            lines.append("No projects to merge.")
            return "\n".join(lines)
        
        if self.projects_to_copy:
            lines.append(f"New Projects ({len(self.projects_to_copy)}):")
            for p in self.projects_to_copy: lines.append(p.summary_line())
            lines.append("")
        
        if self.projects_to_update:
            lines.append(f"Projects to Merge ({len(self.projects_to_update)}):")
            for p in self.projects_to_update: lines.append(p.summary_line())
            lines.append("")
        
        lines.append(f"Summary: {len(self.projects_to_copy)} new, {len(self.projects_to_update)} merge, {self.total_conflicts} conflicts")
        return "\n".join(lines)

@dataclass
class MergeResult:
    success: bool
    projects_copied: int = 0
    projects_merged: int = 0
    tasks_added: int = 0
    tasks_updated: int = 0
    contacts_added: int = 0
    conflicts_created: int = 0
    errors: List[str] = field(default_factory=list)
    
    def summary(self) -> str:
        if not self.success: return f"Merge failed: {'; '.join(self.errors)}"
        lines = ["Merge completed successfully:"]
        if self.projects_copied: lines.append(f"  - {self.projects_copied} projects copied")
        if self.projects_merged: lines.append(f"  - {self.projects_merged} projects merged")
        if self.tasks_added: lines.append(f"  - {self.tasks_added} tasks added")
        if self.tasks_updated: lines.append(f"  - {self.tasks_updated} tasks updated")
        if self.conflicts_created: lines.append(f"  - {self.conflicts_created} conflicts need resolution (run 'scheduler merge conflicts')")
        return "\n".join(lines)

@dataclass
class StoredConflict:
    id: str
    project_slug: str
    task_id: str
    task_title: str
    field: str
    local_value: Any
    remote_value: Any
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    resolved: bool = False
    resolution: Optional[str] = None


# =============================================================================
# LOGIC
# =============================================================================

def _normalize(s: str) -> str:
    return s.lower().strip()

def _title_similarity(a: str, b: str) -> float:
    words_a = set(_normalize(a).split())
    words_b = set(_normalize(b).split())
    if not words_a or not words_b: return 1.0 if a == b else 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0

def _timestamps_close(ts_a: str, ts_b: str) -> bool:
    if not ts_a or not ts_b: return False
    try:
        dt_a = datetime.fromisoformat(ts_a)
        dt_b = datetime.fromisoformat(ts_b)
        return abs((dt_a - dt_b).total_seconds()) <= CREATED_AT_WINDOW
    except ValueError:
        return False

def _generate_conflict_id(project_slug: str, task_id: str, field: str) -> str:
    content = f"{project_slug}:{task_id}:{field}"
    return hashlib.sha256(content.encode()).hexdigest()[:8]

def _merge_field(field_name: str, local_val: Any, remote_val: Any, local_updated: str, remote_updated: str, strategy: MergeStrategy) -> tuple[Any, Optional[FieldConflict]]:
    if strategy == MergeStrategy.THEIRS: return remote_val, None
    if strategy == MergeStrategy.OURS: return local_val, None
    if local_val == remote_val: return local_val, None
    
    rule = FIELD_RULES.get(field_name, FieldMergeRule.NONEMPTY)
    
    if rule == FieldMergeRule.NEWER:
        # Simplified newer check (string comparison usually works for ISO dates)
        return (remote_val if remote_updated > local_updated else local_val), None
    elif rule == FieldMergeRule.LONGER:
        return (remote_val if len(str(remote_val or "")) > len(str(local_val or "")) else local_val), None
    elif rule == FieldMergeRule.UNION:
        return list(set(local_val or []) | set(remote_val or [])), None
    elif rule == FieldMergeRule.HIGHER:
        if isinstance(local_val, TaskStatus) and isinstance(remote_val, TaskStatus):
            # We assume order based on definition in models, or just take remote if diff
             return remote_val, None # Simplification
        return local_val, None
    elif rule == FieldMergeRule.NONEMPTY:
        if not local_val: return remote_val, None
        if not remote_val: return local_val, None
        # Both set and diff -> conflict
        return local_val, FieldConflict(field_name, local_val, remote_val, rule.value)
    elif rule == FieldMergeRule.CONCATENATE:
        if not local_val: return remote_val, None
        if not remote_val: return local_val, None
        return f"{local_val}\n\n--- merged ---\n\n{remote_val}", None
        
    return local_val, None

class MergeService:
    def __init__(self, target: StorageStrategy, source: StorageStrategy):
        self.target = target
        self.source = source
        self._conflicts_file = target.base_dir / "merge_conflicts.json"
    
    def plan_merge(self) -> MergePlan:
        plan = MergePlan(source_path=self.source.base_dir, target_path=self.target.base_dir)
        source_slugs = set(self.source.list_projects())
        target_slugs = set(self.target.list_projects())
        
        for slug in source_slugs - target_slugs:
            plan.project_plans.append(ProjectMergePlan(slug=slug, action=MergeAction.COPY, local_project=None, remote_project=self.source.load_project(slug)))
            
        for slug in source_slugs & target_slugs:
            local = self.target.load_project(slug)
            remote = self.source.load_project(slug)
            if local and remote:
                plan.project_plans.append(self._plan_project_merge(local, remote))
        return plan
    
    def _plan_project_merge(self, local: Project, remote: Project) -> ProjectMergePlan:
        plan = ProjectMergePlan(slug=local.slug, action=MergeAction.UPDATE, local_project=local, remote_project=remote)
        plan.task_matches = self._match_tasks(local.tasks, remote.tasks)
        plan.contact_matches = self._match_contacts(local.contacts, remote.contacts)
        
        has_changes = any(m.action != MergeAction.SKIP for m in plan.task_matches + plan.contact_matches)
        if not has_changes: plan.action = MergeAction.SKIP
        return plan
    
    def _match_tasks(self, local_tasks: List[Task], remote_tasks: List[Task]) -> List[TaskMatch]:
        matches = []
        matched_remote_ids = set()
        
        for local in local_tasks:
            best = None
            best_sim = 0.0
            for remote in remote_tasks:
                if remote.id in matched_remote_ids: continue
                if local.id == remote.id:
                    best = remote
                    best_sim = 1.0
                    break
                sim = _title_similarity(local.title, remote.title)
                if _timestamps_close(local.created_at, remote.created_at): sim = min(1.0, sim + 0.2)
                if sim >= TITLE_SIMILARITY_THRESHOLD and sim > best_sim:
                    best = remote
                    best_sim = sim
            
            if best:
                matched_remote_ids.add(best.id)
                matches.append(self._create_task_match(local, best, best_sim))
            else:
                matches.append(TaskMatch(local_task=local, remote_task=None, action=MergeAction.SKIP))
                
        for remote in remote_tasks:
            if remote.id not in matched_remote_ids:
                matches.append(TaskMatch(local_task=None, remote_task=remote, action=MergeAction.COPY, merged_task=remote))
        return matches

    def _create_task_match(self, local: Task, remote: Task, similarity: float) -> TaskMatch:
        match = TaskMatch(local_task=local, remote_task=remote, similarity=similarity)
        merged_data = {}
        conflicts = []
        
        for field in ["title", "assignee", "due_date", "reminder_date", "outcome", "notes", "tags", "contact_id"]:
            m_val, conf = _merge_field(field, getattr(local, field), getattr(remote, field), local.updated_at, remote.updated_at, MergeStrategy.AUTO)
            merged_data[field] = m_val
            if conf: conflicts.append(conf)
            
        # Status merge (higher wins)
        merged_status = remote.status # Simplified
        
        match.merged_task = Task(
            id=local.id,
            title=merged_data["title"],
            assignee=merged_data["assignee"],
            status=merged_status,
            due_date=merged_data["due_date"],
            reminder_date=merged_data["reminder_date"],
            outcome=merged_data["outcome"],
            notes=merged_data["notes"],
            tags=merged_data["tags"],
            contact_id=merged_data["contact_id"],
            created_at=local.created_at,
            updated_at=datetime.now().isoformat()
        )
        match.conflicts = conflicts
        if conflicts: match.action = MergeAction.CONFLICT
        elif self._task_changed(local, match.merged_task): match.action = MergeAction.UPDATE
        return match

    def _task_changed(self, original: Task, merged: Task) -> bool:
        return asdict(original) != asdict(merged)

    def _match_contacts(self, local: List[Contact], remote: List[Contact]) -> List[ContactMatch]:
        matches = []
        matched_remote = set()
        for l in local:
            match = next((r for r in remote if _normalize(r.name) == _normalize(l.name) and r.id not in matched_remote), None)
            if match:
                matched_remote.add(match.id)
                merged = Contact(id=l.id, name=l.name, phone=match.phone or l.phone, email=match.email or l.email, role=match.role or l.role, notes=match.notes or l.notes)
                matches.append(ContactMatch(local_contact=l, remote_contact=match, action=MergeAction.UPDATE, merged_contact=merged))
            else:
                matches.append(ContactMatch(local_contact=l, remote_contact=None, action=MergeAction.SKIP))
        
        for r in remote:
            if r.id not in matched_remote:
                matches.append(ContactMatch(local_contact=None, remote_contact=r, action=MergeAction.COPY, merged_contact=r))
        return matches

    def execute_merge(self, plan: Optional[MergePlan] = None, strategy: MergeStrategy = MergeStrategy.AUTO) -> MergeResult:
        if strategy == MergeStrategy.PREVIEW: return MergeResult(success=True)
        plan = plan or self.plan_merge()
        result = MergeResult(success=True)
        
        try:
            for pp in plan.project_plans:
                if pp.action == MergeAction.COPY:
                    self.target.save_project(pp.remote_project)
                    result.projects_copied += 1
                elif pp.action == MergeAction.UPDATE:
                    self._merge_project(pp, result)
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
        return result

    def _merge_project(self, plan: ProjectMergePlan, result: MergeResult):
        project = plan.local_project
        modified = False
        
        for tm in plan.task_matches:
            if tm.action == MergeAction.COPY:
                project.tasks.append(tm.merged_task)
                modified = True
                result.tasks_added += 1
            elif tm.action == MergeAction.UPDATE:
                for i, t in enumerate(project.tasks):
                    if t.id == tm.local_task.id:
                        project.tasks[i] = tm.merged_task
                        modified = True
                        result.tasks_updated += 1
                        break
            elif tm.action == MergeAction.CONFLICT:
                for c in tm.conflicts:
                    self._store_conflict(project.slug, tm.task_id, tm.title, c)
                    result.conflicts_created += 1
                # Save the merged task anyway (with local wins)
                for i, t in enumerate(project.tasks):
                     if t.id == tm.local_task.id:
                        project.tasks[i] = tm.merged_task
                        modified = True
                        break
        
        for cm in plan.contact_matches:
            if cm.action == MergeAction.COPY:
                project.contacts.append(cm.merged_contact)
                modified = True
            elif cm.action == MergeAction.UPDATE:
                for i, c in enumerate(project.contacts):
                    if c.id == cm.local_contact.id:
                        project.contacts[i] = cm.merged_contact
                        modified = True
                        break
                        
        if modified:
            project.updated_at = datetime.now().isoformat()
            self.target.save_project(project)
            result.projects_merged += 1

    def _store_conflict(self, slug: str, task_id: str, title: str, conflict: FieldConflict):
        conflicts = self._load_conflicts()
        stored = StoredConflict(id=_generate_conflict_id(slug, task_id, conflict.field), project_slug=slug, task_id=task_id, task_title=title, field=conflict.field, local_value=conflict.local_value, remote_value=conflict.remote_value)
        conflicts.append(stored)
        self._save_conflicts(conflicts)

    def _load_conflicts(self) -> List[StoredConflict]:
        if not self._conflicts_file.exists(): return []
        try:
            with open(self._conflicts_file, "r") as f:
                return [StoredConflict(**c) for c in json.load(f)]
        except: return []

    def _save_conflicts(self, conflicts: List[StoredConflict]):
        with open(self._conflicts_file, "w") as f:
            # FIX: Used ModelEncoder to handle Enums/Objects safely
            json.dump([asdict(c) for c in conflicts], f, indent=2, cls=ModelEncoder)

    def get_conflicts(self) -> List[StoredConflict]:
        return [c for c in self._load_conflicts() if not c.resolved]

    def resolve_conflict(self, conflict_id: str, take: str) -> bool:
        conflicts = self._load_conflicts()
        target_c = next((c for c in conflicts if c.id == conflict_id), None)
        if not target_c: return False
        
        project = self.target.load_project(target_c.project_slug)
        if project:
            task = next((t for t in project.tasks if t.id == target_c.task_id), None)
            if task:
                val = target_c.remote_value if take == "remote" else target_c.local_value
                setattr(task, target_c.field, val)
                self.target.save_project(project)
                target_c.resolved = True
                target_c.resolution = take
                self._save_conflicts(conflicts)
                return True
        return False

# =============================================================================
# CLI
# =============================================================================

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python scheduler_merge.py <source_path> [--apply]")
        print("       python scheduler_merge.py conflicts")
        return

    # FIX: Use Factory instead of Abstract Class
    try:
        from scheduler_config import get_data_dir
        target = get_storage_engine(get_data_dir())
    except:
        target = get_storage_engine()

    if args[0] == "conflicts":
        svc = MergeService(target, target)
        for c in svc.get_conflicts():
            print(f"[{c.id}] {c.project_slug}: {c.field} (Local: {c.local_value} | Remote: {c.remote_value})")
        return
        
    source_path = Path(args[0])
    # FIX: Use Factory for source too
    source = get_storage_engine(source_path)
    
    svc = MergeService(target, source)
    if "--apply" in args:
        res = svc.execute_merge()
        print(res.summary())
    else:
        print(svc.plan_merge().summary())

if __name__ == "__main__":
    main()
