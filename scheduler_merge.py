#!/usr/bin/env python3
"""
scheduler_merge.py - Multi-source merge for Smart Scheduler.

Enables syncing scheduler data between devices by merging projects and tasks
from a remote/secondary data directory into the local/primary one.

Merge Strategy:
    - Projects: Copy new, merge existing by slug
    - Tasks: Match by title similarity + timestamps, apply field-level rules
    - Contacts: Match by name, merge details
    - Conflicts: Track for user resolution

Features:
    - Preview mode (dry run)
    - Configurable conflict resolution (auto, interactive, theirs, ours)
    - Detailed merge reports
    - Conflict tracking and resolution commands

Usage:
    from scheduler_merge import MergeService, MergeStrategy
    
    service = MergeService(local_storage, remote_storage)
    
    # Preview what would happen
    plan = service.plan_merge()
    print(plan.summary())
    
    # Execute merge
    result = service.execute_merge(strategy=MergeStrategy.AUTO)

CLI:
    scheduler merge /path/to/remote/data           # Preview merge
    scheduler merge /path/to/remote/data --apply   # Execute merge
    scheduler merge conflicts                       # Show pending conflicts
    scheduler merge resolve <id> --take local      # Resolve a conflict

Author: Claude (Anthropic)
License: MIT
Version: 1.0.0
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Any

# Import from scheduler (assumes scheduler.py is available)
from scheduler import (
    Storage, Project, Task, Contact, TaskStatus,
    project_from_dict, task_from_dict, contact_from_dict,
    ModelEncoder,
)


# =============================================================================
# CONSTANTS
# =============================================================================

VERSION = "1.0.0"

# Similarity threshold for title matching (0.0 - 1.0)
TITLE_SIMILARITY_THRESHOLD = 0.8

# Time window for considering tasks as "same" (seconds)
CREATED_AT_WINDOW = 3600  # 1 hour


# =============================================================================
# ENUMS
# =============================================================================

class MergeStrategy(Enum):
    """How to resolve conflicts during merge."""
    AUTO = "auto"              # Apply rules, track unresolvable conflicts
    INTERACTIVE = "interactive"  # Prompt user for each conflict
    THEIRS = "theirs"          # Always prefer remote/source values
    OURS = "ours"              # Always prefer local/target values
    PREVIEW = "preview"        # Don't apply changes, just plan


class MergeAction(Enum):
    """What to do with an entity during merge."""
    COPY = "copy"              # New entity, copy from source
    UPDATE = "update"          # Existing entity, update fields
    SKIP = "skip"              # No changes needed
    CONFLICT = "conflict"      # Has unresolved conflicts


class FieldMergeRule(Enum):
    """How to merge a specific field."""
    NEWER = "newer"            # Take value from more recently updated
    LONGER = "longer"          # Take longer string value
    UNION = "union"            # Combine (for lists like tags)
    HIGHER = "higher"          # Take higher value (for status progression)
    NONEMPTY = "nonempty"      # Take non-empty, prefer target if both set
    CONCATENATE = "concatenate"  # Combine with separator (notes)


# Field merge rules by field name
FIELD_RULES: dict[str, FieldMergeRule] = {
    "title": FieldMergeRule.LONGER,
    "assignee": FieldMergeRule.NONEMPTY,  # "me" yields to specific name
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
    """A conflict on a single field that couldn't be auto-resolved."""
    field: str
    local_value: Any
    remote_value: Any
    rule_applied: Optional[str] = None


