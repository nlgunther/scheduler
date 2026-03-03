"""
cli.py - Command Line Interface (COMPREHENSIVE VERSION)

Features:
- Detailed hierarchical display with project IDs
- Status icons with legend
- Smart filtering (hide completed by default)
- Bulk cleanup commands
- Global ID lookup
- Comprehensive help
"""
import sys
import shlex
from pathlib import Path
from .config import get_config
from .storage.factory import get_storage_engine
from .services.task_service import TaskService
from .services.maintenance_service import MaintenanceService
from .services.calendar_service import CalendarService
from .models import TaskStatus

class CLI:
    def __init__(self):
        self.cfg = get_config()
        self.storage = get_storage_engine(self.cfg.data_dir, self.cfg.preferences.get("storage_engine", "json"))
        self.task_service = TaskService(self.storage)
        self.maint_service = MaintenanceService(self.storage)
        self.cal_service = CalendarService()
        self._needs_restart = False  # Flag for restore command

    def run(self):
        print(f"\n📋 Smart Scheduler 2.0 ({self.cfg.preferences.get('storage_engine', 'json')})")
        print(f"Data: {self.cfg.data_dir}")
        print("Type 'help' for commands, 'quit' or Ctrl+Z to exit.\n")
        print("Status Icons: ○ = todo, ▶ = in progress, ⏳ = waiting, ✓ = done, ✗ = cancelled")
        
        while True:
            try:
                cmd = input("\n> ").strip()
                if not cmd: continue
                if cmd.lower() in ("quit", "exit"): break
                
                # Check if restart is needed (after restore)
                if self._needs_restart and cmd.lower() not in ("quit", "exit"):
                    print("\n⚠️  ERROR: You must restart the scheduler after restore!")
                    print("Type 'quit' to exit, then restart the scheduler.")
                    continue
                
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
        """Parse arguments into positional and options."""
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

def cmd_list(cli, args):
    """List projects and tasks with comprehensive detail.
    
    Usage:
        list                      List all projects (summary)
        list --all                List all projects with all tasks (default: hide done)
        list --all --show-done    List everything including completed tasks
        list projects             List only projects (summary)
        list tasks                List all tasks across all projects
        list tasks <project>      List tasks in specific project
    """
    pos, opts = cli._opts(args)
    
    show_done = "show-done" in opts or "show_done" in opts
    show_all = "all" in opts
    
    # Determine what to list
    what = pos[0] if pos else ("all" if show_all else "projects")
    
    if what == "projects" or (what == "all" and not show_all):
        # Summary view: Just list projects
        projects = cli.storage.load_all_projects()
        if not projects:
            return print("No projects.")
        
        print("\n=== PROJECTS ===\n")
        for p in projects:
            active_tasks = [t for t in p.tasks if t.status not in (TaskStatus.DONE, TaskStatus.CANCELLED)]
            done_tasks = [t for t in p.tasks if t.status in (TaskStatus.DONE, TaskStatus.CANCELLED)]
            
            print(f"[{p.name}]")
            print(f"  Slug: {p.slug}")
            if p.description:
                print(f"  Description: {p.description}")
            print(f"  Tasks: {len(active_tasks)} active, {len(done_tasks)} done, {len(p.tasks)} total")
            if p.contacts:
                print(f"  Contacts: {len(p.contacts)}")
            print()
    
    elif what == "all":
        # Detailed hierarchical view
        projects = cli.storage.load_all_projects()
        if not projects:
            return print("No projects.")
        
        print("\n=== ALL PROJECTS & TASKS ===")
        if not show_done:
            print("(Hiding completed tasks. Use --show-done to see all)\n")
        
        for p in projects:
            # Filter tasks based on show_done flag
            if show_done:
                tasks = p.tasks
            else:
                tasks = [t for t in p.tasks if t.status not in (TaskStatus.DONE, TaskStatus.CANCELLED)]
            
            print(f"\n[{p.name}] ({p.slug})")
            if p.description:
                print(f"  Description: {p.description}")
            
            if tasks:
                print(f"  Tasks ({len(tasks)}):")
                for t in tasks:
                    status_icon = t.status.icon
                    due_str = f" [Due: {t.due_date}]" if t.due_date else ""
                    tags_str = f" #{','.join(t.tags)}" if t.tags else ""
                    print(f"    {status_icon} {t.title} ({t.id}){due_str}{tags_str}")
                    if t.notes:
                        # Indent notes
                        for line in t.notes.split('\n'):
                            print(f"       Note: {line}")
            else:
                print(f"  Tasks: {len(p.tasks)} (all completed)" if p.tasks else "  Tasks: 0")
            
            if p.contacts:
                print(f"  Contacts ({len(p.contacts)}):")
                for c in p.contacts:
                    role_str = f" - {c.role}" if c.role else ""
                    print(f"    • {c.name} ({c.id}){role_str}")
            
            print()
    
    elif what == "tasks":
        # List tasks (all or for specific project)
        project_slug = pos[1] if len(pos) > 1 else None
        
        if project_slug:
            # Tasks for specific project
            p = cli.storage.load_project(project_slug)
            if not p:
                return print(f"Project '{project_slug}' not found")
            
            if show_done:
                tasks = p.tasks
            else:
                tasks = [t for t in p.tasks if t.status not in (TaskStatus.DONE, TaskStatus.CANCELLED)]
            
            if not tasks:
                return print(f"No {'active ' if not show_done else ''}tasks in '{p.name}'")
            
            print(f"\n=== TASKS IN {p.name} ===")
            if not show_done:
                print("(Hiding completed tasks. Use --show-done to see all)\n")
            
            for t in tasks:
                _print_task_detail(t)
        else:
            # All tasks across all projects
            projects = cli.storage.load_all_projects()
            all_tasks = []
            
            for p in projects:
                for t in p.tasks:
                    if show_done or t.status not in (TaskStatus.DONE, TaskStatus.CANCELLED):
                        t._project_slug = p.slug
                        t._project_name = p.name
                        all_tasks.append(t)
            
            if not all_tasks:
                return print("No tasks.")
            
            print(f"\n=== ALL TASKS ===")
            if not show_done:
                print("(Hiding completed tasks. Use --show-done to see all)\n")
            
            for t in all_tasks:
                project_str = f" [{t._project_name}]" if hasattr(t, '_project_name') else ""
                status_icon = t.status.icon
                due_str = f" [Due: {t.due_date}]" if t.due_date else ""
                print(f"  {status_icon} {t.title} ({t.id}){project_str}{due_str}")

