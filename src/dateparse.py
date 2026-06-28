"""규칙 기반 날짜/시간 추출 (외부 라이브러리 없이 정규식만 사용).

한국어/영문 메일에서 흔한 표현을 처리한다:
  - 2026-06-30, 2026.06.30, 2026/6/30
  - 6월 30일, 6/30
  - 내일, 모레, 오늘
  - 오후 3시, 오후 3시 30분, 15:00, 3:00 PM, 3pm
완벽한 자연어 처리는 아니며, '제안'을 만들기 위한 휴리스틱이다.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

# (시작 위치, datetime, 시간 정보 포함 여부)
_FoundDate = tuple[int, date]
_FoundTime = tuple[int, int, int]  # (위치, 시, 분)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _find_dates(text: str, today: date) -> list[_FoundDate]:
    found: list[_FoundDate] = []

    # YYYY-MM-DD / YYYY.MM.DD / YYYY/MM/DD
    for m in re.finditer(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})", text):
        d = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            found.append((m.start(), d))

    # 6월 30일 (연도 생략 시 올해, 이미 지난 날짜면 내년)
    for m in re.finditer(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", text):
        month, day = int(m.group(1)), int(m.group(2))
        d = _safe_date(today.year, month, day)
        if d:
            if d < today:
                d = _safe_date(today.year + 1, month, day) or d
            found.append((m.start(), d))

    # MM/DD (연도 없음). 위 YYYY/MM/DD 와 겹치지 않도록 앞에 숫자가 없을 때만.
    for m in re.finditer(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", text):
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            d = _safe_date(today.year, month, day)
            if d:
                if d < today:
                    d = _safe_date(today.year + 1, month, day) or d
                found.append((m.start(), d))

    # 상대 표현
    for keyword, delta in (("오늘", 0), ("내일", 1), ("모레", 2)):
        for m in re.finditer(keyword, text):
            found.append((m.start(), today + timedelta(days=delta)))

    return found


def _find_times(text: str) -> list[_FoundTime]:
    found: list[_FoundTime] = []

    # 오전/오후 H시 [M분]
    for m in re.finditer(r"(오전|오후)?\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?", text):
        ampm, hour, minute = m.group(1), int(m.group(2)), int(m.group(3) or 0)
        if ampm == "오후" and hour < 12:
            hour += 12
        if ampm == "오전" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            found.append((m.start(), hour, minute))

    # HH:MM [AM/PM]
    for m in re.finditer(r"(?<!\d)(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)?", text):
        hour, minute = int(m.group(1)), int(m.group(2))
        ampm = (m.group(3) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            found.append((m.start(), hour, minute))

    # 3pm / 9am (콜론 없이)
    for m in re.finditer(r"(?<!\d)(\d{1,2})\s*(am|pm|AM|PM)(?!\w)", text):
        hour = int(m.group(1))
        ampm = m.group(2).lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23:
            found.append((m.start(), hour, 0))

    return found


def extract_datetimes(text: str, today: date | None = None) -> list[datetime]:
    """텍스트에서 (날짜 + 가능하면 가장 가까운 시간)을 결합한 datetime 목록을 만든다."""
    today = today or datetime.now().date()
    if not text:
        return []

    dates = _find_dates(text, today)
    times = _find_times(text)
    if not dates:
        return []

    results: list[datetime] = []
    seen: set[datetime] = set()
    for pos, d in dates:
        # 같은 날짜 표현에서 가장 가까운(위치 차가 작은) 시간을 붙인다.
        best_time: _FoundTime | None = None
        best_dist = 60  # 60자 이내의 시간만 같은 일정으로 간주
        for tpos, hh, mm in times:
            dist = abs(tpos - pos)
            if dist < best_dist:
                best_dist = dist
                best_time = (tpos, hh, mm)

        if best_time:
            dt = datetime(d.year, d.month, d.day, best_time[1], best_time[2])
        else:
            dt = datetime(d.year, d.month, d.day, 0, 0)

        if dt not in seen:
            seen.add(dt)
            results.append(dt)

    results.sort()
    return results
