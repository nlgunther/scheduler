# Smart Scheduler 2.0 - Command Cheatsheet

Quick reference for common commands.

---

## Status Icons & Values

| Icon | Status | Use in --status flag |
|------|--------|---------------------|
| ○ | todo | `--status todo` |
| ▶ | in progress | `--status in_progress` |
| ⏳ | waiting | `--status waiting` |
| ✓ | done | `--status done` |
| ✗ | cancelled | `--status cancelled` |

**Note**: There is NO "confirmed" status. Only use the 5 values above.

---

## Viewing

```bash
list                    # Project summary
list --all              # Detailed view (hides completed)
list --all --show-done  # Show everything
list tasks              # All tasks
list tasks work         # Tasks in 'work' project

show t30b0a             # Task details
show work               # Project details
```

---

## Creating

```bash
# Project
new project work "Work Tasks" --desc "Description"

# Task
add task work "Title" --due tomorrow --tags urgent,bug

# Contact
add contact work "Name" --role "Client" --email "email@example.com"
```

---

## Editing

```bash
# Change status
edit t30b0a --status in_progress
edit t30b0a --status done

# Update due date
edit t30b0a --due tomorrow
edit t30b0a --due "next friday"
edit t30b0a --due 2026-03-31

# Add notes
edit t30b0a --note "Updated requirements from client"

# Multiple changes
edit t30b0a --status in_progress --due tomorrow --note "Starting today"

# Edit project
edit work --name "New Name" --desc "New description"
```

---

## Deleting

```bash
delete t30b0a           # Delete task
delete work             # Delete project

# Bulk cleanup
cleanup                              # Preview
cleanup --done --execute             # Delete done tasks
cleanup --cancelled --execute        # Delete cancelled
cleanup --done --cancelled --execute # Delete all completed
```

---

## Exporting

```bash
# JSON export
export-json t30b0a                   # Single task
export-json work                     # Project
export-json --all                    # Full database
export-json --all --output backup.json

# Calendar export
export t30b0a ics
```

---

## Natural Language Dates

```bash
--due today
--due tomorrow
--due +3                # 3 days from now
--due +14               # 2 weeks from now
--due monday            # Next Monday
--due "next friday"     # Friday of next week
--due "in 3 days"
--due "in 2 weeks"
--due "march 15"
--due 2026-12-25       # ISO format
```

---

## Common Workflows

### Daily Review
```bash
list --all
show t30b0a
edit t30b0a --status done
```

### Add Task with All Details
```bash
add task work "Deploy website" --due "march 15" --tags deploy,urgent --note "Production deployment"
```

### Weekly Cleanup
```bash
cleanup                              # Preview
export-json --all --output weekly_backup.json
cleanup --done --execute             # Actually delete
```

### Project Setup
```bash
new project website "Website Redesign" --desc "Q1 2026 project"
add task website "Design mockups" --due "march 1" --tags design
add task website "Frontend dev" --due "march 15" --tags dev
add contact website "Client Name" --role "PM" --email "client@example.com"
```

---

## Quick Reference Table

| Task | Command |
|------|---------|
| List all | `list --all` |
| Add task | `add task <project> "<title>" --due <date>` |
| Edit task | `edit <id> --status <status>` |
| Complete task | `edit <id> --status done` |
| Export task | `export-json <id>` |
| Delete task | `delete <id>` |
| Backup all | `export-json --all --output backup.json` |
| Clean up | `cleanup --done --execute` |

---

## Flag Reference

### add task flags
```bash
--due <date>         # Due date
--note <text>        # Notes
--tags <t1,t2>       # Tags (comma-separated)
```

### edit task flags
```bash
--title <text>       # Change title
--due <date>         # Change due date
--status <status>    # Change status (todo/in_progress/waiting/done/cancelled)
--note <text>        # Update notes
--tags <t1,t2>       # Update tags
```

### list flags
```bash
--all                # Detailed view
--show-done          # Include completed tasks
```

### cleanup flags
```bash
--done               # Target done tasks
--cancelled          # Target cancelled tasks
--execute            # Actually delete (requires yes)
```

### export-json flags
```bash
--all                # Export full database
--output <file>      # Custom filename
```

---

## Help Commands

```bash
help                 # Full reference
help edit            # Edit command help
help cleanup         # Cleanup command help
help export-json     # Export help
```

---

## Tips

1. **No project needed for edit**: `edit t30b0a` works anywhere
2. **Preview before deleting**: Run `cleanup` without `--execute` first
3. **Backup before cleanup**: `export-json --all` before deleting
4. **Multi-word dates need quotes**: `--due "next friday"`
5. **Tags have no spaces**: `--tags urgent,bug,deploy` not `urgent, bug`

---

## Common Mistakes

| Wrong | Right | Why |
|-------|-------|-----|
| `edit work/t30b0a` | `edit t30b0a` | No project needed anymore |
| `--status confirmed` | `--status done` | No "confirmed" status exists |
| `--due next friday` | `--due "next friday"` | Multi-word needs quotes |
| `--tags urgent, bug` | `--tags urgent,bug` | No spaces in tag list |
| `cleanup` | `cleanup --execute` | Need --execute to actually delete |

---

**Version**: 2.0  
**Last Updated**: February 25, 2026