def _print_task_detail(task):
    """Helper to print task with full details."""
    status_icon = task.status.icon
    print(f"\n  {status_icon} {task.title}")
    print(f"     ID:     {task.id}")
    print(f"     Status: {task.status.value}")
    if task.due_date:
        print(f"     Due:    {task.due_date}")
    if task.assignee:
        print(f"     Assign: {task.assignee}")
    if task.tags:
        print(f"     Tags:   {', '.join(task.tags)}")
    if task.notes:
        for line in task.notes.split('\n'):
            print(f"     Note:   {line}")
    if task.outcome:
        print(f"     Result: {task.outcome}")

def cmd_show(cli, args):
    """Show comprehensive details of a task, contact, or project.
    
    Usage:
        show <task_id>       Show full task details
        show <contact_id>    Show contact details  
        show <project_slug>  Show project details with all tasks/contacts
    """
    if not args:
        return print("Usage: show <task_id or contact_id or project_slug>")
    
    identifier = args[0]
    
    # Try as task ID (starts with 't')
    if identifier.startswith('t'):
        result = cli.task_service.find_task_by_id(identifier)
        if result:
            project, task = result
            print(f"\n{'='*60}")
            print(f"TASK: {task.title}")
            print(f"{'='*60}")
            print(f"ID:           {task.id}")
            print(f"Project:      {project.name} ({project.slug})")
            print(f"Status:       {task.status.value} {task.status.icon}")
            print(f"Created:      {task.created_at}")
            print(f"Updated:      {task.updated_at}")
            if task.due_date:
                print(f"Due Date:     {task.due_date}")
            if task.reminder_date:
                print(f"Reminder:     {task.reminder_date}")
            if task.assignee:
                print(f"Assignee:     {task.assignee}")
            if task.contact_id:
                print(f"Contact:      {task.contact_id}")
            if task.tags:
                print(f"Tags:         {', '.join(task.tags)}")
            if task.notes:
                print(f"\nNotes:")
                for line in task.notes.split('\n'):
                    print(f"  {line}")
            if task.outcome:
                print(f"\nOutcome:")
                for line in task.outcome.split('\n'):
                    print(f"  {line}")
            print(f"{'='*60}\n")
            return
    
    # Try as contact ID (starts with 'c')
    if identifier.startswith('c'):
        result = cli.task_service.find_contact_by_id(identifier)
        if result:
            project, contact = result
            print(f"\n{'='*60}")
            print(f"CONTACT: {contact.name}")
            print(f"{'='*60}")
            print(f"ID:           {contact.id}")
            print(f"Project:      {project.name} ({project.slug})")
            if contact.role:
                print(f"Role:         {contact.role}")
            if contact.email:
                print(f"Email:        {contact.email}")
            if contact.phone:
                print(f"Phone:        {contact.phone}")
            if contact.notes:
                print(f"\nNotes:")
                for line in contact.notes.split('\n'):
                    print(f"  {line}")
            print(f"{'='*60}\n")
            return
    
    # Try as project slug
    p = cli.storage.load_project(identifier)
    if p:
        print(f"\n{'='*60}")
        print(f"PROJECT: {p.name}")
        print(f"{'='*60}")
        print(f"Slug:         {p.slug}")
        if p.description:
            print(f"Description:  {p.description}")
        print(f"Created:      {p.created_at}")
        print(f"Updated:      {p.updated_at}")
        
        # Task summary
        active = [t for t in p.tasks if t.status not in (TaskStatus.DONE, TaskStatus.CANCELLED)]
        done = [t for t in p.tasks if t.status in (TaskStatus.DONE, TaskStatus.CANCELLED)]
        print(f"\nTasks:        {len(active)} active, {len(done)} done, {len(p.tasks)} total")
        
        if active:
            print("\nActive Tasks:")
            for t in active:
                due_str = f" [Due: {t.due_date}]" if t.due_date else ""
                print(f"  {t.status.icon} {t.title} ({t.id}){due_str}")
        
        if done:
            print("\nCompleted Tasks:")
            for t in done:
                print(f"  {t.status.icon} {t.title} ({t.id})")
        
        if p.contacts:
            print(f"\nContacts ({len(p.contacts)}):")
            for c in p.contacts:
                role_str = f" - {c.role}" if c.role else ""
                print(f"  • {c.name} ({c.id}){role_str}")
        
        print(f"{'='*60}\n")
        return
    
    print(f"Not found: {identifier}")

def cmd_cleanup(cli, args):
    """Delete all completed tasks and/or cancelled tasks.
    
    NOTE: This removes tasks with status='done' or status='cancelled'.
    It does NOT remove tasks based on any "confirmed" status - that doesn't exist.
    
    Usage:
        cleanup                      Show what would be deleted (dry run)
        cleanup --done               Delete all tasks marked status='done'
        cleanup --cancelled          Delete all tasks marked status='cancelled'
        cleanup --done --cancelled   Delete both done and cancelled tasks
        cleanup --execute            Actually perform the deletion (safer than --confirm)
    
    Safety: Always previews first. Use --execute to actually delete.
    """
    pos, opts = cli._opts(args)
    
    delete_done = "done" in opts
    delete_cancelled = "cancelled" in opts
    execute = "execute" in opts or "confirm" in opts  # Support both flags
    
    # If neither specified, delete both (but require execute flag)
    if not delete_done and not delete_cancelled:
        delete_done = True
        delete_cancelled = True
    
    # Collect tasks to delete
    to_delete = []
    projects = cli.storage.load_all_projects()
    
    for project in projects:
        for task in project.tasks:
            should_delete = False
            if delete_done and task.status == TaskStatus.DONE:
                should_delete = True
            if delete_cancelled and task.status == TaskStatus.CANCELLED:
                should_delete = True
            
            if should_delete:
                to_delete.append((project, task))
    
    if not to_delete:
        return print("No completed tasks to delete.")
    
    # Show what will be deleted
    print(f"\nFound {len(to_delete)} completed task(s) to delete:\n")
    for project, task in to_delete:
        print(f"  {task.status.icon} {task.title} ({task.id}) [{task.status.value}] from '{project.name}'")
    
    if not execute:
        print(f"\nDry run - no tasks deleted.")
        print(f"To actually delete, add --execute flag:")
        if delete_done and delete_cancelled:
            print(f"  cleanup --done --cancelled --execute")
        elif delete_done:
            print(f"  cleanup --done --execute")
        else:
            print(f"  cleanup --cancelled --execute")
        return
    
    # Confirm deletion
    response = input(f"\nPermanently delete {len(to_delete)} task(s)? (yes/no): ")
    if response.lower() != 'yes':
        return print("Deletion cancelled.")
    
    # Delete tasks
    deleted_count = 0
    for project, task in to_delete:
        project.tasks = [t for t in project.tasks if t.id != task.id]
        cli.storage.save_project(project)
        deleted_count += 1
    
    print(f"\n✓ Deleted {deleted_count} task(s).")

