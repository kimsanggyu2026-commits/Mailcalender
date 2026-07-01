"""분석 결과를 Markdown 요약 보고서로 만든다."""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from src.models import EmailAnalysis, SuggestedEvent

_IMPORTANCE_LABEL = {"high": "🔴 높음", "medium": "🟡 보통", "low": "⚪ 낮음"}


def _fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return "(날짜 미상)"
    return dt.strftime("%Y-%m-%d %H:%M")


def _fmt_event(ev: SuggestedEvent) -> str:
    when = ev.start.strftime("%Y-%m-%d") if ev.all_day else ev.start.strftime("%Y-%m-%d %H:%M")
    return f"{when} — {ev.title}"


def build_report(analyses: list[EmailAnalysis]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(analyses)
    cat_counts = Counter(a.category for a in analyses)
    high = [a for a in analyses if a.importance == "high"]
    action = [a for a in analyses if a.action_required]
    all_events = [ev for a in analyses for ev in a.events]

    lines: list[str] = []
    lines.append("# 📬 메일 요약 보고서")
    lines.append("")
    lines.append(f"- 생성 시각: **{now}**")
    lines.append(f"- 분석한 메일: **{total}통**")
    lines.append(f"- 주요(높음) 메일: **{len(high)}통**")
    lines.append(f"- 액션 필요: **{len(action)}통**")
    lines.append(f"- 추출된 일정 후보: **{len(all_events)}건**")
    lines.append("")

    # 카테고리 분포
    lines.append("## 📂 분류 현황")
    lines.append("")
    lines.append("| 카테고리 | 메일 수 |")
    lines.append("| --- | ---: |")
    for category, count in cat_counts.most_common():
        lines.append(f"| {category} | {count} |")
    lines.append("")

    # 주요 메일
    lines.append("## ⭐ 주요 메일 요약")
    lines.append("")
    if not high:
        lines.append("_중요도 '높음'으로 분류된 메일이 없습니다._")
        lines.append("")
    for a in high:
        _append_email_block(lines, a)

    # 액션 필요 (주요 메일과 중복 가능 — 별도 체크리스트로 제공)
    lines.append("## ✅ 액션 필요 체크리스트")
    lines.append("")
    if not action:
        lines.append("_회신/확인이 필요한 메일이 감지되지 않았습니다._")
    else:
        for a in action:
            lines.append(
                f"- [ ] **{a.email.subject}** — {a.email.sender} "
                f"({_IMPORTANCE_LABEL[a.importance]})"
            )
    lines.append("")

    # 일정 제안
    lines.append("## 🗓️ 일정 제안 (캘린더에 추가 검토)")
    lines.append("")
    if not all_events:
        lines.append("_메일에서 날짜/시간을 감지하지 못했습니다._")
        lines.append("")
    else:
        lines.append("아래 일정 후보를 검토 후 캘린더에 추가하세요. "
                     "`output/events.ics` 파일을 캘린더에서 '가져오기'하면 한 번에 등록됩니다.")
        lines.append("")
        lines.append("| 일시 | 일정 | 출처 메일 |")
        lines.append("| --- | --- | --- |")
        for ev in sorted(all_events, key=lambda e: e.start):
            when = ev.start.strftime("%Y-%m-%d") if ev.all_day else ev.start.strftime("%Y-%m-%d %H:%M")
            lines.append(f"| {when} | {ev.title} | {ev.source_subject} |")
        lines.append("")

    # 전체 목록
    lines.append("## 📋 전체 메일 (중요도순)")
    lines.append("")
    lines.append("| 중요도 | 카테고리 | 제목 | 발신자 | 받은 시각 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for a in analyses:
        subject = a.email.subject.replace("|", "\\|")
        sender = a.email.sender.replace("|", "\\|")
        lines.append(
            f"| {_IMPORTANCE_LABEL[a.importance]} | {a.category} | {subject} "
            f"| {sender} | {_fmt_dt(a.email.date)} |"
        )
    lines.append("")

    return "\n".join(lines)


def build_telegram_summary(analyses: list[EmailAnalysis], max_len: int = 3500) -> str:
    """텔레그램 메시지용 간결한 요약 (HTML parse_mode 기준)."""
    import html

    def esc(s: str) -> str:
        return html.escape(s)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(analyses)
    high = [a for a in analyses if a.importance == "high"]
    action = [a for a in analyses if a.action_required]
    all_events = sorted(
        (ev for a in analyses for ev in a.events), key=lambda e: e.start
    )

    parts: list[str] = []
    parts.append(f"📬 <b>메일 요약</b>  ({esc(now)})")
    parts.append(
        f"총 {total}통 · 주요 {len(high)}통 · 액션 {len(action)}통 · 일정 {len(all_events)}건"
    )

    if high:
        parts.append("\n⭐ <b>주요 메일</b>")
        for a in high[:5]:
            parts.append(f"• <b>{esc(a.email.subject)}</b> — {esc(a.email.sender)}")
            parts.append(f"  {esc(a.summary)}")

    if action:
        parts.append("\n✅ <b>액션 필요</b>")
        for a in action[:8]:
            parts.append(f"• {esc(a.email.subject)} ({_IMPORTANCE_LABEL[a.importance]})")

    if all_events:
        parts.append("\n🗓️ <b>일정 제안</b>")
        for ev in all_events[:10]:
            when = (
                ev.start.strftime("%Y-%m-%d")
                if ev.all_day
                else ev.start.strftime("%Y-%m-%d %H:%M")
            )
            parts.append(f"• {esc(when)} — {esc(ev.title)}")

    text = "\n".join(parts)
    if len(text) > max_len:
        text = text[:max_len].rsplit("\n", 1)[0] + "\n…(이하 생략, 첨부 보고서 참고)"
    return text


def _append_email_block(lines: list[str], a: EmailAnalysis) -> None:
    lines.append(f"### {a.email.subject}")
    lines.append("")
    lines.append(f"- 발신자: {a.email.sender} `<{a.email.sender_email}>`")
    lines.append(f"- 받은 시각: {_fmt_dt(a.email.date)}")
    lines.append(f"- 분류: {a.category} · 중요도: {_IMPORTANCE_LABEL[a.importance]} (점수 {a.importance_score})")
    lines.append(f"- 요약: {a.summary}")
    if a.events:
        lines.append(f"- 감지된 일정: {', '.join(_fmt_event(ev) for ev in a.events)}")
    lines.append("")
