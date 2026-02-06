"""
cli.py - Command Line Interface
"""
import sys
import shlex
from pathlib import Path
from .config import get_config
from .storage.factory import get_storage_engine
from .services.task_service import TaskService
from .services.maintenance_service import MaintenanceService
from .services.calendar_service import CalendarService

class CLI:
    def __init__(self):
        self.cfg = get_config()
        self.storage = get_storage_engine(self.cfg.data_dir, self.cfg.preferences.get("storage_engine", "json"))
        self.task_service = TaskService(self.storage)
        self.maint_service = MaintenanceService(self.storage)
        self.cal_service = CalendarService()

    def run(self):
        print(f"\n📋 Smart Scheduler 2.0 ({self.cfg.preferences.get('storage_engine', 'json')})")
        print(f"Data: {self.cfg.data_dir}")
        print("Type 'help' for commands, 'quit' or Ctrl+Z to exit.")
        while True:
            try:
                cmd = input("\n> ").strip()
                if not cmd: continue
                if cmd.lower() in ("quit", "exit"): break
                self._execute(cmd)
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")

    def _execute(self, cmd_str):
        parts = shlex.split(cmd_str)
        if not parts: return
        handler = _COMMANDS.get(parts[0].lower())
        if handler: handler(self, parts[1:])
        else: print(f"Unknown command: {parts[0]}")

    def _opts(self, args):
        pos, opts = [], {}
        i = 0
        while i < len(args):
            if args[i].startswith("-"):
                k = args[i].lstrip("-")
                v = True
                if i+1 < len(args) and not args[i+1].startswith("-"):
                    v = args[i+1]; i += 1
                opts[k] = v
            else: pos.append(args[i])
            i += 1
        return pos, opts

# --- Commands ---

def cmd_config(cli, args):
    if not args:
        print(f"\nConfiguration:")
        print(f"  Data Directory: {cli.cfg.data_dir}")
        print(f"  Config File:    {cli.cfg.config_path}")
        print(f"  Preferences:    {cli.cfg.preferences}")
        return

    action = args[0].lower()
    
    if action == "location" and len(args) > 1:
        import shutil
        import os
        
        new_path = Path(args[1]).resolve()
        old_path = cli.cfg.data_dir
        
        if new_path == old_path:
            return print("New path is the same as current path.")
            
        print(f"\nMoving data...")
        print(f"  Source: {old_path}")
        print(f"  Dest:   {new_path}")
        
        new_path.mkdir(parents=True, exist_ok=True)
        items_to_move = ["scheduler.db", "projects", "exports"]
        moved_count = 0
        
        for item in items_to_move:
            src = old_path / item
            dst = new_path / item
            
            if src.exists():
                if dst.exists():
                    print(f"  Warning: '{item}' already exists in destination. Skipping.")
                else:
                    shutil.move(str(src), str(dst))
                    print(f"  Moved: {item}")
                    moved_count += 1
        
        cli.cfg.set_data_dir(str(new_path))
        print(f"\nSuccess! Data directory updated.")
        print(f"Config file remains at: {cli.cfg.config_path}")
    
    elif action == "set" and len(args) > 2:
        key, val = args[1], args[2]
        cli.cfg.set_preference(key, val)
        print(f"Preference '{key}' set to '{val}'")
        if key == "storage_engine":
            print("Restart required to switch storage engines.")
    else:
        print("Usage: config [location <path> | set <key> <val>]")

def cmd_list(cli, args):
    pos, opts = cli._opts(args)
    projects = cli.storage.load_all_projects()
    show_all = opts.get("all") or opts.get("a")
    found = False
    for p in projects:
        active = p.active_tasks
        if not active and not show_all: continue
        found = True
        print(f"\n[{p.name}] ({p.slug})")
        if active:
            for t in active:
                # UPDATED: Display due date next to task
                due = f" [Due: {t.due_date}]" if t.due_date else ""
                print(f"  {t.status.icon} {t.title} ({t.id}){due}")
        else:
            print(f"  (No active tasks. {len(p.tasks)} total.)")
    if not found: print("No active projects. Use --all.")