def cmd_new(cli, args):
    """Create a new project.
    
    Usage:
        new project <slug> <name> [--desc <description>]
    """
    if len(args) < 2 or args[0] != "project":
        return print("Usage: new project <slug> <name> [--desc <description>]")
    
    pos, opts = cli._opts(args[1:])
    if len(pos) < 2:
        return print("Usage: new project <slug> <name>")
    
    slug, name = pos[0], pos[1]
    cli.task_service.create_project(slug, name)
    
    if "desc" in opts or "description" in opts:
        desc = opts.get("desc") or opts.get("description")
        cli.task_service.update_project(slug, desc=desc)
    
    print(f"✓ Project '{name}' created with slug '{slug}'")

def cmd_add(cli, args):
    """Add a task or contact.
    
    Usage:
        add task <project_slug> <title> [--due <date>] [--note <text>] [--tags <tag1,tag2>]
        add contact <project_slug> <name> [--role <role>] [--email <email>] [--phone <phone>]
    """
    if len(args) < 2:
        return print("Usage: add task <project> <title> [options]\n"
                    "       add contact <project> <name> [options]")
    
    kind = args[0]
    if kind == "task":
        if len(args) < 3:
            return print("Usage: add task <project_slug> <title> [--due <date>] [--note <text>] [--tags <tag1,tag2>]")
        
        slug, title = args[1], args[2]
        pos, opts = cli._opts(args[3:])
        
        # Validate flags - catch common mistakes
        valid_task_flags = {'due', 'd', 'note', 'notes', 'tags', 'g'}
        invalid_flags = set(opts.keys()) - valid_task_flags
        
        if invalid_flags:
            # Specific helpful error for --desc
            if 'desc' in invalid_flags or 'description' in invalid_flags:
                return print("Error: --desc is not a valid option for tasks.\n"
                           "       Did you mean --note? (Use --note for task descriptions/notes)")
            else:
                invalid_list = ', '.join('--' + f for f in invalid_flags)
                return print(f"Error: Unknown option(s): {invalid_list}\n"
                           f"       Valid options: --due, --note, --tags")
        
        task = cli.task_service.add_task(
            slug, title,
            due=opts.get("due") or opts.get("d"),
            notes=opts.get("note") or opts.get("notes"),
            tags=opts.get("tags", "").split(",") if opts.get("tags") else None
        )
        print(f"✓ Task added: {task.title} ({task.id})")
    
    elif kind == "contact":
        if len(args) < 3:
            return print("Usage: add contact <project_slug> <name> [--role <role>] [--email <email>]")
        
        slug, name = args[1], args[2]
        pos, opts = cli._opts(args[3:])
        
        contact = cli.task_service.add_contact(
            slug, name,
            role=opts.get("role"),
            note=opts.get("note")
        )
        print(f"✓ Contact added: {contact.name} ({contact.id})")

def cmd_edit(cli, args):
    """Edit a task or project by ID.
    
    Usage:
        edit <task_id> [--title <title>] [--due <date>] [--note <text>] [--status <status>] [--tags <tags>]
        edit <project_slug> [--name <name>] [--desc <description>]
        
    Valid statuses: todo, in_progress, waiting, done, cancelled
    """
    if not args:
        return print("Usage: edit <task_id or project_slug> [options]\n"
                    "Task options: --title, --due, --note, --status, --tags\n"
                    "Project options: --name, --desc")
    
    identifier = args[0]
    pos, opts = cli._opts(args[1:])
    
    # Try as task ID
    if identifier.startswith('t'):
        result = cli.task_service.find_task_by_id(identifier)
        if result:
            project, task = result
            
            # Validate flags before processing
            valid_flags = {'title', 't', 'due', 'd', 'note', 'notes', 'status', 's', 'tags'}
            invalid_flags = set(opts.keys()) - valid_flags
            
            if invalid_flags:
                if 'desc' in invalid_flags or 'description' in invalid_flags:
                    return print("Error: --desc is not a valid option for tasks.\n"
                               "       Did you mean --note? (Use --note for task descriptions/notes)")
                else:
                    invalid_list = ', '.join('--' + f for f in invalid_flags)
                    return print(f"Error: Unknown option(s): {invalid_list}\n"
                               f"       Valid task options: --title, --due, --note, --status, --tags")
            
            updates = {}
            
            if "title" in opts or "t" in opts:
                updates["title"] = opts.get("title") or opts.get("t")
            if "due" in opts or "d" in opts:
                updates["due_date"] = opts.get("due") or opts.get("d")
            if "note" in opts or "notes" in opts:
                updates["notes"] = opts.get("note") or opts.get("notes")
            if "status" in opts or "s" in opts:
                updates["status"] = opts.get("status") or opts.get("s")
            if "tags" in opts:
                updates["tags"] = opts.get("tags").split(",")
            
            if not updates:
                return print("No updates specified. Use --title, --due, --note, --status, or --tags")
            
            cli.task_service.update_task(project.slug, task.id, **updates)
            print(f"✓ Task '{task.title}' updated.")
            return
    
    # Try as project slug
    p = cli.storage.load_project(identifier)
    if p:
        updates = {}
        if "name" in opts:
            updates["name"] = opts["name"]
        if "desc" in opts or "description" in opts:
            updates["desc"] = opts.get("desc") or opts.get("description")
        
        if not updates:
            return print("No updates specified. Use --name or --desc")
        
        cli.task_service.update_project(identifier, **updates)
        print(f"✓ Project '{p.name}' updated.")
        return
    
    print(f"Not found: {identifier}")

