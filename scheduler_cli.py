"""
scheduler_cli.py - Command Line Interface.
"""
import sys
import argparse
from pathlib import Path
from typing import List, Optional, Tuple

from scheduler_config import get_config
from scheduler_storage import get_storage_engine
from scheduler_services import TaskService, TaskStatus
from scheduler_models import Task

class CLI:
    def __init__(self, base_dir: Optional[Path] = None):
        cfg = get_config()
        self.base_dir = base_dir or cfg.data_dir
        engine_type = cfg.preferences.get("storage_engine", "json")
        
        self.storage = get_storage_engine(self.base_dir, engine_type)
        self.service = TaskService(self.storage)

    def run(self):
        print(f"\n📋 Smart Scheduler ({self.storage.__class__.__name__})")
        print("="*40)
        summary = self.service.get_summary()
        print(f"Projects: {summary['total_projects']}, Active Tasks: {summary['total_active']}")
        print("\nType 'help' for commands, 'quit' to exit.")
        
        while True:
            try:
                cmd = input("\n> ").strip()
                if not cmd: continue
                if cmd.lower() in ("quit", "exit"): break
                self._execute(cmd)
            except (KeyboardInterrupt, EOFError):
                break
            except Exception as e:
                print(f"Error: {e}")

    def _execute(self, cmd_str: str):
        parts = self._split_args(cmd_str)
        if not parts: return
        
        handler_name = parts[0].lower()
        if handler_name in _COMMANDS:
            _COMMANDS[handler_name](self, parts[1:])
        else:
            print(f"Unknown command: {handler_name}")

    def _split_args(self, cmd_str: str) -> List[str]:
        import shlex
        return shlex.split(cmd_str)

    def _parse_options(self, args: List[str]) -> Tuple[List[str], dict]:
        positional = []
        options = {}
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith("-"):
                key = arg.lstrip("-")
                val = True
                if i + 1 < len(args) and not args[i+1].startswith("-"):
                    val = args[i+1]
                    i += 1
                options[key] = val
            else:
                positional.append(arg)
            i += 1
        return positional, options

# --- Command Handlers ---

def cmd_list(cli: CLI, args: List[str]):
    _, opts = cli._parse_options(args)
    tag_filter = opts.get("tag") or opts.get("t")
    
    projects = cli.storage.load_all_projects()
    if not projects:
        print("No projects found.")
        return

    for p in projects:
        active = [t for t in p.active_tasks]
        if tag_filter:
            active = [t for t in active if tag_filter in t.tags]
            
        if not active: continue
        print(f"\n[{p.name}] ({p.slug})")
        for t in active:
            icon = t.status.icon
            due = f" due {t.due_date}" if t.due_date else ""
            print(f"  {icon} {t.title} ({t.id}){due}")

def cmd_show(cli: CLI, args: List[str]):
    if not args: return print("Usage: show <slug> [task_id]")
    slug = args[0]
    project = cli.storage.load_project(slug)
    if not project: return print(f"Project '{slug}' not found.")

    if len(args) > 1:
        task_id = args[1]
        task = next((t for t in project.tasks if t.id.startswith(task_id)), None)
        if not task: return print(f"Task '{task_id}' not found in project '{slug}'.")
        
        print(f"\nTask: {task.title}")
        print("="*40)
        print(f"ID:       {task.id}")
        print(f"Status:   {task.status.icon} {task.status.value.upper()}")
        print(f"Assignee: {task.assignee or 'None'}")
        print(f"Due:      {task.due_date or 'None'}")
        print(f"Tags:     {', '.join(task.tags)}")
        if task.contact_id:
            c_name = next((c.name for c in project.contacts if c.id == task.contact_id), "Unknown")
            print(f"Contact:  {c_name}")
        print("-" * 40)
        print(f"📝 Notes:\n{task.notes or '(No notes)'}")
        print("-" * 40)
        print(f"🏁 Outcome:\n{task.outcome or '(No outcome)'}")
        return

    print(f"\nProject: {project.name} ({project.slug})")
    print("="*40)
    print(project.description or "(No description)")
    
    if project.contacts:
        print("\nContacts:")
        for c in project.contacts:
            note = f" -- {c.notes}" if c.notes else ""
            print(f"  * {c.name} ({c.role or 'No role'}) - {c.phone or 'No phone'}{note}")
            
    print("\nTasks:")
    for t in project.tasks:
        if t.is_active:
            print(f"  {t.status.icon} {t.title} ({t.id})")