@dataclass
class TaskMatch:
    """A matched pair of tasks (local and remote) or a new task."""
    local_task: Optional[Task]
    remote_task: Optional[Task]
    similarity: float = 1.0
    action: MergeAction = MergeAction.SKIP
    conflicts: list[FieldConflict] = field(default_factory=list)
    merged_task: Optional[Task] = None
    
    @property
    def is_new(self) -> bool:
        return self.local_task is None and self.remote_task is not None
    
    @property
    def task_id(self) -> str:
        """Get the relevant task ID."""
        if self.local_task:
            return self.local_task.id
        if self.remote_task:
            return self.remote_task.id
        return "unknown"
    
    @property
    def title(self) -> str:
        """Get the task title for display."""
        if self.merged_task:
            return self.merged_task.title
        if self.remote_task:
            return self.remote_task.title
        if self.local_task:
            return self.local_task.title
        return "Unknown"


@dataclass
class ContactMatch:
    """A matched pair of contacts."""
    local_contact: Optional[Contact]
    remote_contact: Optional[Contact]
    action: MergeAction = MergeAction.SKIP
    merged_contact: Optional[Contact] = None


@dataclass  
class ProjectMergePlan:
    """Merge plan for a single project."""
    slug: str
    action: MergeAction
    local_project: Optional[Project]
    remote_project: Optional[Project]
    task_matches: list[TaskMatch] = field(default_factory=list)
    contact_matches: list[ContactMatch] = field(default_factory=list)
    
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
        """One-line summary for display."""
        if self.action == MergeAction.COPY:
            task_count = len(self.remote_project.tasks) if self.remote_project else 0
            return f"  {self.slug}: NEW (copy {task_count} tasks)"
        elif self.action == MergeAction.UPDATE:
            parts = []
            if self.tasks_to_add:
                parts.append(f"+{self.tasks_to_add} tasks")
            if self.tasks_to_update:
                parts.append(f"~{self.tasks_to_update} updates")
            if self.task_conflicts:
                parts.append(f"!{self.task_conflicts} conflicts")
            return f"  {self.slug}: MERGE ({', '.join(parts) or 'no changes'})"
        else:
            return f"  {self.slug}: UP TO DATE"


@dataclass
class MergePlan:
    """Complete merge plan across all projects."""
    project_plans: list[ProjectMergePlan] = field(default_factory=list)
    source_path: Optional[Path] = None
    target_path: Optional[Path] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    
    @property
    def projects_to_copy(self) -> list[ProjectMergePlan]:
        return [p for p in self.project_plans if p.action == MergeAction.COPY]
    
    @property
    def projects_to_update(self) -> list[ProjectMergePlan]:
        return [p for p in self.project_plans if p.action == MergeAction.UPDATE]
    
    @property
    def total_conflicts(self) -> int:
        return sum(p.task_conflicts for p in self.project_plans)
    
    @property
    def total_tasks_to_add(self) -> int:
        return sum(p.tasks_to_add for p in self.project_plans)
    
    @property
    def total_tasks_to_update(self) -> int:
        return sum(p.tasks_to_update for p in self.project_plans)
    
    def summary(self) -> str:
        """Human-readable merge plan summary."""
        lines = [
            "Merge Plan",
            "=" * 50,
            f"Source: {self.source_path}",
            f"Target: {self.target_path}",
            "",
        ]
        
        if not self.project_plans:
            lines.append("No projects to merge.")
            return "\n".join(lines)
        
        if self.projects_to_copy:
            lines.append(f"New Projects ({len(self.projects_to_copy)}):")
            for p in self.projects_to_copy:
                lines.append(p.summary_line())
            lines.append("")
        
        if self.projects_to_update:
            lines.append(f"Projects to Merge ({len(self.projects_to_update)}):")
            for p in self.projects_to_update:
                lines.append(p.summary_line())
            lines.append("")
        
        # Summary stats
        lines.extend([
            "Summary:",
            f"  Projects: {len(self.projects_to_copy)} new, {len(self.projects_to_update)} to merge",
            f"  Tasks: {self.total_tasks_to_add} to add, {self.total_tasks_to_update} to update",
        ])
        
        if self.total_conflicts:
            lines.append(f"  Conflicts: {self.total_conflicts} (will need resolution)")
        
        return "\n".join(lines)