def cmd_delete(cli, args):
    """Delete a task or project by ID.
    
    Usage:
        delete <task_id>       Delete a task
        delete <project_slug>  Delete a project (and all its tasks)
    """
    if not args:
        return print("Usage: delete <task_id or project_slug>")
    
    identifier = args[0]
    
    # Try as task ID
    if identifier.startswith('t'):
        result = cli.task_service.find_task_by_id(identifier)
        if result:
            project, task = result
            confirm = input(f"Delete task '{task.title}' from '{project.name}'? (yes/no): ")
            if confirm.lower() == 'yes':
                cli.task_service.delete_task_by_id(identifier)
                print(f"✓ Task deleted.")
            else:
                print("Deletion cancelled.")
            return
    
    # Try as project
    p = cli.storage.load_project(identifier)
    if p:
        confirm = input(f"Delete project '{p.name}' and ALL its {len(p.tasks)} task(s)? (yes/no): ")
        if confirm.lower() == 'yes':
            if cli.task_service.delete_project(identifier):
                print(f"✓ Project '{identifier}' deleted.")
        else:
            print("Deletion cancelled.")
        return
    
    print(f"Not found: {identifier}")

def cmd_import_json(cli, args):
    """Import tasks, projects, or entire database from JSON.
    
    Usage:
        import-json <file>               Import from JSON file (auto-detect type)
        import-json <file> --to <project>   Import tasks to specific project
        import-json <file> --merge       Merge with existing data (don't replace)
        import-json <file> --dry-run     Preview without importing
    
    Import types (auto-detected from export_type field):
        - task: Add task to specified project or original project
        - contact: Add contact to specified project or original project
        - project: Create new project with all tasks/contacts
        - full_database: Import all projects (with merge or replace)
    
    Examples:
        import-json backup.json                    # Import whatever is in the file
        import-json task.json --to work            # Import task to 'work' project
        import-json project.json                   # Import entire project
        import-json full_backup.json               # Import all projects
        import-json full_backup.json --merge       # Merge with existing
        import-json backup.json --dry-run          # Preview only
    """
    import json
    from datetime import datetime
    
    pos, opts = cli._opts(args)
    
    if not pos:
        return print("Usage: import-json <file> [--to <project>] [--merge] [--dry-run]")
    
    filename = pos[0]
    target_project = opts.get("to")
    merge = "merge" in opts
    dry_run = "dry-run" in opts or "dry_run" in opts
    
    # Load JSON file
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return print(f"Error: File not found: {filename}")
    except json.JSONDecodeError as e:
        return print(f"Error: Invalid JSON file: {e}")
    except Exception as e:
        return print(f"Error reading file: {e}")
    
    # Validate required fields
    if "export_type" not in data:
        return print("Error: Invalid export file - missing 'export_type' field.\n"
                    "       This doesn't appear to be a valid scheduler export.")
    
    export_type = data["export_type"]
    
    if dry_run:
        print(f"\n{'='*60}")
        print("DRY RUN - No changes will be made")
        print(f"{'='*60}")
    
    # Route to appropriate import handler
    if export_type == "task":
        _import_task(cli, data, target_project, dry_run)
    elif export_type == "contact":
        _import_contact(cli, data, target_project, dry_run)
    elif export_type == "project":
        _import_project(cli, data, dry_run)
    elif export_type == "full_database":
        _import_full_database(cli, data, merge, dry_run)
    else:
        print(f"Error: Unknown export_type '{export_type}'")

def _import_task(cli, data, target_project, dry_run):
    """Import a single task."""
    from datetime import datetime
    
    if "task" not in data:
        return print("Error: Invalid task export - missing 'task' field")
    
    task_data = data["task"]
    source_project = data.get("project", {}).get("slug")
    
    # Determine target project
    if target_project:
        project_slug = target_project
    elif source_project:
        project_slug = source_project
    else:
        return print("Error: No target project specified and no source project in export.\n"
                    "       Use --to <project_slug> to specify target project.")
    
    # Check if project exists
    project = cli.storage.load_project(project_slug)
    if not project:
        return print(f"Error: Project '{project_slug}' not found.\n"
                    f"       Create it first with: new project {project_slug} \"Project Name\"")
    
    # Check for ID conflict
    existing_task = next((t for t in project.tasks if t.id == task_data["id"]), None)
    if existing_task:
        print(f"Warning: Task with ID {task_data['id']} already exists in project.")
        if not dry_run:
            response = input("Overwrite existing task? (yes/no): ")
            if response.lower() != 'yes':
                return print("Import cancelled.")
            # Remove existing task
            project.tasks = [t for t in project.tasks if t.id != task_data["id"]]
    
    # Create task from data
    # Use models that are already imported in the CLI module
    from scheduler.models import Task, TaskStatus
    
    # Convert status string to enum
    try:
        status = TaskStatus(task_data.get("status", "todo"))
    except ValueError:
        status = TaskStatus.TODO
    
    task = Task(
        id=task_data["id"],
        title=task_data["title"],
        status=status,
        assignee=task_data.get("assignee"),
        due_date=task_data.get("due_date"),
        reminder_date=task_data.get("reminder_date"),
        contact_id=task_data.get("contact_id"),
        tags=task_data.get("tags", []),
        notes=task_data.get("notes"),
        outcome=task_data.get("outcome"),
        created_at=task_data.get("created_at", datetime.now().isoformat()),
        updated_at=task_data.get("updated_at", datetime.now().isoformat())
    )
    
    if dry_run:
        print(f"\nWould import task:")
        print(f"  ID:      {task.id}")
        print(f"  Title:   {task.title}")
        print(f"  Status:  {task.status.value}")
        print(f"  Project: {project_slug}")
        return
    
    # Add task to project
    project.tasks.append(task)
    cli.storage.save_project(project)
    
    print(f"✓ Imported task '{task.title}' ({task.id}) to project '{project_slug}'")

