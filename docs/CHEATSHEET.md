# 📋 Smart Scheduler Cheatsheet

# 

# # 🟢 Core Commands

| Action            | Command                          | Example                                  |
| ----------------- | -------------------------------- | ---------------------------------------- |
| **New Project**   | `schd new project <slug> <name>` | `schd new project dev "Dev Work"`        |
| **List Projects** | `schd list`                      | `schd list`                              |
| **List All**      | `schd list --all`                | `schd list -a` (Shows inactive projects) |
| **Show Project**  | `schd show <slug>`               | `schd show dev`                          |
| **Show Task**     | `schd show <slug> <task_id>`     | `schd show dev t40a`                     |

Export to Sheets

## 📝 Task Management

| Action         | Command                              | Flags / Options                          |
| -------------- | ------------------------------------ | ---------------------------------------- |
| **Add Task**   | `schd add task <slug> <title>`       | `-d` (Due), `-g` (Tags), `--note`        |
| **Edit Task**  | `schd edit <slug> <id>`              | `-s` (Status), `-d` (Due), `--note`      |
| **Set Status** | `schd edit <slug> <id> -s <val>`     | `todo`, `in_progress`, `waiting`, `done` |
| **Add Note**   | `schd edit <slug> <id> --note "..."` | (Overwrites existing note)               |

Export to Sheets

*Example:*

Bash

```
schd add task dev "Fix bug" -d friday -g urgent
schd edit dev t40a -s in_progress --note "Started investigation"
```

## 👥 Contacts

| Action          | Command                                           |
| --------------- | ------------------------------------------------- |
| **Add Contact** | `schd add contact <slug> <name>`                  |
| **Add w/ Role** | `schd add contact <slug> <name> --role "Manager"` |

Export to Sheets

## 💾 Data & Maintenance

| Action          | Command                       | Description                           |
| --------------- | ----------------------------- | ------------------------------------- |
| **Backup**      | `schd backup`                 | Creates `.bkp` folder copy.           |
| **Zip Backup**  | `schd backup --compress`      | Creates `.bkp.zip` file.              |
| **Restore**     | `schd restore <path>`         | **WARNING**: Overwrites current data. |
| **Optimize**    | `schd maintenance --optimize` | Vacuums SQLite database.              |
| **Export ICS**  | `schd export <slug> ics <id>` | Creates `.ics` for Google Calendar.   |
| **Export JSON** | `schd export <slug> json`     | Dumps raw project data.               |

Export to Sheets

## ⚙️ Configuration

| Action          | Command                                 |
| --------------- | --------------------------------------- |
| **View Config** | `schd config`                           |
| **Move Data**   | `schd config location <path>`           |
| **Set Engine**  | `schd config set storage_engine sqlite` |

Export to Sheets

## ⌨️ Shortcuts

- **Exit**: `Ctrl+Z` (Windows) or `Ctrl+D` (Mac/Linux), or type `quit`.

- **Dates**: `today`, `tomorrow`, `monday`...`sunday`, `+3` (days).