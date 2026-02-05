#!/usr/bin/env python3
"""
scheduler.py - Entry point for Smart Scheduler.
"""
import sys
from scheduler_cli import CLI, _COMMANDS

# Re-export key components for external scripts (like tests/migrations)
from scheduler_models import Task, Project, Contact, TaskStatus, ModelEncoder, task_from_dict, contact_from_dict, project_from_dict
from scheduler_storage import StorageStrategy, JsonFileStorage, SqliteStorage
from scheduler_services import (TaskService, ReminderService, CalendarService, DedupeService, ImportExportService, MergeConflict, MergeResult, ConflictResolution, parse_date, parse_time, parse_tags, validate_slug, ensure_unique_slug)
from scheduler_config import get_config

# Import shim for legacy tests
try:
    from scheduler_storage import JsonFileStorage as Storage
except ImportError:
    pass

def main():
    if len(sys.argv) > 1:
        cmd_name = sys.argv[1].lower()
        
        # 1. Config/Special commands (handled by legacy shim or direct invocation if needed)
        if cmd_name == "config":
            from scheduler_config import get_config
            cfg = get_config()
            if len(sys.argv) > 2 and sys.argv[2] == "set":
                if len(sys.argv) > 4:
                    if sys.argv[3] == "storage_engine":
                        cfg.set_preference("storage_engine", sys.argv[4])
                        cfg.save()
                        print(f"Storage engine set to {sys.argv[4]}")
                        return

        # 2. Standard CLI commands
        if cmd_name in _COMMANDS:
            try:
                cli = CLI()
                _COMMANDS[cmd_name](cli, sys.argv[2:])
            except Exception as e:
                print(f"Error: {e}")
            return
            
    # Interactive
    CLI().run()

if __name__ == "__main__":
    main()
