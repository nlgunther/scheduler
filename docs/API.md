# Smart Scheduler 2.0 - API Documentation

Complete command reference with all flags and options.

---

## Command Index

- [list](#list) - Display projects and tasks
- [show](#show) - Show detailed information
- [new](#new) - Create projects
- [add](#add) - Add tasks and contacts
- [edit](#edit) - Modify tasks and projects
- [delete](#delete) - Remove tasks and projects
- [cleanup](#cleanup) - Bulk delete completed tasks
- [export-json](#export-json) - Export to JSON format
- [export](#export) - Export to other formats
- [backup](#backup) - Create backups
- [restore](#restore) - Restore from backups
- [config](#config) - View/modify configuration
- [help](#help) - Display help

---

## list

Display projects and tasks with various levels of detail.

### Syntax

```bash
list
list --all
list --all --show-done
list projects
list tasks
list tasks <project_slug>
```

### Options

| Flag | Description |
|------|-------------|
| `--all` | Show detailed hierarchical view with all tasks |
| `--show-done` | Include completed tasks (normally hidden) |

### Examples

```bash
# Quick project summary
list

# Detailed view (hides completed)
list --all

# Show everything including completed
list --all --show-done

# List all tasks across all projects
list tasks

# Tasks in specific project
list tasks myproject
```

### Output

```
=== ALL PROJECTS & TASKS ===
(Hiding completed tasks. Use --show-done to see all)

[Work Projects] (work)
  Description: Professional tasks and projects
  Tasks (3):
    ▶ Deploy website (t5a2b3) [Due: 2026-02-28] #deploy,urgent
    ○ Fix bug #123 (t7c4d5) #bug
    ⏳ Waiting on client (t9e1f2)

[Personal] (personal)
  Tasks (2):
    ○ Buy groceries (t3a1b2)
    ○ Call dentist (t4c5d6) [Due: 2026-03-01]
```

---

## show

Display comprehensive details of a task, contact, or project.

### Syntax

```bash
show <task_id>
show <contact_id>
show <project_slug>
```

### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `task_id` | string | Task ID starting with 't' (e.g., t30b0a) |
| `contact_id` | string | Contact ID starting with 'c' (e.g., c5a2b3) |
| `project_slug` | string | Project identifier (e.g., myproject) |

### Examples

```bash
show t30b0a      # Show task
show c5a2b3      # Show contact
show myproject   # Show project
```

### Output (Task)

```
============================================================
TASK: Mountain View CC
============================================================
ID:           t30b0a
Project:      Schedule payments (scheduled_payments)
Status:       todo ○
Created:      2026-02-20T10:30:00
Updated:      2026-02-25T14:22:00
Due Date:     2026-03-31

Notes:
  email from jpatterson @mvccvt.com 2026-02-25 with specs
============================================================
```

---

## new

Create a new project.

### Syntax

```bash
new project <slug> <name> [--desc <description>]
```

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `slug` | string | Yes | Unique project identifier (no spaces) |
| `name` | string | Yes | Display name (can have spaces, use quotes) |

### Options

| Flag | Type | Description |
|------|------|-------------|
| `--desc <text>` | string | Project description |
| `--description <text>` | string | Alias for --desc |

### Examples

```bash
# Simple project
new project work "Work Tasks"

# With description
new project website "Website Redesign" --desc "Q1 2026 redesign project"

# Multi-word names need quotes
new project client-acme "ACME Corp Projects"
```

---

## add

Add tasks or contacts to a project.

### Syntax

```bash
add task <project_slug> <title> [options]
add contact <project_slug> <name> [options]
```

### Task Options

| Flag | Type | Description |
|------|------|-------------|
| `--due <date>` | string | Due date (natural language or ISO) |
| `-d <date>` | string | Alias for --due |
| `--note <text>` | string | Task notes |
| `--notes <text>` | string | Alias for --note |
| `--tags <tag1,tag2>` | string | Comma-separated tags (no spaces) |

### Contact Options

| Flag | Type | Description |
|------|------|-------------|
| `--role <text>` | string | Person's role |
| `--email <email>` | string | Email address |
| `--phone <phone>` | string | Phone number |
| `--note <text>` | string | Contact notes |

### Examples

```bash
# Basic task
add task work "Deploy website"

# With due date (ISO format)
add task work "Fix bug" --due 2026-03-15

# With natural language date
add task work "Team meeting" --due tomorrow

# With tags and notes
add task work "Client presentation" --due "march 15" --tags meeting,client --note "Prepare slides"

# Full example
add task work "Deploy feature" --due "next friday" --tags deploy,urgent --note "Deploy to production"

# Add contact
add contact work "John Doe" --role "Client" --email "john@example.com" --phone "555-1234"
```

---

## edit

Modify tasks or projects by ID. **No project slug needed for tasks!**

### Syntax

```bash
edit <task_id> [options]
edit <project_slug> [options]
```

### Task Options

| Flag | Type | Description |
|------|------|-------------|
| `--title <text>` | string | Change task title |
| `-t <text>` | string | Alias for --title |
| `--due <date>` | string | Change due date |
| `-d <date>` | string | Alias for --due |
| `--status <status>` | string | Change status (see below) |
| `-s <status>` | string | Alias for --status |
| `--note <text>` | string | Update notes (replaces existing) |
| `--notes <text>` | string | Alias for --note |
| `--tags <tag1,tag2>` | string | Update tags (replaces existing) |

### Valid Status Values

| Status | Meaning |
|--------|---------|
| `todo` | Not started / pending |
| `in_progress` | Actively being worked on |
| `waiting` | Blocked / waiting |
| `done` | Completed |
| `cancelled` | Abandoned |

**Note**: There is NO "confirmed" status. Only use the values listed above.

### Project Options

| Flag | Type | Description |
|------|------|-------------|
| `--name <text>` | string | Change project name |
| `--desc <text>` | string | Change description |
| `--description <text>` | string | Alias for --desc |

### Examples

```bash
# Change status
edit t30b0a --status in_progress
edit t30b0a --status done

# Update due date
edit t30b0a --due tomorrow
edit t30b0a --due "march 31"
edit t30b0a --due 2026-04-15

# Add/update notes
edit t30b0a --note "Met with client, updated requirements"

# Change title
edit t30b0a --title "New task title"

# Update tags
edit t30b0a --tags urgent,bug,backend

# Multiple updates
edit t30b0a --status in_progress --due tomorrow --note "Starting work today"

# Edit project
edit myproject --name "Updated Name"
edit myproject --desc "New description for project"
```

---

## delete

Delete tasks or projects with confirmation.

### Syntax

```bash
delete <task_id>
delete <project_slug>
```

### Confirmation

Both task and project deletion require typing "yes" at the confirmation prompt.

### Examples

```bash
# Delete task
delete t30b0a
Delete task 'Mountain View CC' from 'Schedule payments'? (yes/no): yes
✓ Task deleted.

# Delete project
delete myproject
Delete project 'My Project' and ALL its 15 task(s)? (yes/no): yes
✓ Project 'myproject' deleted.
```

---

## cleanup

Bulk delete completed tasks based on their status.

### Syntax

```bash
cleanup                      # Preview only (dry run)
cleanup --done               # Delete 'done' tasks
cleanup --cancelled          # Delete 'cancelled' tasks
cleanup --done --cancelled   # Delete both
cleanup --execute            # Actually perform deletion
```

### Options

| Flag | Description |
|------|-------------|
| `--done` | Target tasks with status='done' |
| `--cancelled` | Target tasks with status='cancelled' |
| `--execute` | Actually delete (requires typing "yes") |

**Note**: "cleanup" deletes tasks based on their STATUS field:
- status='done' - Completed tasks
- status='cancelled' - Cancelled/abandoned tasks

There is NO "confirmed" status. If you see a "confirmed" status somewhere, it's an error.

### Safety

1. Run without `--execute` to preview what will be deleted
2. Add `--execute` flag to enable deletion
3. Confirm with "yes" when prompted

### Examples

```bash
# Preview all completed tasks
cleanup
Found 5 completed task(s) to delete:
  ✓ Old task (t12345) [done] from 'Work'
  ✗ Cancelled (t67890) [cancelled] from 'Personal'

Dry run - no tasks deleted.
To actually delete, add --execute flag:
  cleanup --done --cancelled --execute

# Delete only 'done' tasks
cleanup --done --execute
Permanently delete 3 task(s)? (yes/no): yes
✓ Deleted 3 task(s).

# Delete both done and cancelled
cleanup --done --cancelled --execute
```

---

## export-json

Export tasks, projects, or entire database to JSON format.

### Syntax

```bash
export-json <task_id>
export-json <project_slug>
export-json <contact_id>
export-json --all
export-json --all --output <filename>
```

### Options

| Flag | Type | Description |
|------|------|-------------|
| `--all` | flag | Export entire database |
| `--output <file>` | string | Specify output filename |

### Output Format

#### Task Export
```json
{
  "export_date": "2026-02-25T14:30:00",
  "export_type": "task",
  "task": {
    "id": "t30b0a",
    "title": "Mountain View CC",
    "status": "todo",
    "due_date": "2026-03-31",
    "notes": "email from jpatterson...",
    "tags": [],
    "created_at": "2026-02-20T10:30:00",
    "updated_at": "2026-02-25T14:22:00"
  },
  "project": {
    "slug": "scheduled_payments",
    "name": "Schedule payments to make."
  }
}
```

#### Project Export
```json
{
  "export_date": "2026-02-25T14:30:00",
  "export_type": "project",
  "project": {
    "slug": "work",
    "name": "Work Tasks",
    "description": "Professional projects",
    "created_at": "2026-01-15T09:00:00",
    "updated_at": "2026-02-25T14:30:00",
    "tasks": [
      {
        "id": "t5a2b3",
        "title": "Deploy website",
        "status": "in_progress",
        ...
      }
    ],
    "contacts": [
      {
        "id": "c5a2b3",
        "name": "John Doe",
        "role": "Client",
        ...
      }
    ]
  }
}
```

#### Full Database Export
```json
{
  "export_date": "2026-02-25T14:30:00",
  "export_type": "full_database",
  "storage_engine": "json",
  "data_directory": "/path/to/data",
  "projects": [
    {
      "slug": "work",
      "name": "Work Tasks",
      "tasks": [...],
      "contacts": [...]
    },
    ...
  ]
}
```

### Examples

```bash
# Export single task
export-json t30b0a
✓ Exported task 'Mountain View CC' to: t30b0a.json

# Export project
export-json myproject
✓ Exported project 'My Project' to: myproject.json
  Tasks:    15
  Contacts: 3

# Export entire database
export-json --all
✓ Exported full database to: scheduler_export_20260225_143022.json
  Projects: 5
  Tasks:    47
  Contacts: 8

# Export with custom filename
export-json --all --output my_backup.json
✓ Exported full database to: my_backup.json
  Projects: 5
  Tasks:    47
  Contacts: 8
```

### Use Cases

- **Inspection**: View raw data structure
- **Backup**: Create portable backups
- **Analysis**: Import into spreadsheets or data tools
- **Migration**: Transfer data between systems
- **Debugging**: Examine data structure issues

---

## export

Export to other formats (currently ICS for calendar).

### Syntax

```bash
export <task_id> ics
```

### Examples

```bash
export t30b0a ics
✓ Exported to scheduled_payments_t30b0a.ics
```

---

## backup

Create a backup of all scheduler data.

### Syntax

```bash
backup
backup --name <backup_name>
backup --compress
```

### Options

| Flag | Type | Description |
|------|------|-------------|
| `--name <text>` | string | Custom backup name |
| `--compress` | flag | Compress backup (tar.gz) |

### Examples

```bash
# Simple backup
backup
✓ Backup created at: /path/to/backups/backup_20260225_143000.tar.gz

# Named backup
backup --name before_cleanup
✓ Backup created at: /path/to/backups/before_cleanup.tar.gz
```

---

## restore

Restore data from a backup file.

### Syntax

```bash
restore <path_to_backup>
```

### Examples

```bash
restore /path/to/backup.tar.gz
✓ Restore successful.
```

---

## config

View or modify configuration.

### Syntax

```bash
config
config location <new_path>
```

### Examples

```bash
# View configuration
config
============================================================
CONFIGURATION
============================================================
Data Directory: /home/user/.local/share/scheduler
Config File:    /home/user/.config/scheduler/config.yaml

Preferences:
  storage_engine: json
============================================================

# Move data directory
config location /new/path/to/data
Moving data...
  Source: /old/path
  Dest:   /new/path
  Moved: scheduler.db
  Moved: projects
✓ Moved 2 items. Config updated.
```

---

## help

Display help information.

### Syntax

```bash
help
help <command>
```

### Examples

```bash
# General help
help

# Command-specific help
help edit
help cleanup
help export-json
```

---

## Natural Language Date Parsing

All date fields (`--due`, etc.) support natural language input.

### Supported Formats

| Example | Result | Description |
|---------|--------|-------------|
| `today` | Current date | Today's date |
| `tomorrow` | +1 day | Tomorrow |
| `yesterday` | -1 day | Yesterday |
| `+3` | +3 days | 3 days from now |
| `+14` | +14 days | 2 weeks from now |
| `monday` | Next Monday | Upcoming Monday |
| `friday` | Next Friday | Upcoming Friday |
| `"next tuesday"` | Next week Tuesday | Tuesday of next week |
| `"in 3 days"` | +3 days | 3 days from now |
| `"in 2 weeks"` | +14 days | 2 weeks from now |
| `"in 1 month"` | ~+30 days | Approximately 1 month |
| `"march 15"` | March 15 | March 15 of current/next year |
| `"jan 5"` | January 5 | January 5 of current/next year |
| `2026-12-25` | Dec 25, 2026 | ISO format |

### Notes

- Multi-word expressions need quotes: `--due "next friday"`
- If a date has passed this year, assumes next year: `"jan 5"` in February → next January
- Weekday names without "next" mean the upcoming occurrence

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (exception occurred) |

---

## File Locations

### Default Data Directory

- **Linux/Mac**: `~/.local/share/scheduler/`
- **Windows**: `%APPDATA%\scheduler\`

### Structure

```
scheduler/
├── projects/              # Project JSON files
│   ├── work.json
│   ├── personal.json
│   └── myproject.json
├── scheduler.db          # SQLite database (if using)
└── exports/              # Exported files
    └── backups/          # Backup files
```

---

## Error Messages

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Project not found" | Project slug doesn't exist | Check `list projects` for valid slugs |
| "Task not found" | Task ID doesn't exist | Check `list tasks` for valid IDs |
| "Not found: <id>" | ID doesn't match any task/project | Verify ID with `list --all --show-done` |
| "Invalid status" | Status value not recognized | Use: todo, in_progress, waiting, done, cancelled |

---

## Performance Notes

- **Global ID Lookup**: Scans all projects, ~1ms for 100 projects with 100 tasks each
- **Large Exports**: `export-json --all` can take several seconds for >1000 tasks
- **Cleanup**: Scales linearly with number of completed tasks

---

## Version

**Smart Scheduler 2.0**  
Last Updated: February 25, 2026
