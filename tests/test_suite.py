"""
tests/test_suite.py
Comprehensive Test Suite for Smart Scheduler 2.0
"""
import pytest
import json
import shutil
import tempfile
import os
from pathlib import Path
from datetime import date, datetime, timedelta

# Adjust import based on package structure
# We assume the user is running from root via 'pytest'
from scheduler.models import Task, Project, TaskStatus
from scheduler.storage.factory import get_storage_engine
from scheduler.services.task_service import TaskService
from scheduler.services.maintenance_service import MaintenanceService
from scheduler.services.calendar_service import CalendarService
from scheduler.cli import CLI

# --- FIXTURES ---

@pytest.fixture
def temp_dir():
    """Provides a clean temporary directory for each test."""
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)

@pytest.fixture(params=["json", "sqlite"])
def storage(request, temp_dir):
    """
    Parameterized fixture to run tests against BOTH 
    JSON and SQLite engines automatically.
    """
    engine_type = request.param
    # Initialize storage engine
    store = get_storage_engine(temp_dir, engine_type)
    return store

@pytest.fixture
def task_service(storage):
    return TaskService(storage)

@pytest.fixture
def maint_service(storage):
    return MaintenanceService(storage)

@pytest.fixture
def cal_service():
    return CalendarService()

# --- 1. UNIT TESTS: PARSING & MODELS ---

def test_natural_language_dates():
    from scheduler.services.task_service import TaskService
    # We can test the helper directly if exposed, or via add_task
    # Accessing the hidden helper for unit testing if imported, 
    # otherwise we test via service behavior.
    
    # Let's test via Task creation which uses parsing logic
    today = date.today()
    
    t1 = Task.create("Test", due_date="today")
    # Note: Task.create doesn't parse, the Service does. 
    # We'll test this in the Service block.
    pass 

def test_task_status_enum():
    t = Task(id="1", title="Test", status=TaskStatus.TODO)
    assert t.status == TaskStatus.TODO
    assert t.is_active is True
    
    t.status = TaskStatus.DONE
    assert t.is_active is False
    assert t.status.icon == "✓"

# --- 2. INTEGRATION TESTS: STORAGE ENGINES ---

def test_storage_persistence(storage):
    """Verifies data survives a reload."""
    # 1. Save data
    p = Project(slug="work", name="Work Projects")
    t = Task.create("Meeting", due_date="2026-01-01")
    t.notes = "Important notes"
    p.tasks.append(t)
    storage.save_project(p)
    
    # 2. Reload data
    loaded = storage.load_project("work")
    assert loaded is not None
    assert loaded.name == "Work Projects"
    assert len(loaded.tasks) == 1
    assert loaded.tasks[0].title == "Meeting"
    
    # 3. Check Sidecar Data (Notes)
    assert loaded.tasks[0].notes == "Important notes"

def test_delete_project(storage):
    p = Project(slug="temp", name="Temp")
    storage.save_project(p)
    assert storage.load_project("temp") is not None
    
    storage.delete_project("temp")
    assert storage.load_project("temp") is None

def test_rename_project(storage):
    p = Project(slug="old", name="Old Name")
    t = Task.create("Task1")
    p.tasks.append(t)
    storage.save_project(p)
    
    storage.rename_project("old", "new")
    
    assert storage.load_project("old") is None
    new_p = storage.load_project("new")
    assert new_p is not None
    assert len(new_p.tasks) == 1

# --- 3. INTEGRATION TESTS: TASK SERVICE ---

def test_service_date_parsing(task_service):
    """Test 'tomorrow', '+3', etc."""
    task_service.create_project("dates", "Date Test")
    
    # Test 'tomorrow'
    t1 = task_service.add_task("dates", "T1", due="tomorrow")
    expected = (date.today() + timedelta(days=1)).isoformat()
    assert t1.due_date == expected
    
    # Test '+3'
    t2 = task_service.add_task("dates", "T2", due="+3")
    expected_3 = (date.today() + timedelta(days=3)).isoformat()
    assert t2.due_date == expected_3

def test_add_contact_to_project(task_service):
    task_service.create_project("crm", "CRM Test")
    c = task_service.add_contact("crm", "John Doe", role="Manager", note="VIP")
    
    loaded = task_service.storage.load_project("crm")
    assert len(loaded.contacts) == 1
    assert loaded.contacts[0].name == "John Doe"
    assert loaded.contacts[0].notes == "VIP"

def test_update_task_flow(task_service):
    task_service.create_project("dev", "Dev")
    t = task_service.add_task("dev", "Fix Bug")
    
    # Update Status
    updated = task_service.update_task("dev", t.id, status="in_progress")
    assert updated.status == TaskStatus.IN_PROGRESS
    
    # Update Notes & Tags
    updated = task_service.update_task("dev", t.id, notes="Fixed it", tags=["v1.0"])
    assert updated.notes == "Fixed it"
    assert "v1.0" in updated.tags

# --- 4. INTEGRATION TESTS: CALENDAR SERVICE ---

def test_ics_generation(cal_service):
    t = Task.create("Doctor Appt", due_date="2026-05-20")
    t.notes = "Bring ID"
    t.id = "t123"
    
    content = cal_service.generate_file_content(t)
    
    assert "BEGIN:VCALENDAR" in content
    assert "SUMMARY:Doctor Appt" in content
    assert "DTSTART;VALUE=DATE:20260520" in content
    assert "DESCRIPTION:Bring ID" in content

# --- 5. SYSTEM TESTS: BACKUP & RESTORE ---

def test_backup_and_restore(maint_service, task_service, temp_dir):
    # 1. Create Data
    task_service.create_project("main", "Main Project")
    task_service.add_task("main", "Critical Data")
    
    # 2. Create Backup
    backup_path = maint_service.backup("snapshot", compress=True)
    assert backup_path.exists()
    assert backup_path.suffix == ".zip"
    
    # 3. Corrupt Data (Delete Project)
    task_service.storage.delete_project("main")
    assert task_service.storage.load_project("main") is None
    
    # 4. Restore
    maint_service.restore(str(backup_path))
    
    # 5. Verify Restoration
    restored = task_service.storage.load_project("main")
    assert restored is not None
    assert restored.tasks[0].title == "Critical Data"

# --- 6. CLI SIMULATION ---

def test_cli_flow(temp_dir, monkeypatch, capsys):
    """
    Simulate user typing commands into the CLI.
    """
    # Initialize CLI with temp dir
    # We patch the config to point to temp_dir
    from scheduler.config import get_config
    cfg = get_config()
    cfg.set_data_dir(str(temp_dir))
    
    cli = CLI()
    
    # Helper to run command
    def run_cmd(cmd_str):
        cli._execute(cmd_str)

    # 1. Create Project
    run_cmd('new project alpha "Alpha Team"')
    
    # 2. Add Task
    run_cmd('add task alpha "Deploy App" -d tomorrow -g work')
    
    # 3. List
    run_cmd('list')
    out, err = capsys.readouterr()
    assert "[Alpha Team]" in out
    assert "Deploy App" in out
    
    # 4. Export ICS (Needs Task ID, we'll fuzzy find it)
    # We need to peek at the task ID generated
    p = cli.storage.load_project("alpha")
    tid = p.tasks[0].id
    
    run_cmd(f'export alpha ics {tid}')
    out, err = capsys.readouterr()
    assert ".ics" in out