def _import_contact(cli, data, target_project, dry_run):
    """Import a single contact."""
    if "contact" not in data:
        return print("Error: Invalid contact export - missing 'contact' field")
    
    contact_data = data["contact"]
    source_project = data.get("project", {}).get("slug")
    
    # Determine target project
    if target_project:
        project_slug = target_project
    elif source_project:
        project_slug = source_project
    else:
        return print("Error: No target project specified and no source project in export.\n"
                    "       Use --to <project_slug> to specify target project.")
    
    # Check if project exists
    project = cli.storage.load_project(project_slug)
    if not project:
        return print(f"Error: Project '{project_slug}' not found.")
    
    # Check for ID conflict
    existing = next((c for c in project.contacts if c.id == contact_data["id"]), None)
    if existing:
        print(f"Warning: Contact with ID {contact_data['id']} already exists.")
        if not dry_run:
            response = input("Overwrite? (yes/no): ")
            if response.lower() != 'yes':
                return print("Import cancelled.")
            project.contacts = [c for c in project.contacts if c.id != contact_data["id"]]
    
    from scheduler.models import Contact
    
    contact = Contact(
        id=contact_data["id"],
        name=contact_data["name"],
        phone=contact_data.get("phone"),
        email=contact_data.get("email"),
        role=contact_data.get("role"),
        notes=contact_data.get("notes")
    )
    
    if dry_run:
        print(f"\nWould import contact:")
        print(f"  ID:      {contact.id}")
        print(f"  Name:    {contact.name}")
        print(f"  Project: {project_slug}")
        return
    
    project.contacts.append(contact)
    cli.storage.save_project(project)
    
    print(f"✓ Imported contact '{contact.name}' ({contact.id}) to project '{project_slug}'")

def _import_project(cli, data, dry_run):
    """Import an entire project."""
    from datetime import datetime
    from scheduler.models import Task, Contact, Project, TaskStatus
    
    if "project" not in data:
        return print("Error: Invalid project export - missing 'project' field")
    
    proj_data = data["project"]
    slug = proj_data["slug"]
    
    # Check if project exists
    existing = cli.storage.load_project(slug)
    if existing:
        print(f"Warning: Project '{slug}' already exists.")
        if not dry_run:
            response = input("Overwrite entire project? (yes/no): ")
            if response.lower() != 'yes':
                return print("Import cancelled.")
    
    # Create project
    project = Project(
        slug=slug,
        name=proj_data["name"],
        description=proj_data.get("description", ""),
        created_at=proj_data.get("created_at", datetime.now().isoformat()),
        updated_at=proj_data.get("updated_at", datetime.now().isoformat())
    )
    
    # Import tasks
    for task_data in proj_data.get("tasks", []):
        try:
            status = TaskStatus(task_data.get("status", "todo"))
        except ValueError:
            status = TaskStatus.TODO
        
        task = Task(
            id=task_data["id"],
            title=task_data["title"],
            status=status,
            assignee=task_data.get("assignee"),
            due_date=task_data.get("due_date"),
            reminder_date=task_data.get("reminder_date"),
            contact_id=task_data.get("contact_id"),
            tags=task_data.get("tags", []),
            notes=task_data.get("notes"),
            outcome=task_data.get("outcome"),
            created_at=task_data.get("created_at", datetime.now().isoformat()),
            updated_at=task_data.get("updated_at", datetime.now().isoformat())
        )
        project.tasks.append(task)
    
    # Import contacts
    for contact_data in proj_data.get("contacts", []):
        contact = Contact(
            id=contact_data["id"],
            name=contact_data["name"],
            phone=contact_data.get("phone"),
            email=contact_data.get("email"),
            role=contact_data.get("role"),
            notes=contact_data.get("notes")
        )
        project.contacts.append(contact)
    
    if dry_run:
        print(f"\nWould import project:")
        print(f"  Slug:     {project.slug}")
        print(f"  Name:     {project.name}")
        print(f"  Tasks:    {len(project.tasks)}")
        print(f"  Contacts: {len(project.contacts)}")
        return
    
    cli.storage.save_project(project)
    
    print(f"✓ Imported project '{project.name}' ({project.slug})")
    print(f"  Tasks:    {len(project.tasks)}")
    print(f"  Contacts: {len(project.contacts)}")

def _import_full_database(cli, data, merge, dry_run):
    """Import entire database."""
    from datetime import datetime
    from scheduler.models import Task, Contact, Project, TaskStatus
    
    if "projects" not in data:
        return print("Error: Invalid database export - missing 'projects' field")
    
    projects_data = data["projects"]
    
    if not merge:
        print(f"Warning: This will REPLACE all existing data with {len(projects_data)} projects.")
        if not dry_run:
            response = input("Continue? Type 'yes' to confirm: ")
            if response != 'yes':
                return print("Import cancelled.")
    
    imported_count = 0
    skipped_count = 0
    
    for proj_data in projects_data:
        slug = proj_data["slug"]
        
        # Check if exists
        existing = cli.storage.load_project(slug)
        if existing and merge:
            print(f"Skipping existing project: {slug}")
            skipped_count += 1
            continue
        
        # Create project
        project = Project(
            slug=slug,
            name=proj_data["name"],
            description=proj_data.get("description", ""),
            created_at=proj_data.get("created_at", datetime.now().isoformat()),
            updated_at=proj_data.get("updated_at", datetime.now().isoformat())
        )
        
        # Import tasks
        for task_data in proj_data.get("tasks", []):
            try:
                status = TaskStatus(task_data.get("status", "todo"))
            except ValueError:
                status = TaskStatus.TODO
            
            task = Task(
                id=task_data["id"],
                title=task_data["title"],
                status=status,
                assignee=task_data.get("assignee"),
                due_date=task_data.get("due_date"),
                reminder_date=task_data.get("reminder_date"),
                contact_id=task_data.get("contact_id"),
                tags=task_data.get("tags", []),
                notes=task_data.get("notes"),
                outcome=task_data.get("outcome"),
                created_at=task_data.get("created_at", datetime.now().isoformat()),
                updated_at=task_data.get("updated_at", datetime.now().isoformat())
            )
            project.tasks.append(task)
        
        # Import contacts
        for contact_data in proj_data.get("contacts", []):
            contact = Contact(
                id=contact_data["id"],
                name=contact_data["name"],
                phone=contact_data.get("phone"),
                email=contact_data.get("email"),
                role=contact_data.get("role"),
                notes=contact_data.get("notes")
            )
            project.contacts.append(contact)
        
        if dry_run:
            print(f"  Would import: {project.name} ({len(project.tasks)} tasks)")
        else:
            cli.storage.save_project(project)
            print(f"  Imported: {project.name}")
        
        imported_count += 1
    
    if dry_run:
        print(f"\nDry run complete - would import {imported_count} project(s)")
        if merge and skipped_count > 0:
            print(f"Would skip {skipped_count} existing project(s)")
    else:
        print(f"\n✓ Imported {imported_count} project(s)")
        if merge and skipped_count > 0:
            print(f"  Skipped {skipped_count} existing project(s)")

