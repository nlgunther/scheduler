"""
Shared Infrastructure Library
==============================

Common utilities for Smart Scheduler and Manifest Manager.
"""

# Import from the SUBMODULE 'calendar'
from .calendar.ics_writer import CalendarEvent, ICSWriter

from .id_generator import generate_id, validate_id
from .locking import file_lock, LockTimeout

__version__ = "1.0.0"

__all__ = [
    "CalendarEvent", 
    "ICSWriter",
    "generate_id",
    "validate_id",
    "file_lock",
    "LockTimeout",
]