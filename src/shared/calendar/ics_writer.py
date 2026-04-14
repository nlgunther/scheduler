"""
shared/calendar/ics_writer.py
"""
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import List, Optional

@dataclass
class CalendarEvent:
    uid: str
    title: str
    start_date: datetime | date
    end_date: Optional[datetime | date] = None
    description: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    all_day: bool = False

    def to_ics(self) -> str:
        """Serialize event to VEVENT block."""
        # FIX 1: Use timezone-aware UTC instead of deprecated utcnow()
        dtstamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        
        lines = [
            "BEGIN:VEVENT",
            f"UID:{self.uid}",
            f"SUMMARY:{self._escape(self.title)}",
            f"DTSTAMP:{dtstamp}",
        ]
        
        # Handle Date Formatting
        if self.all_day:
            dt_str = self.start_date.strftime('%Y%m%d')
            lines.append(f"DTSTART;VALUE=DATE:{dt_str}")
            if self.end_date:
                end_str = self.end_date.strftime('%Y%m%d')
                lines.append(f"DTEND;VALUE=DATE:{end_str}")
        else:
            if isinstance(self.start_date, datetime):
                dt_str = self.start_date.strftime('%Y%m%dT%H%M%S')
                lines.append(f"DTSTART:{dt_str}")
            else:
                lines.append(f"DTSTART;VALUE=DATE:{self.start_date.strftime('%Y%m%d')}")

            if self.end_date:
                if isinstance(self.end_date, datetime):
                    end_str = self.end_date.strftime('%Y%m%dT%H%M%S')
                    lines.append(f"DTEND:{end_str}")
                else:
                    lines.append(f"DTEND;VALUE=DATE:{self.end_date.strftime('%Y%m%d')}")
            
        if self.description:
            lines.append(f"DESCRIPTION:{self._escape(self.description)}")
            
        if self.location:
            lines.append(f"LOCATION:{self._escape(self.location)}")
            
        if self.status:
            lines.append(f"STATUS:{self.status}")
            
        lines.append("END:VEVENT")
        return "\n".join(lines)

    @staticmethod
    def _escape(text: str) -> str:
        """Escape special characters for ICS."""
        if not text: return ""
        # FIX 2: Use double backslashes (\\) to avoid SyntaxWarning
        return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

class ICSWriter:
    def __init__(self, name="Export"):
        self.calendar_name = name
        self.events: List[CalendarEvent] = []

    def add_event(self, evt: CalendarEvent):
        self.events.append(evt)

    def to_string(self) -> str:
        """Return the complete ICS content as a string."""
        content = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Productivity Suite//Shared//EN",
            "CALSCALE:GREGORIAN",
            f"X-WR-CALNAME:{self.calendar_name}",
        ]
        
        for evt in self.events:
            content.append(evt.to_ics())
            
        content.append("END:VCALENDAR")
        return "\n".join(content)

    def write(self, fp: str):
        with open(fp, "w", encoding="utf-8") as f:
            f.write(self.to_string())