def cmd_config(cli, args):
    """Show or modify configuration.
    
    Usage:
        config                    Show current configuration
        config location <path>    Move data to new location
        config reset              Reset to default configuration
    """
    if not args:
        print(f"\n{'='*60}")
        print("CONFIGURATION")
        print(f"{'='*60}")
        print(f"Data Directory: {cli.cfg.data_dir}")
        print(f"Config File:    {cli.cfg.config_path}")
        print(f"\nPreferences:")
        for key, value in cli.cfg.preferences.items():
            print(f"  {key}: {value}")
        print(f"{'='*60}\n")
        return

    action = args[0].lower()
    
    if action == "reset":
        print("\n⚠️  WARNING: This will reset configuration to defaults.")
        print(f"Current data directory: {cli.cfg.data_dir}")
        print(f"Default data directory: ~/.scheduler/")
        print("\nThis will:")
        print("  • Reset data_dir to default (~/.scheduler/)")
        print("  • Reset all preferences to defaults")
        print("  • NOT move or delete any data files")
        print("\nYour data will remain at the current location.")
        print("You'll need to manually move it if desired.")
        
        response = input("\nReset configuration? (yes/no): ")
        if response.lower() != 'yes':
            return print("Reset cancelled.")
        
        # Delete the config file to force defaults
        if cli.cfg.config_path.exists():
            cli.cfg.config_path.unlink()
            print(f"\n✓ Deleted config file: {cli.cfg.config_path}")
        
        # Reload with defaults
        cli.cfg.load()
        
        print("✓ Configuration reset to defaults")
        print(f"  Data Directory: {cli.cfg.data_dir}")
        print(f"  Storage Engine: {cli.cfg.preferences.get('storage_engine', 'json')}")
        print("\nRestart the scheduler for changes to take full effect.")
        return
    
    if action == "location" and len(args) > 1:
        import shutil
        
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
        print(f"\n✓ Moved {moved_count} items. Config updated.")

def cmd_backup(cli, args):
    """Create a backup of all data (read-only by default)."""
    import os
    import stat
    
    pos, opts = cli._opts(args)
    name = opts.get("name") or opts.get("bkup_name")
    compress = "compress" in opts
    allow_write = "writable" in opts  # Optional flag to keep writable
    
    path = cli.maint_service.backup(name, compress)
    
    if not allow_write:
        # Make backup read-only
        if path.is_file():
            # Single file (compressed backup)
            current_mode = path.stat().st_mode
            # Remove write permissions for user, group, and others
            read_only_mode = current_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
            path.chmod(read_only_mode)
            print(f"✓ Backup created at: {path} (read-only)")
        elif path.is_dir():
            # Directory backup - make all files read-only
            for root, dirs, files in os.walk(path):
                # Make directory readable and executable but not writable
                for d in dirs:
                    dir_path = Path(root) / d
                    current_mode = dir_path.stat().st_mode
                    read_only_mode = current_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
                    dir_path.chmod(read_only_mode)
                
                # Make files read-only
                for f in files:
                    file_path = Path(root) / f
                    current_mode = file_path.stat().st_mode
                    read_only_mode = current_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
                    file_path.chmod(read_only_mode)
            
            print(f"✓ Backup created at: {path} (read-only)")
    else:
        print(f"✓ Backup created at: {path} (writable)")


def cmd_restore(cli, args):
    """Restore data from a backup."""
    if not args:
        return print("Usage: restore <path>")
    
    print("\n⚠️  WARNING: Restore will replace ALL current data")
    print("Current data will be backed up to a temporary location.")
    print("\nIMPORTANT: After restore completes, you MUST restart the scheduler!")
    print("DO NOT use any commands after restore - just quit and restart.\n")
    
    response = input("Continue with restore? (yes/no): ")
    if response.lower() != 'yes':
        return print("Restore cancelled.")
    
    try:
        cli.maint_service.restore(args[0])
        print("✓ Restore successful.")
        print("\n" + "="*60)
        print("CRITICAL: You MUST restart the scheduler NOW!")
        print("="*60)
        print("\nSteps:")
        print("  1. Type 'quit' to exit")
        print("  2. Restart the scheduler")
        print("  3. Verify your data with 'list'")
        print("\n⚠️  DO NOT run any other commands before restarting!")
        print("⚠️  Running commands now will overwrite the restored data!")
        print("="*60)
        
        # Mark CLI as needing restart
        cli._needs_restart = True
        
    except Exception as e:
        print(f"✗ Restore failed: {e}")

def cmd_maintenance(cli, args):
    """Perform database maintenance."""
    pos, opts = cli._opts(args)
    if "vacuum" in opts or "optimize" in opts:
        cli.maint_service.optimize_database()
        print("✓ Database optimized.")

def cmd_export(cli, args):
    """Export data to various formats."""
    if len(args) < 2:
        return print("Usage: export <task_id or project_slug> <ics|json|csv>")
    
    identifier, fmt = args[0], args[1]
    
    if fmt == "ics":
        if identifier.startswith('t'):
            result = cli.task_service.find_task_by_id(identifier)
            if result:
                project, task = result
                content = cli.cal_service.generate_file_content(task)
                fname = f"{project.slug}_{task.id}.ics"
                Path(fname).write_text(content, encoding="utf-8")
                print(f"✓ Exported to {fname}")
                return
        
        print(f"Task not found: {identifier}")

