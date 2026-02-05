#!/usr/bin/env python3
"""
Smart Scheduler - Test Suite (Refactored & Restored)
"""
import pytest
import json
import shutil
import tempfile
from pathlib import Path
from datetime import date, timedelta, datetime

# --- Imports from New Architecture ---
from scheduler_models import (
    Task, Project, Contact, TaskStatus, ModelEncoder
)
from scheduler_storage import (
    JsonFileStorage, SqliteStorage
)
from scheduler_services import (
    TaskService, ReminderService, CalendarService, DedupeService,
    ImportExportService, MergeResult, MergeConflict, ConflictResolution,
    parse_date, parse_time, parse_tags, validate_slug, ensure_unique_slug
)
from scheduler_cli import CLI

# --- Fixtures ---
@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    path = Path(d)
    yield path
    shutil.rmtree(d, ignore_errors=True)

@pytest.fixture(params=["json", "sqlite"])
def storage(request, temp_dir):
    if request.param == "json":
        return JsonFileStorage(temp_dir)
    return SqliteStorage(temp_dir)

@pytest.fixture
def service(storage):
    return TaskService(storage)

@pytest.fixture
def cli(temp_dir):
    return CLI(base_dir=temp_dir)

@pytest.fixture
def sample_project(service):
    return service.create_project("test", "Test Project")

# --- Tests: Helpers ---
class TestDateParsing:
    def test_iso_format(self):
        assert parse_date("2025-12-25") == "2025-12-25"
    def test_us_format(self):
        # The parser returns ISO string
        assert parse_date("12/25/2025") == "2025-12-25"
    def test_relative_dates(self):
        assert parse_date("today") == date.today().isoformat()
        assert parse_date("tomorrow") == (date.today() + timedelta(days=1)).isoformat()
    def test_offset_dates(self):
        assert parse_date("+3") == (date.today() + timedelta(days=3)).isoformat()
    def test_invalid_dates(self):
        assert parse_date("invalid") is None
    def test_whitespace(self):
        assert parse_date("  2025-12-25  ") == "2025-12-25"

class TestTimeParsing:
    def test_valid_time(self):
        assert parse_time("10:00") == "10:00"
        assert parse_time("9:30") == "09:30" # Should pad zero
    def test_invalid_time(self):
        assert parse_time("25:00") is None

class TestTagParsing:
    def test_parse_tags(self):
        assert parse_tags("Urgent, Home ") == ["urgent", "home"]

class TestSlugValidation:
    def test_valid(self):
        assert validate_slug("roof") is True
        assert validate_slug("move-me") is True
    def test_invalid(self):
        assert validate_slug("move_me") is False

# --- Tests: Models ---
class TestTask:
    def test_create(self):
        t = Task.create("Test")
        assert t.id is not None
        assert t.status == TaskStatus.TODO
    
    def test_has_tag(self):
        t = Task.create("Test", tags=["urgent"])
        assert t.has_tag("urgent") is True
        assert t.has_tag("home") is False

    def test_matches_search(self):
        t = Task.create("Call Mom")
        assert t.matches_search("mom") is True
        assert t.matches_search("dad") is False

class TestProject:
    def test_all_tags(self):
        p = Project("slug", "Name")
        p.tasks = [Task.create("1", tags=["a"]), Task.create("2", tags=["b", "a"])]
        assert p.all_tags == {"a", "b"}

class TestSerialization:
    def test_roundtrip(self):
        # New arch uses dataclasses + custom ModelEncoder
        t = Task.create("Test")
        # Ensure encoder works with json.dumps
        s = json.dumps(t, cls=ModelEncoder)
        assert "Test" in s

# --- Tests: Storage ---
class TestStorage:
    def test_save_load(self, storage):
        p = Project("test", "Test")
        p.tasks.append(Task.create("T1"))
        storage.save_project(p)
        
        loaded = storage.load_project("test")
        assert loaded.name == "Test"
        assert len(loaded.tasks) == 1

    def test_list_projects(self, storage):
        storage.save_project(Project("p1", "P1"))
        storage.save_project(Project("p2", "P2"))
        lst = storage.list_projects()
        assert "p1" in lst
        assert "p2" in lst

    def test_delete_project(self, storage):
        storage.save_project(Project("p1", "P1"))
        assert storage.delete_project("p1") is True
        assert storage.load_project("p1") is None

# --- Tests: Services ---
class TestTaskService:
    def test_create_project(self, service):
        p = service.create_project("new", "New")
        assert p.slug == "new"
        assert service.storage.load_project("new") is not None

    def test_create_duplicate_project(self, service):
        # Smart renaming
        p1 = service.create_project("test", "First")
        p2 = service.create_project("test", "Second")
        assert p2.slug != "test"
        assert p2.slug.startswith("test-")

    def test_add_task(self, service, sample_project):
        t = service.add_task("test", "Task 1", tags=["urgent"])
        assert t.title == "Task 1"
        assert t.has_tag("urgent")
        
        loaded = service.storage.load_project("test")
        assert len(loaded.tasks) == 1

    def test_search(self, service, sample_project):
        service.add_task("test", "Buy Milk")
        results = service.search("milk")
        assert len(results) == 1
        assert results[0][1].title == "Buy Milk"

class TestRenaming:
    def test_rename_project_success(self, service):
        service.create_project("old", "Old")
        service.rename_project("old", "new")
        assert service.storage.load_project("old") is None
        assert service.storage.load_project("new") is not None

class TestDedupeService:
    def test_merge_success(self):
        # We Mock this since it's a stub in the service currently
        tasks = [Task.create("T1")]
        res = DedupeService().try_merge(tasks)
        assert res.success

class TestImportExport:
    def test_export_json(self, service, sample_project):
        exporter = ImportExportService(service.storage)
        json_out = exporter.export_json("test")
        assert "Test Project" in json_out