@dataclass
class MergeResult:
    """Result of executing a merge."""
    success: bool
    projects_copied: int = 0
    projects_merged: int = 0
    tasks_added: int = 0
    tasks_updated: int = 0
    contacts_added: int = 0
    conflicts_created: int = 0
    errors: list[str] = field(default_factory=list)
    
    def summary(self) -> str:
        """Human-readable result summary."""
        if not self.success:
            return f"Merge failed: {'; '.join(self.errors)}"
        
        lines = ["Merge completed successfully:"]
        if self.projects_copied:
            lines.append(f"  - {self.projects_copied} projects copied")
        if self.projects_merged:
            lines.append(f"  - {self.projects_merged} projects merged")
        if self.tasks_added:
            lines.append(f"  - {self.tasks_added} tasks added")
        if self.tasks_updated:
            lines.append(f"  - {self.tasks_updated} tasks updated")
        if self.contacts_added:
            lines.append(f"  - {self.contacts_added} contacts added")
        if self.conflicts_created:
            lines.append(f"  - {self.conflicts_created} conflicts need resolution")
            lines.append("    Run 'scheduler merge conflicts' to view")
        
        return "\n".join(lines)


@dataclass
class StoredConflict:
    """A conflict stored for later resolution."""
    id: str
    project_slug: str
    task_id: str
    task_title: str
    field: str
    local_value: Any
    remote_value: Any
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    resolved: bool = False
    resolution: Optional[str] = None  # "local", "remote", or custom value


# =============================================================================
# SIMILARITY UTILITIES
# =============================================================================

def _normalize(s: str) -> str:
    """Normalize string for comparison."""
    return s.lower().strip()


def _title_similarity(a: str, b: str) -> float:
    """
    Calculate similarity between two task titles.
    
    Uses a simple approach: normalized overlap of words.
    Returns 0.0 to 1.0.
    """
    words_a = set(_normalize(a).split())
    words_b = set(_normalize(b).split())
    
    if not words_a or not words_b:
        return 1.0 if a == b else 0.0
    
    intersection = words_a & words_b
    union = words_a | words_b
    
    return len(intersection) / len(union) if union else 0.0