def cmd_export_json(cli, args):
    """Export tasks, projects, or entire database to JSON.
    
    Usage:
        export-json <task_id>        Export single task to JSON
        export-json <project_slug>   Export project with all tasks/contacts
        export-json --all            Export entire database
        export-json --all --output <file>  Specify output filename
    
    Examples:
        export-json t30b0a           Creates t30b0a.json
        export-json myproject        Creates myproject.json
        export-json --all            Creates scheduler_export_YYYYMMDD_HHMMSS.json
        export-json --all --output full_backup.json
    """
    import json
    from datetime import datetime
    
    pos, opts = cli._opts(args)
    
    # Check for conflicting arguments
    if "all" in opts and pos:
        return print("Error: Cannot use --all with a specific ID.\n"
                    "Usage: export-json --all  (for everything)\n"
                    "   OR: export-json <task_id or project_slug>  (for specific item)")
    
    # Export entire database
    if "all" in opts:
        projects = cli.storage.load_all_projects()
        
        data = {
            "export_date": datetime.now().isoformat(),
            "export_type": "full_database",
            "storage_engine": cli.cfg.preferences.get("storage_engine", "json"),
            "data_directory": str(cli.cfg.data_dir),
            "projects": []
        }
        
        for p in projects:
            project_data = {
                "slug": p.slug,
                "name": p.name,
                "description": p.description,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
                "tasks": [],
                "contacts": []
            }
            
            for t in p.tasks:
                task_data = {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status.value,
                    "assignee": t.assignee,
                    "due_date": t.due_date,
                    "reminder_date": t.reminder_date,
                    "contact_id": t.contact_id,
                    "tags": t.tags,
                    "notes": t.notes,
                    "outcome": t.outcome,
                    "created_at": t.created_at,
                    "updated_at": t.updated_at
                }
                project_data["tasks"].append(task_data)
            
            for c in p.contacts:
                contact_data = {
                    "id": c.id,
                    "name": c.name,
                    "phone": c.phone,
                    "email": c.email,
                    "role": c.role,
                    "notes": c.notes
                }
                project_data["contacts"].append(contact_data)
            
            data["projects"].append(project_data)
        
        # Determine output filename
        if "output" in opts:
            filename = opts["output"]
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"scheduler_export_{timestamp}.json"
        
        # Write to file
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        total_tasks = sum(len(p["tasks"]) for p in data["projects"])
        total_contacts = sum(len(p["contacts"]) for p in data["projects"])
        
        print(f"\n✓ Exported full database to: {filename}")
        print(f"  Projects: {len(projects)}")
        print(f"  Tasks:    {total_tasks}")
        print(f"  Contacts: {total_contacts}")
        return
    
    # Export single task or project
    if not pos:
        return print("Usage: export-json <task_id or project_slug> OR export-json --all")
    
    identifier = pos[0]
    
    # Try as task ID
    if identifier.startswith('t'):
        result = cli.task_service.find_task_by_id(identifier)
        if result:
            project, task = result
            
            data = {
                "export_date": datetime.now().isoformat(),
                "export_type": "task",
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "status": task.status.value,
                    "assignee": task.assignee,
                    "due_date": task.due_date,
                    "reminder_date": task.reminder_date,
                    "contact_id": task.contact_id,
                    "tags": task.tags,
                    "notes": task.notes,
                    "outcome": task.outcome,
                    "created_at": task.created_at,
                    "updated_at": task.updated_at
                },
                "project": {
                    "slug": project.slug,
                    "name": project.name
                }
            }
            
            filename = opts.get("output", f"{task.id}.json")
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Exported task '{task.title}' to: {filename}")
            return
    
    # Try as contact ID
    if identifier.startswith('c'):
        result = cli.task_service.find_contact_by_id(identifier)
        if result:
            project, contact = result
            
            data = {
                "export_date": datetime.now().isoformat(),
                "export_type": "contact",
                "contact": {
                    "id": contact.id,
                    "name": contact.name,
                    "phone": contact.phone,
                    "email": contact.email,
                    "role": contact.role,
                    "notes": contact.notes
                },
                "project": {
                    "slug": project.slug,
                    "name": project.name
                }
            }
            
            filename = opts.get("output", f"{contact.id}.json")
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Exported contact '{contact.name}' to: {filename}")
            return
    
    # Try as project slug
    p = cli.storage.load_project(identifier)
    if p:
        data = {
            "export_date": datetime.now().isoformat(),
            "export_type": "project",
            "project": {
                "slug": p.slug,
                "name": p.name,
                "description": p.description,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
                "tasks": [],
                "contacts": []
            }
        }
        
        for t in p.tasks:
            task_data = {
                "id": t.id,
                "title": t.title,
                "status": t.status.value,
                "assignee": t.assignee,
                "due_date": t.due_date,
                "reminder_date": t.reminder_date,
                "contact_id": t.contact_id,
                "tags": t.tags,
                "notes": t.notes,
                "outcome": t.outcome,
                "created_at": t.created_at,
                "updated_at": t.updated_at
            }
            data["project"]["tasks"].append(task_data)
        
        for c in p.contacts:
            contact_data = {
                "id": c.id,
                "name": c.name,
                "phone": c.phone,
                "email": c.email,
                "role": c.role,
                "notes": c.notes
            }
            data["project"]["contacts"].append(contact_data)
        
        filename = opts.get("output", f"{p.slug}.json")
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Exported project '{p.name}' to: {filename}")
        print(f"  Tasks:    {len(data['project']['tasks'])}")
        print(f"  Contacts: {len(data['project']['contacts'])}")
        return
    
    print(f"Not found: {identifier}")

