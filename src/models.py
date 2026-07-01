"""공통 데이터 모델."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EmailMessage:
    """Gmail에서 가져온 한 통의 메일."""

    id: str
    thread_id: str
    sender: str
    sender_email: str
    subject: str
    date: datetime | None
    snippet: str
    body: str


@dataclass
class SuggestedEvent:
    """메일에서 추출한 일정 제안."""

    title: str
    start: datetime
    end: datetime | None = None
    all_day: bool = False
    location: str | None = None
    source_subject: str = ""


@dataclass
class EmailAnalysis:
    """한 통의 메일에 대한 규칙 기반 분석 결과."""

    email: EmailMessage
    category: str
    importance: str  # "high" | "medium" | "low"
    importance_score: int
    reasons: list[str]
    summary: str
    action_required: bool
    events: list[SuggestedEvent] = field(default_factory=list)
