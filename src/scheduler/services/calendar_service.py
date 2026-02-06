"""
services/calendar_service.py
Strategy Pattern implementation for Calendar Exports (ICS).
"""
from abc import ABC, abstractmethod
from typing import List
from datetime import datetime
from ..models import Task

class CalendarExportStrategy(ABC):
    @abstractmethod
    def export(self, task: Task) -> str:
        """Returns the string content of the calendar file."""
        pass

class IcsExportStrategy(CalendarExportStrategy):
    def export(self, task: Task) -> str:
        """Generates an ICS VEVENT block."""
        if not task.due_date:
            raise ValueError("Task has no due date.")
        
        dt_start = task.due_date.replace("-", "")
        
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Smart Scheduler//EN",
            "BEGIN:VEVENT",
            f"UID:{task.id}@scheduler.local",
            f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART;VALUE=DATE:{dt_start}",
            f"SUMMARY:{task.title}",
        ]
        
        desc = []
        if task.notes: desc.append(task.notes)
        if task.outcome: desc.append(f"Outcome: {task.outcome}")
        if desc:
            # FIX: Used raw strings (r"") to fix invalid escape sequence warning
            full_desc = "\\n".join(desc).replace(",", r"\,").replace(";", r"\;")
            lines.append(f"DESCRIPTION:{full_desc}")
            
        lines.append("END:VEVENT")
        lines.append("END:VCALENDAR")
        return "\n".join(lines)

class CalendarService:
    def __init__(self, strategy: CalendarExportStrategy = None):
        self.strategy = strategy or IcsExportStrategy()

    def generate_file_content(self, task: Task) -> str:
        return self.strategy.export(task)