def cmd_new_project(cli: CLI, args: List[str]):
    if len(args) < 3 or args[0] != "project":
        return print("Usage: new project <slug> <name>")
    try:
        p = cli.service.create_project(args[1], args[2])
        print(f"Created project '{p.name}'")
    except ValueError as e:
        print(f"Error: {e}")

def cmd_add_task(cli: CLI, args: List[str]):
    if len(args) < 3:
        return print("Usage: add task <slug> <title>")
    
    # args[0] is 'task' (checked by router), so args[1] is slug, args[2] is title
    slug, title = args[1], args[2]
    pos, opts = cli._parse_options(args[3:])
    
    due = opts.get("due") or opts.get("d")
    assignee = opts.get("assignee") or opts.get("a")
    tags_str = opts.get("tags") or opts.get("g") or opts.get("tag")
    tags = tags_str.split(",") if tags_str else []
    contact = opts.get("contact") or opts.get("c")
    
    try:
        t = cli.service.add_task(slug, title, assignee, due, tags, contact_id=contact)
        print(f"Added task: {t.title} ({t.id})")
    except ValueError as e:
        print(f"Error: {e}")

def cmd_add_contact(cli: CLI, args: List[str]):
    if len(args) < 3: return print("Usage: add contact <slug> <name> [options]")
    slug, name = args[1], args[2]
    _, opts = cli._parse_options(args[3:])
    
    try:
        c = cli.service.add_contact(slug, name, opts.get("phone"), opts.get("role"), opts.get("email"), opts.get("note"))
        print(f"Added contact: {c.name}")
    except ValueError as e:
        print(f"Error: {e}")

def cmd_add_router(cli: CLI, args: List[str]):
    if not args: return print("Usage: add <task|contact> <slug> ...")
    sub = args[0].lower()
    if sub == "task": cmd_add_task(cli, args)
    elif sub == "contact": cmd_add_contact(cli, args)
    else: print(f"Unknown command: '{sub}'")

def cmd_rename(cli: CLI, args: List[str]):
    if len(args) < 2: return print("Usage: rename <old> <new>")
    try:
        new = cli.service.rename_project(args[0], args[1])
        print(f"Renamed to {new}")
    except ValueError as e:
        print(f"Error: {e}")

def cmd_export(cli: CLI, args: List[str]):
    if len(args) < 1: return print("Usage: export <slug> [json|csv]")
    slug = args[0]
    fmt = args[1] if len(args) > 1 else "json"
    
    from scheduler_services import ImportExportService
    svc = ImportExportService(cli.storage)
    
    try:
        if fmt == "csv":
            print(svc.export_csv(slug))
        else:
            print(svc.export_json(slug))
    except ValueError as e:
        print(f"Error: {e}")

def cmd_edit(cli: CLI, args: List[str]):
    if not args: return print("Usage: edit <slug> [task_id] [options]")
    slug = args[0]
    is_task_edit = len(args) > 1 and not args[1].startswith("-")
    
    if is_task_edit:
        task_id = args[1]
        _, opts = cli._parse_options(args[2:])
        updates = {}
        if "due" in opts or "d" in opts: updates["due_date"] = opts.get("due") or opts.get("d")
        if "title" in opts or "t" in opts: updates["title"] = opts.get("title") or opts.get("t")
        if "assignee" in opts or "a" in opts: updates["assignee"] = opts.get("assignee") or opts.get("a")
            
        if not updates: return print("No task changes specified.")
        try:
            t = cli.service.update_task(slug, task_id, **updates)
            print(f"Updated task: {t.title} ({t.id})")
        except ValueError as e:
            print(f"Error: {e}")
    else:
        _, opts = cli._parse_options(args[1:])
        name = opts.get("name") or opts.get("n")
        desc = opts.get("desc") or opts.get("description") or opts.get("note")
        
        if not name and not desc: return print("No project changes specified.")
        try:
            p = cli.service.update_project(slug, name, desc)
            print(f"Updated Project: {p.name}")
        except ValueError as e:
            print(f"Error: {e}")

def cmd_help(cli: CLI, args: List[str]):
    print("Commands: list, show, new project, add task, add contact, rename, edit, export, help, quit")

_COMMANDS = {
    "list": cmd_list,
    "show": cmd_show,
    "new": cmd_new_project,
    "add": cmd_add_router,
    "rename": cmd_rename,
    "edit": cmd_edit,
    "export": cmd_export,
    "help": cmd_help
}