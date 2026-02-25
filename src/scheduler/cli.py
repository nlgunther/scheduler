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
        
        cmd_name = parts[0].lower()
        args = parts[1:]
        
        # Handle --help flag for any command
        if args and args[0] in ("--help", "-h"):
            help_text = _HELP.get(cmd_name)
            if help_text:
                print(help_text)
            else:
                print(f"No help available for '{cmd_name}'")
            return
        
        handler = _COMMANDS.get(cmd_name)
        if handler: handler(self, args)
        else: print(f"Unknown command: {cmd_name}")

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
    
    def _find_by_id(self, identifier):
        """
        Find a project or task by ID globally across all projects.
        
        Args:
            identifier: Full ID or ID prefix
            
        Returns:
            Tuple of (project, task) or (project, None) for project-only,
            or (None, None) if not found
        """
        projects = self.storage.load_all_projects()
        
        # Check if it's a project slug first
        for p in projects:
            if p.slug == identifier:
                return (p, None)
        
        # Search for task ID across all projects
        matches = []
        for p in projects:
            for t in p.tasks:
                if t.id == identifier or t.id.startswith(identifier):
                    matches.append((p, t))
        
        if len(matches) == 0:
            return (None, None)
        elif len(matches) == 1:
            return matches[0]
        else:
            # Multiple matches - show options
            print(f"\nMultiple items match '{identifier}':")
            for i, (p, t) in enumerate(matches, 1):
                print(f"  [{i}] {t.title} ({t.id}) in project '{p.name}'")
            
            try:
                choice = input("\nSelect number (or 'c' to cancel): ").strip()
                if choice.lower() == 'c':
                    return (None, None)
                idx = int(choice) - 1
                if 0 <= idx < len(matches):
                    return matches[idx]
            except (ValueError, KeyboardInterrupt):
                pass
            
            return (None, None)

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
    """Show project or task details. Supports global ID lookup."""
    if not args: return print("Usage: show <project_slug|task_id>")
    
    # Try global ID lookup first
    p, t = cli._find_by_id(args[0])
    
    if t:
        # Found a task
        print(f"\n{t.title} ({t.id})")
        print(f"Project: {p.name} ({p.slug})")
        print(f"Status: {t.status.value}")
        print(f"Due: {t.due_date or 'Not set'}")
        print(f"Notes: {t.notes or 'None'}")
        return
    
    if p:
        # Found a project - show all tasks
        print(f"\nProject: {p.name}\n{p.description or '(No description)'}")
        for task in p.tasks:
            icon = task.status.icon if task.is_active else f"[{task.status.value.upper()}]"
            due = f" [Due: {task.due_date}]" if task.due_date else ""
            print(f"  {icon} {task.title} ({task.id}){due}")
        return
    
    print(f"No project or task found matching '{args[0]}'")

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
    """Edit a task or project. Supports global ID lookup."""
    if len(args) < 1: 
        return print("Usage: edit <project_slug|task_id> [options]\n"
                    "Options: --due <date>, --note <text>, --s <status>")
    
    identifier = args[0]
    pos, opts = cli._opts(args[1:])
    
    # Try global ID lookup
    p, t = cli._find_by_id(identifier)
    
    if not p:
        return print(f"No project or task found matching '{identifier}'")
    
    if t:
        # Editing a task
        updates = {}
        if "due" in opts or "d" in opts: 
            updates["due_date"] = opts.get("due") or opts.get("d")
        if "note" in opts: 
            updates["notes"] = opts.get("note")
        if "s" in opts: 
            updates["status"] = opts.get("s")
        
        if not updates:
            return print("No updates specified. Use --due, --note, or --s")
        
        cli.task_service.update_task(p.slug, t.id, **updates)
        print(f"Task '{t.title}' updated.")
    else:
        # Editing a project
        updates = {}
        if "name" in opts:
            updates["name"] = opts["name"]
        if "desc" in opts:
            updates["desc"] = opts["desc"]
        
        if not updates:
            return print("No updates specified. Use --name or --desc")
        
        cli.task_service.update_project(p.slug, **updates)
        print(f"Project '{p.name}' updated.")

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
    """Export project data in various formats."""
    if len(args) < 2: 
        return print("Usage: export <slug> [ics|json|csv|to_manifest] [task_id]\n"
                    "       export to_manifest <slug> <file>")
    
    # Handle manifest export format
    if args[0] == "to_manifest":
        return cmd_export_manifest(cli, args)
    
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

