# 📚 Developer API Documentation

Use these classes when building AI agents or external scripts that interact with the Scheduler.

## Access Patterns

Python

```
from scheduler.config import get_config
from scheduler.storage.factory import get_storage_engine
from scheduler.services.task_service import TaskService

# 1. Setup
cfg = get_config()
storage = get_storage_engine(cfg.data_dir, cfg.preferences["storage_engine"])
service = TaskService(storage)

# 2. Interact
projects = storage.load_all_projects()
task = service.add_task("garage", "New Item", due="tomorrow")
```

---

## 🧠 Services (`scheduler.services`)

### `TaskService`

The primary entry point for manipulating data.

- **`create_project(slug, name)`** -> `Project`

- **`add_task(slug, title, due=None, tags=None, notes=None)`** -> `Task`
  
  - *Parses natural language dates automatically.*

- **`update_task(slug, task_id, **kwargs)`** -> `Task`
  
  - *Supported kwargs*: `title`, `due_date`, `status`, `notes`, `tags`.

- **`add_contact(slug, name, role=None, note=None)`** -> `Contact`

### `MaintenanceService`

Handles system integrity and portability.

- **`backup(name=None, compress=False)`** -> `Path`
  
  - *Returns path to the backup artifact.*

- **`restore(source_path)`** -> `None`
  
  - *Raises `ValueError` if format is invalid.*

- **`optimize_database()`**
  
  - *Triggers `VACUUM` on SQLite or defragmentation on JSON.*

### `CalendarService`

- **`generate_file_content(task)`** -> `str`
  
  - *Returns formatted ICS string for the given task.*

---

## 💾 Storage (`scheduler.storage`)

### `StorageStrategy` (Abstract Base Class)

Implement this to create new backends (e.g., Postgres, S3).

- `load_project(slug)`

- `save_project(project)`

- `list_projects()`

- `rename_project(old, new)`

### `SqliteStorage`

- **Location**: `<data_dir>/scheduler.db`

- **Sidecars**: `<data_dir>/projects/<slug>/<task_id>.json`

- **Tables**: `projects`, `tasks`, `contacts`, `task_tags`

---

## 📦 Data Models (`scheduler.models`)

### `Task`

| Field      | Type         | Description                                                 |
| ---------- | ------------ | ----------------------------------------------------------- |
| `id`       | `str`        | Unique ID (e.g., `t82a9`)                                   |
| `status`   | `TaskStatus` | Enum: `todo`, `in_progress`, `waiting`, `done`, `cancelled` |
| `due_date` | `str`        | ISO 8601 (`YYYY-MM-DD`)                                     |
| `notes`    | `str`        | Long-form content (stored in sidecar)                       |

Export to Sheets

### `Project`

| Field   | Type         | Description                       |
| ------- | ------------ | --------------------------------- |
| `slug`  | `str`        | URL-safe identifier (Primary Key) |
| `tasks` | `List[Task]` | In-memory list of tasks           |
|         |              |                                   |