def _parse_timestamp(ts: str) -> Optional[datetime]:
    """Parse ISO timestamp, return None on failure."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _timestamps_close(ts_a: str, ts_b: str, window_seconds: int = CREATED_AT_WINDOW) -> bool:
    """Check if two timestamps are within the given window."""
    dt_a, dt_b = _parse_timestamp(ts_a), _parse_timestamp(ts_b)
    if not dt_a or not dt_b:
        return False
    return abs((dt_a - dt_b).total_seconds()) <= window_seconds


def _generate_conflict_id(project_slug: str, task_id: str, field: str) -> str:
    """Generate a unique ID for a conflict."""
    content = f"{project_slug}:{task_id}:{field}"
    return hashlib.sha256(content.encode()).hexdigest()[:8]


# =============================================================================
# FIELD MERGING
# =============================================================================

def _merge_field(
    field_name: str,
    local_val: Any,
    remote_val: Any,
    local_updated: str,
    remote_updated: str,
    strategy: MergeStrategy
) -> tuple[Any, Optional[FieldConflict]]:
    """
    Merge a single field according to rules.
    
    Returns (merged_value, conflict_or_none).
    """
    # Strategy overrides
    if strategy == MergeStrategy.THEIRS:
        return remote_val, None
    if strategy == MergeStrategy.OURS:
        return local_val, None
    
    rule = FIELD_RULES.get(field_name, FieldMergeRule.NONEMPTY)
    
    # Same value = no conflict
    if local_val == remote_val:
        return local_val, None
    
    # Apply rule
    if rule == FieldMergeRule.NEWER:
        local_dt = _parse_timestamp(local_updated)
        remote_dt = _parse_timestamp(remote_updated)
        if local_dt and remote_dt:
            return (remote_val if remote_dt > local_dt else local_val), None
        return local_val, None  # Default to local if can't compare
    
    elif rule == FieldMergeRule.LONGER:
        local_len = len(str(local_val or ""))
        remote_len = len(str(remote_val or ""))
        return (remote_val if remote_len > local_len else local_val), None
    
    elif rule == FieldMergeRule.UNION:
        # For lists (tags)
        local_set = set(local_val or [])
        remote_set = set(remote_val or [])
        return list(local_set | remote_set), None
    
    elif rule == FieldMergeRule.HIGHER:
        # For TaskStatus
        if isinstance(local_val, TaskStatus) and isinstance(remote_val, TaskStatus):
            return (remote_val if remote_val.order > local_val.order else local_val), None
        return local_val, None
    
    elif rule == FieldMergeRule.NONEMPTY:
        # Special case: "me" yields to specific assignee
        if field_name == "assignee":
            if local_val == "me" and remote_val and remote_val != "me":
                return remote_val, None
            if remote_val == "me" and local_val and local_val != "me":
                return local_val, None
        
        # Take non-empty; if both set and different, conflict
        if not local_val:
            return remote_val, None
        if not remote_val:
            return local_val, None
        # Both set and different - conflict
        return local_val, FieldConflict(field_name, local_val, remote_val, rule.value)
    
    elif rule == FieldMergeRule.CONCATENATE:
        # For notes
        if not local_val:
            return remote_val, None
        if not remote_val:
            return local_val, None
        # Concatenate with separator
        return f"{local_val}\n\n--- merged ---\n\n{remote_val}", None
    
    # Fallback: keep local
    return local_val, None


# =============================================================================
# MERGE SERVICE
# =============================================================================

class MergeService:
    """
    Service for merging scheduler data from multiple sources.
    
    Compares a source (remote) storage with a target (local) storage,
    creates a merge plan, and optionally executes it.
    
    Example:
        local = Storage()  # Uses configured path
        remote = Storage(Path("/backup/scheduler"))
        
        service = MergeService(local, remote)
        plan = service.plan_merge()
        
        if plan.total_conflicts == 0:
            result = service.execute_merge()
    """
    
    def __init__(self, target: Storage, source: Storage):
        """
        Initialize merge service.
        
        Args:
            target: Local/primary storage (will be modified)
            source: Remote/secondary storage (read-only)
        """
        self.target = target
        self.source = source
        self._conflicts_file = target.base_dir / "merge_conflicts.json"
    
    # -------------------------------------------------------------------------
    # Planning
    # -------------------------------------------------------------------------
    
    def plan_merge(self) -> MergePlan:
        """
        Create a merge plan without making changes.
        
        Analyzes both storages and determines what actions to take.
        """
        plan = MergePlan(
            source_path=self.source.base_dir,
            target_path=self.target.base_dir,
        )
        
        source_slugs = set(self.source.list_projects())
        target_slugs = set(self.target.list_projects())
        
        # Projects only in source -> copy
        for slug in source_slugs - target_slugs:
            remote_project = self.source.load_project(slug)
            if remote_project:
                plan.project_plans.append(ProjectMergePlan(
                    slug=slug,
                    action=MergeAction.COPY,
                    local_project=None,
                    remote_project=remote_project,
                ))
        
        # Projects in both -> merge
        for slug in source_slugs & target_slugs:
            local_project = self.target.load_project(slug)
            remote_project = self.source.load_project(slug)
            
            if local_project and remote_project:
                project_plan = self._plan_project_merge(local_project, remote_project)
                plan.project_plans.append(project_plan)
        
        return plan
    
    def _plan_project_merge(self, local: Project, remote: Project) -> ProjectMergePlan:
        """Plan merge for a single project."""
        plan = ProjectMergePlan(
            slug=local.slug,
            action=MergeAction.UPDATE,
            local_project=local,
            remote_project=remote,
        )
        
        # Match tasks
        plan.task_matches = self._match_tasks(local.tasks, remote.tasks)
        
        # Match contacts
        plan.contact_matches = self._match_contacts(local.contacts, remote.contacts)
        
        # Determine if any actual changes
        has_changes = any(
            m.action != MergeAction.SKIP 
            for m in plan.task_matches + plan.contact_matches
        )
        
        if not has_changes:
            plan.action = MergeAction.SKIP
        
        return plan
    
    def _match_tasks(self, local_tasks: list[Task], remote_tasks: list[Task]) -> list[TaskMatch]:
        """
        Match local and remote tasks by similarity.
        
        Strategy:
            1. Exact ID match (rare but possible if data was copied)
            2. Title similarity + created_at proximity
            3. Remaining remote tasks are new
        """
        matches = []
        matched_remote_ids = set()
        
        for local_task in local_tasks:
            best_match: Optional[Task] = None
            best_similarity = 0.0
            
            for remote_task in remote_tasks:
                if remote_task.id in matched_remote_ids:
                    continue
                
                # Exact ID match
                if local_task.id == remote_task.id:
                    best_match = remote_task
                    best_similarity = 1.0
                    break
                
                # Title similarity
                similarity = _title_similarity(local_task.title, remote_task.title)
                
                # Boost if created_at is close
                if _timestamps_close(local_task.created_at, remote_task.created_at):
                    similarity = min(1.0, similarity + 0.2)
                
                if similarity >= TITLE_SIMILARITY_THRESHOLD and similarity > best_similarity:
                    best_match = remote_task
                    best_similarity = similarity
            
            if best_match:
                matched_remote_ids.add(best_match.id)
                match = self._create_task_match(local_task, best_match, best_similarity)
                matches.append(match)
            else:
                # Local task has no remote match - skip (already in local)
                matches.append(TaskMatch(
                    local_task=local_task,
                    remote_task=None,
                    action=MergeAction.SKIP,
                ))
        
        # Remote tasks with no local match - new
        for remote_task in remote_tasks:
            if remote_task.id not in matched_remote_ids:
                matches.append(TaskMatch(
                    local_task=None,
                    remote_task=remote_task,
                    action=MergeAction.COPY,
                    merged_task=remote_task,
                ))
        
        return matches
    
    def _create_task_match(self, local: Task, remote: Task, similarity: float) -> TaskMatch:
        """Create a TaskMatch with merged task and conflicts."""
        match = TaskMatch(
            local_task=local,
            remote_task=remote,
            similarity=similarity,
        )
        
        # Merge each field
        merged_data = {}
        conflicts = []
        
        for field_name in ["title", "assignee", "due_date", "reminder_date", 
                          "outcome", "notes", "tags", "contact_id"]:
            local_val = getattr(local, field_name)
            remote_val = getattr(remote, field_name)
            
            merged_val, conflict = _merge_field(
                field_name, local_val, remote_val,
                local.updated_at, remote.updated_at,
                MergeStrategy.AUTO
            )
            
            merged_data[field_name] = merged_val
            if conflict:
                conflicts.append(conflict)
        
        # Status merge
        merged_status = remote.status if remote.status.order > local.status.order else local.status
        
        # Create merged task
        match.merged_task = Task(
            id=local.id,  # Keep local ID
            title=merged_data["title"],
            assignee=merged_data["assignee"],
            status=merged_status,
            due_date=merged_data["due_date"],
            reminder_date=merged_data["reminder_date"],
            outcome=merged_data["outcome"],
            notes=merged_data["notes"],
            tags=merged_data["tags"],
            contact_id=merged_data["contact_id"],
            created_at=local.created_at,  # Keep original creation time
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )
        
        match.conflicts = conflicts
        
        # Determine action
        if conflicts:
            match.action = MergeAction.CONFLICT
        elif self._task_changed(local, match.merged_task):
            match.action = MergeAction.UPDATE
        else:
            match.action = MergeAction.SKIP
        
        return match
    
    def _task_changed(self, original: Task, merged: Task) -> bool:
        """Check if merged task differs from original."""
        fields = ["title", "assignee", "status", "due_date", "reminder_date",
                  "outcome", "notes", "contact_id"]
        
        for f in fields:
            if getattr(original, f) != getattr(merged, f):
                return True
        
        if set(original.tags) != set(merged.tags):
            return True
        
        return False
    
    def _match_contacts(self, local: list[Contact], remote: list[Contact]) -> list[ContactMatch]:
        """Match contacts by name."""
        matches = []
        matched_remote_ids = set()
        
        for local_contact in local:
            for remote_contact in remote:
                if remote_contact.id in matched_remote_ids:
                    continue
                
                if _normalize(local_contact.name) == _normalize(remote_contact.name):
                    matched_remote_ids.add(remote_contact.id)
                    # Merge: take non-empty fields from remote
                    merged = Contact(
                        id=local_contact.id,
                        name=local_contact.name,
                        phone=remote_contact.phone or local_contact.phone,
                        email=remote_contact.email or local_contact.email,
                        role=remote_contact.role or local_contact.role,
                        notes=remote_contact.notes or local_contact.notes,
                    )
                    
                    changed = any(
                        getattr(merged, f) != getattr(local_contact, f)
                        for f in ["phone", "email", "role", "notes"]
                    )
                    
                    matches.append(ContactMatch(
                        local_contact=local_contact,
                        remote_contact=remote_contact,
                        action=MergeAction.UPDATE if changed else MergeAction.SKIP,
                        merged_contact=merged,
                    ))
                    break
            else:
                matches.append(ContactMatch(
                    local_contact=local_contact,
                    remote_contact=None,
                    action=MergeAction.SKIP,
                ))
        
        # New contacts from remote
        for remote_contact in remote:
            if remote_contact.id not in matched_remote_ids:
                matches.append(ContactMatch(
                    local_contact=None,
                    remote_contact=remote_contact,
                    action=MergeAction.COPY,
                    merged_contact=remote_contact,
                ))
        
        return matches
    
    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------
    
    def execute_merge(self, plan: Optional[MergePlan] = None, 
                      strategy: MergeStrategy = MergeStrategy.AUTO) -> MergeResult:
        """
        Execute a merge plan.
        
        Args:
            plan: Pre-computed merge plan (computed if None)
            strategy: How to handle conflicts
        
        Returns:
            MergeResult with statistics
        """
        if strategy == MergeStrategy.PREVIEW:
            return MergeResult(success=True)
        
        plan = plan or self.plan_merge()
        result = MergeResult(success=True)
        
        try:
            for project_plan in plan.project_plans:
                if project_plan.action == MergeAction.COPY:
                    self._copy_project(project_plan, result)
                elif project_plan.action == MergeAction.UPDATE:
                    self._merge_project(project_plan, result, strategy)
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
        
        return result
    
    def _copy_project(self, plan: ProjectMergePlan, result: MergeResult) -> None:
        """Copy a new project from source to target."""
        if plan.remote_project:
            self.target.save_project(plan.remote_project)
            result.projects_copied += 1
            result.tasks_added += len(plan.remote_project.tasks)
            result.contacts_added += len(plan.remote_project.contacts)
    
    def _merge_project(self, plan: ProjectMergePlan, result: MergeResult,
                       strategy: MergeStrategy) -> None:
        """Merge changes into an existing project."""
        if not plan.local_project:
            return
        
        project = plan.local_project
        modified = False
        
        # Process task matches
        for task_match in plan.task_matches:
            if task_match.action == MergeAction.COPY and task_match.merged_task:
                project.tasks.append(task_match.merged_task)
                result.tasks_added += 1
                modified = True
                
            elif task_match.action == MergeAction.UPDATE and task_match.merged_task:
                # Replace local task with merged
                for i, t in enumerate(project.tasks):
                    if t.id == task_match.local_task.id:
                        project.tasks[i] = task_match.merged_task
                        result.tasks_updated += 1
                        modified = True
                        break
                        
            elif task_match.action == MergeAction.CONFLICT:
                # Store conflicts for later resolution
                for conflict in task_match.conflicts:
                    self._store_conflict(
                        project.slug, 
                        task_match.task_id,
                        task_match.title,
                        conflict
                    )
                    result.conflicts_created += 1
                
                # Still apply the merged task (with local values for conflicted fields)
                if task_match.merged_task:
                    for i, t in enumerate(project.tasks):
                        if t.id == task_match.local_task.id:
                            project.tasks[i] = task_match.merged_task
                            modified = True
                            break
        
        # Process contact matches
        for contact_match in plan.contact_matches:
            if contact_match.action == MergeAction.COPY and contact_match.merged_contact:
                project.contacts.append(contact_match.merged_contact)
                result.contacts_added += 1
                modified = True
                
            elif contact_match.action == MergeAction.UPDATE and contact_match.merged_contact:
                for i, c in enumerate(project.contacts):
                    if c.id == contact_match.local_contact.id:
                        project.contacts[i] = contact_match.merged_contact
                        modified = True
                        break
        
        if modified:
            project.mark_updated()
            self.target.save_project(project)
            result.projects_merged += 1
    
    # -------------------------------------------------------------------------
    # Conflict Management
    # -------------------------------------------------------------------------
    
    def _store_conflict(self, project_slug: str, task_id: str, 
                        task_title: str, conflict: FieldConflict) -> None:
        """Store a conflict for later resolution."""
        conflicts = self._load_conflicts()
        
        stored = StoredConflict(
            id=_generate_conflict_id(project_slug, task_id, conflict.field),
            project_slug=project_slug,
            task_id=task_id,
            task_title=task_title,
            field=conflict.field,
            local_value=conflict.local_value,
            remote_value=conflict.remote_value,
        )
        
        # Replace if exists, otherwise append
        existing_idx = next(
            (i for i, c in enumerate(conflicts) if c.id == stored.id), 
            None
        )
        
        if existing_idx is not None:
            conflicts[existing_idx] = stored
        else:
            conflicts.append(stored)
        
        self._save_conflicts(conflicts)
    
    def _load_conflicts(self) -> list[StoredConflict]:
        """Load stored conflicts from file."""
        if not self._conflicts_file.exists():
            return []
        
        try:
            with open(self._conflicts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [StoredConflict(**c) for c in data]
        except (json.JSONDecodeError, TypeError):
            return []
    
    def _save_conflicts(self, conflicts: list[StoredConflict]) -> None:
        """Save conflicts to file."""
        with open(self._conflicts_file, "w", encoding="utf-8") as f:
            json.dump([asdict(c) for c in conflicts], f, indent=2)
    
    def get_conflicts(self, include_resolved: bool = False) -> list[StoredConflict]:
        """Get pending conflicts."""
        conflicts = self._load_conflicts()
        if include_resolved:
            return conflicts
        return [c for c in conflicts if not c.resolved]
    
    def resolve_conflict(self, conflict_id: str, take: str) -> bool:
        """
        Resolve a stored conflict.
        
        Args:
            conflict_id: ID of the conflict
            take: "local", "remote", or a custom value
        
        Returns:
            True if conflict was found and resolved
        """
        conflicts = self._load_conflicts()
        
        for conflict in conflicts:
            if conflict.id == conflict_id:
                # Apply resolution to task
                project = self.target.load_project(conflict.project_slug)
                if project:
                    task = project.get_task(conflict.task_id)
                    if task:
                        if take == "local":
                            # Already has local value, just mark resolved
                            pass
                        elif take == "remote":
                            setattr(task, conflict.field, conflict.remote_value)
                            task.mark_updated()
                            project.mark_updated()
                            self.target.save_project(project)
                        else:
                            # Custom value
                            setattr(task, conflict.field, take)
                            task.mark_updated()
                            project.mark_updated()
                            self.target.save_project(project)
                
                conflict.resolved = True
                conflict.resolution = take
                self._save_conflicts(conflicts)
                return True
        
        return False
    
    def clear_resolved_conflicts(self) -> int:
        """Remove resolved conflicts from storage. Returns count removed."""
        conflicts = self._load_conflicts()
        unresolved = [c for c in conflicts if not c.resolved]
        removed = len(conflicts) - len(unresolved)
        self._save_conflicts(unresolved)
        return removed


# =============================================================================
# CLI INTEGRATION HELPERS
# =============================================================================

def format_conflicts(conflicts: list[StoredConflict]) -> str:
    """Format conflicts for CLI display."""
    if not conflicts:
        return "No pending conflicts."
    
    lines = [f"Pending Conflicts ({len(conflicts)}):", ""]
    
    for c in conflicts:
        lines.extend([
            f"  [{c.id}] {c.project_slug} / {c.task_title}",
            f"    Field: {c.field}",
            f"    Local:  {c.local_value!r}",
            f"    Remote: {c.remote_value!r}",
            "",
        ])
    
    lines.append("Resolve with: scheduler merge resolve <id> --take local|remote")
    return "\n".join(lines)


def merge_preview(source_path: Path, target_storage: Storage) -> str:
    """Generate merge preview for CLI."""
    source_storage = Storage(source_path)
    service = MergeService(target_storage, source_storage)
    plan = service.plan_merge()
    return plan.summary()


def execute_merge_cli(source_path: Path, target_storage: Storage, 
                      strategy: str = "auto") -> str:
    """Execute merge and return summary for CLI."""
    source_storage = Storage(source_path)
    service = MergeService(target_storage, source_storage)
    
    strategy_enum = MergeStrategy(strategy)
    result = service.execute_merge(strategy=strategy_enum)
    
    return result.summary()


# =============================================================================
# STANDALONE CLI
# =============================================================================

def main():
    """Standalone CLI for merge operations."""
    import sys
    
    args = sys.argv[1:]
    
    if not args or args[0] in ("--help", "-h"):
        print(__doc__)
        return
    
    # Load target storage
    try:
        from scheduler_config import get_data_dir
        target = Storage(get_data_dir())
    except ImportError:
        target = Storage()
    
    if args[0] == "conflicts":
        # Show conflicts
        service = MergeService(target, target)  # Source doesn't matter for conflicts
        conflicts = service.get_conflicts()
        print(format_conflicts(conflicts))
        
    elif args[0] == "resolve" and len(args) >= 2:
        # Resolve a conflict
        conflict_id = args[1]
        take = "local"
        if "--take" in args:
            idx = args.index("--take")
            if idx + 1 < len(args):
                take = args[idx + 1]
        
        service = MergeService(target, target)
        if service.resolve_conflict(conflict_id, take):
            print(f"Resolved conflict {conflict_id} -> {take}")
        else:
            print(f"Conflict {conflict_id} not found")
            
    elif len(args) >= 1:
        # Merge from path
        source_path = Path(args[0]).expanduser().resolve()
        
        if not source_path.exists():
            print(f"Error: Source path not found: {source_path}")
            sys.exit(1)
        
        if "--apply" in args:
            print(execute_merge_cli(source_path, target))
        else:
            print(merge_preview(source_path, target))
            print("\nTo apply, run with --apply flag")
    
    else:
        print("Usage: python scheduler_merge.py <source_path> [--apply]")
        print("       python scheduler_merge.py conflicts")
        print("       python scheduler_merge.py resolve <id> --take local|remote")


if __name__ == "__main__":
    main()