def cmd_import_manifest(cli, args):
    """Import tasks from Manifest Manager CSV export.
    
    Usage: import from_manifest <csv_file> --project <slug>
    """
    try:
        from shared.integration import SchemaMapper, DataFrameBridge
        import pandas as pd
    except ImportError:
        return print("Error: Manifest integration requires 'shared' module and pandas.\n"
                    "Install: pip install pandas\n"
                    "Setup shared module - see SHARED_MODULE_INTEGRATION_PLAN.md")
    
    pos, opts = cli._opts(args)
    if len(pos) < 2 or pos[0] != "from_manifest":
        return print("Usage: import from_manifest <file> --project <slug>")
    
    csv_file = pos[1]
    project_slug = opts.get("project") or opts.get("p")
    
    if not project_slug:
        return print("Error: --project <slug> required\n"
                    "Example: import from_manifest tasks.csv --project planning")
    
    # Check file exists
    if not Path(csv_file).exists():
        return print(f"Error: File not found: {csv_file}")
    
    # Load project
    project = cli.storage.load_project(project_slug)
    if not project:
        return print(f"Error: Project '{project_slug}' not found\n"
                    f"Create it first: new project {project_slug} \"Project Name\"")
    
    # Read and validate CSV
    try:
        df_manifest = pd.read_csv(csv_file)
    except Exception as e:
        return print(f"Error reading CSV: {e}")
    
    # Validate
    is_valid, issues = DataFrameBridge.validate_import(
        df_manifest,
        required_columns=['source_id', 'title']
    )
    if not is_valid:
        print("Validation errors:")
        for issue in issues:
            print(f"  • {issue}")
        return
    
    # Transform to scheduler format
    df_scheduler = SchemaMapper.manifest_to_scheduler(df_manifest)
    
    # Import tasks
    count = 0
    for _, row in df_scheduler.iterrows():
        title = row.get('title', 'Untitled')
        due_date = row.get('due_date')
        notes = row.get('notes', '')
        source_id = row.get('source_id')
        status = row.get('status', 'todo')
        
        # Store source_id in tags for round-trip
        tags = [f"manifest_id:{source_id}"] if pd.notna(source_id) else []
        
        try:
            cli.task_service.add_task(
                project_slug,
                title,
                due=due_date if pd.notna(due_date) else None,
                notes=notes if pd.notna(notes) else None,
                tags=tags
            )
            count += 1
        except Exception as e:
            print(f"Warning: Failed to import task '{title}': {e}")
    
    print(f"✓ Imported {count} tasks from manifest into project '{project.name}'")

def cmd_export_manifest(cli, args):
    """Export project to Manifest Manager format.
    
    Usage: export to_manifest <project_slug> <output_file>
    """
    try:
        from shared.integration import SchemaMapper, DataFrameBridge
        import pandas as pd
    except ImportError:
        return print("Error: Manifest integration requires 'shared' module and pandas.\n"
                    "Install: pip install pandas\n"
                    "Setup shared module - see SHARED_MODULE_INTEGRATION_PLAN.md")
    
    if len(args) < 3:
        return print("Usage: export to_manifest <project_slug> <file>")
    
    project_slug = args[1]
    output_file = args[2]
    
    # Load project
    project = cli.storage.load_project(project_slug)
    if not project:
        return print(f"Error: Project '{project_slug}' not found")
    
    # Convert tasks to DataFrame
    rows = []
    for task in project.tasks:
        # Extract manifest_id from tags if present
        manifest_id = None
        if hasattr(task, 'tags') and task.tags:
            for tag in task.tags:
                if tag.startswith("manifest_id:"):
                    manifest_id = tag.split(":", 1)[1]
                    break
        
        rows.append({
            'source_id': manifest_id or task.id,
            'title': task.title,
            'assignee': getattr(task, 'assignee', None),
            'status': task.status.value,
            'due_date': task.due_date,
            'priority': getattr(task, 'priority', None),
            'notes': task.notes,
        })
    
    df_scheduler = pd.DataFrame(rows)
    
    # Transform to manifest format
    df_manifest = SchemaMapper.scheduler_to_manifest(df_scheduler)
    
    # Add metadata for tracking
    df_manifest = DataFrameBridge.add_metadata(df_manifest, source='scheduler')
    
    # Save
    df_manifest.to_csv(output_file, index=False)
    
    print(f"✓ Exported {len(rows)} tasks to {output_file}")
    print(f"\nTo import into manifest:")
    print(f"  manifest")
    print(f"  (manifest) load your_file.xml")
    print(f"  (your_file.xml) import_scheduler {output_file}")
    print(f"  (your_file.xml) save")

