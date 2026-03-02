# Smart Scheduler 2.0

A powerful command-line task and project management system with natural language date parsing, hierarchical project organization, and comprehensive export capabilities.

## Quick Start

```bash
# Start the scheduler
python -m scheduler.cli

# Create a project
> new project work "Work Tasks"

# Add a task  
> add task work "Deploy website" --due tomorrow --tags urgent,deploy

# List everything
> list --all

# Edit a task (no project needed!)
> edit t30b0a --status in_progress --note "Started deployment"

# Export to JSON
> export-json work
```

## Task Status Levels

| Icon | Status | Meaning |
|------|--------|---------|
| ○ | `todo` | Not started / pending |
| ▶ | `in_progress` | Actively being worked on |
| ⏳ | `waiting` | Blocked / waiting for something |
| ✓ | `done` | Completed successfully |
| ✗ | `cancelled` | Abandoned / no longer needed |

**Valid status values for `--status` flag:**
- `todo`
- `in_progress`
- `waiting`
- `done`
- `cancelled`

**Note**: There is NO "confirmed" status. Using `--status confirmed` will cause an error.

## Common Commands

### Viewing Data
```bash
list                    # Quick project summary
list --all              # Detailed view (hides completed tasks)
list --all --show-done  # Show everything including completed
list tasks              # All tasks across all projects
show t30b0a             # Full task details
```

### Creating
```bash
new project work "Work Tasks" --desc "Professional projects"
add task work "Task title" --due tomorrow --tags urgent
```

### Editing (No Project Needed!)
```bash
edit t30b0a --status in_progress
edit t30b0a --due "next friday"
edit t30b0a --note "Updated specs from client"
edit t30b0a --status done
```

### Exporting
```bash
export-json t30b0a              # Single task
export-json work                # Entire project  
export-json --all               # Full database
export-json --all --output backup.json
```

### Cleanup
```bash
cleanup                         # Preview completed tasks
cleanup --done --execute        # Delete 'done' tasks
cleanup --cancelled --execute   # Delete 'cancelled' tasks
```

## Natural Language Dates

```bash
--due today
--due tomorrow
--due +3                # 3 days from now
--due monday            # Next Monday
--due "next friday"
--due "in 2 weeks"
--due "march 15"
--due "2026-12-25"     # ISO format still works
```

## Getting Help

```bash
help                # Full command reference
help edit           # Command-specific help
help cleanup        # See cleanup options
```

For complete documentation, see [Full Documentation](FULL_README.md)
