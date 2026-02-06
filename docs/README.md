# Smart Scheduler 2.0

A professional, hybrid task management system designed for power users and AI agents. It combines the speed of **SQLite** for indexing with the flexibility of **JSON** for content, wrapped in a robust Python CLI.

## 🚀 Features

* **Hybrid Storage**: SQLite for relationships/queries + JSON sidecars for long-form notes.
* **Agent Ready**: Clean Python API for AI agents to hook into.
* **Smart Parsing**: Natural language due dates (`tomorrow`, `friday`, `+3`).
* **Resilient**: Full backup/restore with compression support.
* **Calendar Integration**: Export tasks to `.ics` for Google Calendar/Outlook.
* **Portable**: Configurable data directory locations.

## 📦 Installation

This project is structured as a Python package.

```bash
# 1. Open your terminal in the project root
# 2. Install in editable mode
pip install -e .
```

⚡ Quick Start

```Bash
# 1. Initialize (runs automatically on first command)
schd config

# 2. Create a project
schd new project garage "Garage Cleanup"

# 3. Add tasks
schd add task garage "Buy shelves" -d friday -g shopping
schd add task garage "Sort boxes" -d +2

# 4. View your schedule
schd list
schd show garage
```

🛠 Configuration

The system defaults to ~/.scheduler. You can move this anywhere.

```Bash
# Switch to SQLite engine (Recommended)
schd config set storage_engine sqlite

# Move data to a cloud folder (Dropbox/Drive)
# WARNING: This moves your existing data to the new location automatically.
schd config location "D:/Dropbox/SchedulerData"

📂 Project Structure
Plaintext

smart-scheduler/
├── pyproject.toml       # Package definition
├── src/scheduler/       # Source code
│   ├── cli.py           # Command Line Interface
│   ├── models.py        # Data Classes (Task, Project)
│   ├── services/        # Business Logic (Task, Calendar, Maint)
│   └── storage/         # Storage Engines (SQLite, JSON)
└── README.md
```