_COMMANDS = {
    "list": cmd_list, "show": cmd_show, "new": cmd_new, "add": cmd_add, 
    "edit": cmd_edit, "delete": cmd_delete,
    "backup": cmd_backup, "restore": cmd_restore, "maintenance": cmd_maintenance, 
    "export": cmd_export, "config": cmd_config,
    "import": cmd_import_manifest,
    "help": lambda c, a: print(_GENERAL_HELP if not a else _HELP.get(a[0], f"No help for '{a[0]}'"))
}

_GENERAL_HELP = """
Smart Scheduler Commands:

  list [--all]              List projects and active tasks
  show <id>                 Show project or task details (by ID or slug)
  edit <id> [options]       Edit task or project (by ID or slug)
  add task <project> <title> [--due <date>] [--note <text>]
  new project <slug> <name>
  delete project <slug>
  
  backup [--name <n>]       Create backup
  restore <path>            Restore from backup
  export <slug> <format>    Export project
  config [location <path>]  Configure settings
  
  help [command]            Show help (use: help <command> for details)
  quit | exit               Exit scheduler

Use '<command> --help' for command-specific help.
Examples:
  edit --help
  show --help
"""

_HELP = {
    "list": """list [--all | -a]

List all projects with their active tasks.

Options:
  --all, -a    Show all projects, including those with no active tasks

Examples:
  list
  list --all""",

    "show": """show <project_slug | task_id>

Show details for a project or task. Accepts project slug or task ID.
Task IDs work globally - no need to specify the project.

Arguments:
  project_slug   Project identifier (e.g., 'my_project')
  task_id        Task ID or ID prefix (e.g., 't30b0a' or just 't30')

Examples:
  show scheduled_payments     # Show project
  show t30b0a                 # Show task by ID
  show t30                    # Show task by ID prefix (interactive if multiple)""",

    "edit": """edit <project_slug | task_id> [OPTIONS]

Edit a project or task. Accepts project slug or task ID.
Task IDs work globally - no need to specify the project.

Arguments:
  project_slug | task_id   What to edit

Task Options:
  --due <date>      Set due date (YYYY-MM-DD format)
  --note <text>     Set or update notes
  --s <status>      Set status (todo, in_progress, done, etc.)

Project Options:
  --name <text>     Change project name
  --desc <text>     Change project description

Examples:
  edit t30b0a --note "email from jpatterson @mvccvt.com 2026-02-25"
  edit t30b0a --due 2026-03-31
  edit scheduled_payments --desc "Monthly payment tracking"
  edit t30 --s done""",

    "add": """add task <project_slug> <title> [OPTIONS]
add contact <project_slug> <name> [OPTIONS]

Add a task or contact to a project.

Task Options:
  --due <date>      Due date (YYYY-MM-DD)
  --note <text>     Task notes
  --g <tags>        Comma-separated tags

Contact Options:
  --role <text>     Contact's role
  --note <text>     Notes about contact

Examples:
  add task scheduled_payments "Pay utility bill" --due 2026-03-15
  add task my_project "Review document" --note "Check appendix" --due 2026-03-20
  add contact my_project "John Doe" --role "Project Manager" """,

    "new": """new project <slug> <name>

Create a new project.

Arguments:
  slug    Project identifier (lowercase, no spaces)
  name    Project display name

Example:
  new project budget_2026 "2026 Budget Planning" """,

    "delete": """delete project <slug>

Delete a project and all its tasks (requires confirmation).

Arguments:
  slug    Project slug to delete

Example:
  delete project old_project""",

    "export": """export <project_slug> <format> [task_id]

Export project or task data.

Formats:
  ics      Export single task as iCalendar file (requires task_id)
  json     Export project as JSON
  csv      Export project as CSV

Examples:
  export scheduled_payments ics t30b0a
  export my_project json
  export budget_2026 csv""",

    "backup": """backup [--name <name>] [--compress]

Create a backup of all data.

Options:
  --name <name>    Custom backup name
  --compress       Create compressed backup

Example:
  backup --name "before_cleanup" --compress""",

    "restore": """restore <backup_path>

Restore data from a backup file.

Arguments:
  backup_path    Path to backup file

Example:
  restore backups/backup_20260217.json""",

    "config": """config [ACTION]
config location <path>
config set <key> <value>

View or modify configuration.

Actions:
  (no args)           Show current configuration
  location <path>     Move data directory
  set <key> <value>   Set preference

Examples:
  config
  config location ~/Documents/scheduler_data
  config set storage_engine sqlite"""
}

def main():
    CLI().run()