def cmd_show(cli, args):
    if not args: return print("Usage: show <slug> [task_id]")
    p = cli.storage.load_project(args[0])
    if not p: return print("Project not found")
    
    if len(args) > 1:
        t = next((x for x in p.tasks if x.id.startswith(args[1])), None)
        if not t: return print("Task not found")
        print(f"\n{t.title} ({t.id})\nStatus: {t.status.value}\nDue: {t.due_date}\nNotes: {t.notes}")
    else:
        print(f"\nProject: {p.name}\n{p.description}")
        for t in p.tasks:
            icon = t.status.icon if t.is_active else f"[{t.status.value.upper()}]"
            # UPDATED: Display due date next to task
            due = f" [Due: {t.due_date}]" if t.due_date else ""
            print(f"  {icon} {t.title} ({t.id}){due}")

def cmd_new(cli, args):
    if len(args) < 2 or args[0] != "project": return print("Usage: new project <slug> <name>")
    cli.task_service.create_project(args[1], args[2])
    print("Project created.")

def cmd_delete(cli, args):
    if len(args) < 2 or args[0] != "project": return print("Usage: delete project <slug>")
    slug = args[1]
    
    confirm = input(f"Are you sure you want to delete project '{slug}' and ALL its tasks? (y/N): ")
    if confirm.lower() != 'y':
        return print("Deletion cancelled.")
        
    if cli.task_service.delete_project(slug):
        print(f"Project '{slug}' deleted.")
    else:
        print(f"Project '{slug}' not found.")

def cmd_add(cli, args):
    if len(args) < 2: return print("Usage: add <task|contact> ...")
    kind = args[0]
    if kind == "task":
        if len(args) < 3: return
        slug, title = args[1], args[2]
        pos, opts = cli._opts(args[3:])
        cli.task_service.add_task(slug, title, due=opts.get("due") or opts.get("d"), notes=opts.get("note"), tags=opts.get("g", "").split(","))
        print("Task added.")
    elif kind == "contact":
        if len(args) < 3: return
        slug, name = args[1], args[2]
        pos, opts = cli._opts(args[3:])
        cli.task_service.add_contact(slug, name, role=opts.get("role"), note=opts.get("note"))
        print("Contact added.")

def cmd_edit(cli, args):
    if len(args) < 1: return
    slug = args[0]
    pos, opts = cli._opts(args[1:])
    
    task_id = None
    if pos: task_id = pos[0]
    
    if task_id:
        updates = {}
        if "due" in opts or "d" in opts: updates["due_date"] = opts.get("due") or opts.get("d")
        if "note" in opts: updates["notes"] = opts.get("note")
        if "s" in opts: updates["status"] = opts.get("s")
        cli.task_service.update_task(slug, task_id, **updates)
        print("Task updated.")
    else:
        cli.task_service.update_project(slug, name=opts.get("name"), desc=opts.get("desc"))
        print("Project updated.")

def cmd_backup(cli, args):
    pos, opts = cli._opts(args)
    name = opts.get("name") or opts.get("bkup_name")
    compress = "compress" in opts
    path = cli.maint_service.backup(name, compress)
    print(f"Backup created at: {path}")

def cmd_restore(cli, args):
    if not args: return print("Usage: restore <path>")
    try:
        cli.maint_service.restore(args[0])
        print("Restore successful.")
    except Exception as e:
        print(f"Restore failed: {e}")

def cmd_maintenance(cli, args):
    pos, opts = cli._opts(args)
    if "vacuum" in opts or "optimize" in opts:
        cli.maint_service.optimize_database()
        print("Database optimized.")

def cmd_export(cli, args):
    if len(args) < 2: return print("Usage: export <slug> [ics|json|csv] [task_id]")
    slug, fmt = args[0], args[1]
    
    if fmt == "ics":
        if len(args) < 3: return print("For ICS, specify task_id: export <slug> ics <task_id>")
        task_id = args[2]
        p = cli.storage.load_project(slug)
        if not p: return print("Project not found")
        t = next((x for x in p.tasks if x.id.startswith(task_id)), None)
        if not t: return print("Task not found")
        content = cli.cal_service.generate_file_content(t)
        fname = f"{slug}_{t.id}.ics"
        Path(fname).write_text(content, encoding="utf-8")
        print(f"Exported to {fname}")

_COMMANDS = {
    "list": cmd_list, "show": cmd_show, "new": cmd_new, "add": cmd_add, 
    "edit": cmd_edit, "delete": cmd_delete,
    "backup": cmd_backup, "restore": cmd_restore, "maintenance": cmd_maintenance, 
    "export": cmd_export, "config": cmd_config,
    "help": lambda c, a: print("Commands: list, show, new, add, edit, delete, backup, restore, maintenance, export, config")
}

def main():
    CLI().run()
