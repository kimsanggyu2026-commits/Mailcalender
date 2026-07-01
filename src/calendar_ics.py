"""추출한 일정 제안을 .ics(iCalendar) 파일로 내보낸다.

생성된 파일은 Google/Apple/Outlook 캘린더에서 '가져오기'로 등록할 수 있다.
캘린더 쓰기 권한 없이 '제안'만 하는 방식이므로 안전하다.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from src.models import SuggestedEvent


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _uid(ev: SuggestedEvent) -> str:
    raw = f"{ev.title}-{ev.start.isoformat()}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{digest}@mailcalender"


def _fmt_local(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def build_ics(events: list[SuggestedEvent]) -> str:
    now_stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Mailcalender//Rule-based//KO",
        "CALSCALE:GREGORIAN",
    ]
    for ev in events:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{_uid(ev)}")
        lines.append(f"DTSTAMP:{now_stamp}")
        if ev.all_day:
            start = _fmt_date(ev.start)
            end = _fmt_date(ev.start + timedelta(days=1))
            lines.append(f"DTSTART;VALUE=DATE:{start}")
            lines.append(f"DTEND;VALUE=DATE:{end}")
        else:
            end_dt = ev.end or (ev.start + timedelta(hours=1))
            lines.append(f"DTSTART:{_fmt_local(ev.start)}")
            lines.append(f"DTEND:{_fmt_local(end_dt)}")
        lines.append(f"SUMMARY:{_escape(ev.title)}")
        if ev.location:
            lines.append(f"LOCATION:{_escape(ev.location)}")
        if ev.source_subject:
            lines.append(f"DESCRIPTION:{_escape('출처 메일: ' + ev.source_subject)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def write_ics(events: list[SuggestedEvent], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_ics(events))