def cmd_help(cli, args):
    """Show comprehensive help documentation."""
    if not args:
        print(f"""
{'='*70}
SMART SCHEDULER 2.0 - COMPREHENSIVE COMMAND REFERENCE
{'='*70}

STATUS ICONS:
  ○ = todo         Task is pending/not started
  ▶ = in_progress  Task is actively being worked on
  ⏳ = waiting      Task is blocked/waiting for something
  ✓ = done         Task is completed
  ✗ = cancelled    Task was cancelled/abandoned

LISTING & VIEWING:
  list                      Quick project summary
  list --all                Show all projects with tasks (hides completed)
  list --all --show-done    Show everything including completed tasks
  list projects             Same as 'list'
  list tasks                List all tasks across all projects
  list tasks <project>      List tasks in specific project
  
  show <id>                 Show full details of task/contact/project

CREATING:
  new project <slug> <name> [--desc <text>]
                            Create a new project
  
  add task <project> <title> [--due <date>] [--note <text>] [--tags <t1,t2>]
                            Add a task to a project
  
  add contact <project> <name> [--role <role>] [--email <email>]
                            Add a contact to a project

EDITING:
  edit <task_id> [--title <title>] [--due <date>] [--note <text>] 
                 [--status <status>] [--tags <tag1,tag2>]
                            Edit a task (no project needed!)
  
  edit <project> [--name <name>] [--desc <description>]
                            Edit a project

DELETING:
  delete <task_id>          Delete a task (with confirmation)
  delete <project>          Delete a project and all its tasks
  
  cleanup                   Show completed tasks (dry run)
  cleanup --done            Delete all tasks with status='done'
  cleanup --cancelled       Delete all tasks with status='cancelled'  
  cleanup --execute         Actually perform the deletion

EXPORTING:
  export <id> ics           Export task to calendar format
  
  export-json <task_id>     Export task to JSON file
  export-json <project>     Export project to JSON file
  export-json --all         Export entire database to JSON
  export-json --all --output <file>
                            Export to specific filename

IMPORTING:
  import-json <file>        Import from JSON file (auto-detect type)
  import-json <file> --to <project>
                            Import task/contact to specific project
  import-json <file> --merge
                            Merge with existing (don't replace)
  import-json <file> --dry-run
                            Preview without importing

MAINTENANCE:
  backup [--name <n>]       Create a backup (read-only by default)
  backup --writable         Create a writable backup
  restore <path>            Restore from backup
  maintenance --optimize    Optimize database
  config                    Show configuration
  config location <path>    Move data directory
  config reset              Reset to default configuration

UTILITY:
  export <id> <format>      Export to ICS/JSON/CSV
  help [command]            Show this help or command-specific help
  quit                      Exit scheduler

{'='*70}

EXAMPLES:

  # List everything with full details
  list --all
  
  # List everything including completed tasks
  list --all --show-done
  
  # Add a task
  add task myproject "Fix bug #123" --due tomorrow --tags bug,urgent
  
  # Edit a task (no project needed!)
  edit t30b0a --note "Updated specs from client" --status in_progress
  
  # Show full task details
  show t30b0a
  
  # Delete completed tasks (preview first)
  cleanup
  cleanup --done --cancelled --execute
  
  # Create and configure project
  new project work "Work Tasks" --desc "Professional projects"
  edit work --desc "Updated description"

{'='*70}

For command-specific help: help <command>
Example: help edit, help list, help cleanup
""")
    else:
        # Command-specific help
        cmd = args[0].lower()
        help_docs = {
            "list": """
LIST - Display projects and tasks

Usage:
  list                      Quick project summary
  list --all                All projects with tasks (hides completed)
  list --all --show-done    Everything including completed tasks
  list projects             Project summary only
  list tasks                All tasks across all projects
  list tasks <project>      Tasks in specific project

Examples:
  list --all               # Detailed view, hides completed
  list --all --show-done   # Show everything
  list tasks work          # Tasks in 'work' project
""",
            "show": """
SHOW - Display full details

Usage:
  show <task_id>       Full task details with all fields
  show <contact_id>    Contact information
  show <project_slug>  Project with all tasks and contacts

Examples:
  show t30b0a          # Show task details
  show c5f9a2          # Show contact
  show myproject       # Show project with all tasks
""",
            "edit": """
EDIT - Modify tasks or projects

Usage:
  edit <task_id> [options]
    Options: --title, --due, --note, --status, --tags
  
  edit <project_slug> [options]
    Options: --name, --desc

Valid statuses: todo, in_progress, waiting, done, cancelled

Examples:
  edit t30b0a --note "Client called with update"
  edit t30b0a --due tomorrow --status in_progress
  edit t30b0a --title "New title" --tags urgent,bug
  edit myproject --name "Updated Name" --desc "New description"
""",
            "cleanup": """
CLEANUP - Delete completed tasks in bulk

Usage:
  cleanup                      Preview (dry run) - shows what would be deleted
  cleanup --done               Delete tasks with status='done'
  cleanup --cancelled          Delete tasks with status='cancelled'
  cleanup --done --cancelled   Delete both done and cancelled
  cleanup --execute            Actually delete (requires 'yes' confirmation)

Note: This deletes tasks based on their STATUS field:
  - status='done'      Tasks marked as completed
  - status='cancelled' Tasks marked as cancelled/abandoned

There is NO "confirmed" status. The valid statuses are:
  todo, in_progress, waiting, done, cancelled

Safety:
  1. Run without --execute to preview what will be deleted
  2. Add --execute and type 'yes' at prompt to actually delete

Examples:
  cleanup                              # Preview all completed tasks
  cleanup --done --execute             # Delete only 'done' tasks
  cleanup --done --cancelled --execute # Delete all completed
""",
            "add": """
ADD - Create new tasks or contacts

Usage:
  add task <project> <title> [--due <date>] [--note <text>] [--tags <t1,t2>]
  add contact <project> <name> [--role <role>] [--email <email>]

Examples:
  add task work "Deploy website" --due "2026-03-01" --tags deploy,urgent
  add task work "Fix bug" --note "Issue reported by client"
  add contact work "John Doe" --role "Client" --email "john@example.com"
""",
            "config": """
CONFIG - View and modify configuration

Usage:
  config                    Show current configuration
  config location <path>    Move data to new location
  config reset              Reset to default configuration

Examples:
  config                                    # View current settings
  config location ~/Documents/scheduler     # Move data directory
  config location /mnt/external/scheduler   # Move to external drive
  config reset                              # Reset to defaults

Reset behavior:
  • Deletes config file to restore defaults
  • Reverts data_dir to ~/.scheduler/
  • Resets all preferences to defaults
  • Does NOT move or delete existing data files
  • Requires typing 'yes' to confirm
  • Restart scheduler after reset

Default configuration:
  Data Directory: ~/.scheduler/
  Storage Engine: json
"""
        }
        
        help_text = help_docs.get(cmd, f"No detailed help available for '{cmd}'")
        print(help_text)

_COMMANDS = {
    "list": cmd_list,
    "show": cmd_show,
    "new": cmd_new,
    "add": cmd_add,
    "edit": cmd_edit,
    "delete": cmd_delete,
    "cleanup": cmd_cleanup,
    "backup": cmd_backup,
    "restore": cmd_restore,
    "maintenance": cmd_maintenance,
    "export": cmd_export,
    "export-json": cmd_export_json,
    "import-json": cmd_import_json,
    "config": cmd_config,
    "help": cmd_help,
}

def main():
    CLI().run()
