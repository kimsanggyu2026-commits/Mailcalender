"""규칙 기반 메일 분석: 분류 + 중요도 + 요약 + 일정 추출."""
from __future__ import annotations

import re

from src.dateparse import extract_datetimes
from src.models import EmailAnalysis, EmailMessage, SuggestedEvent

# ── 분류 규칙 ─────────────────────────────────────────────
# (카테고리 이름, 키워드 목록). 위에서부터 먼저 매칭되는 카테고리를 사용.
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("보안/계정", [
        "verify", "verification", "인증", "보안", "security", "비밀번호",
        "password", "otp", "로그인", "sign-in", "login", "2단계",
    ]),
    ("결제/청구", [
        "invoice", "청구", "결제", "payment", "receipt", "영수증", "구독",
        "subscription", "환불", "refund", "카드", "billing", "요금",
    ]),
    ("회의/약속", [
        "회의", "미팅", "meeting", "agenda", "안건", "통화", "call",
        "약속", "appointment", "면접", "interview", "일정", "schedule",
        "zoom", "google meet", "teams",
    ]),
    ("예약/주문", [
        "예약", "reservation", "booking", "주문", "order", "배송",
        "shipping", "delivery", "확정", "티켓", "ticket",
    ]),
    ("뉴스레터/프로모션", [
        "unsubscribe", "수신거부", "newsletter", "뉴스레터", "할인", "sale",
        "promotion", "광고", "쿠폰", "coupon", "이벤트", "%", "특가",
    ]),
]
DEFAULT_CATEGORY = "개인/기타"

# ── 중요도 규칙 ───────────────────────────────────────────
HIGH_KEYWORDS = [
    "긴급", "urgent", "asap", "immediately", "마감", "deadline", "오늘까지",
    "내일까지", "중요", "important", "승인", "approval", "최종", "확인 요청",
    "action required", "respond", "회신", "답장 바랍니다",
]
ACTION_KEYWORDS = [
    "요청", "request", "확인", "회신", "답장", "reply", "승인", "검토",
    "review", "제출", "submit", "작성", "응답", "참석", "rsvp", "확정",
]


def _classify(email: EmailMessage) -> tuple[str, list[str]]:
    haystack = f"{email.subject}\n{email.body}".lower()
    reasons: list[str] = []
    for category, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw.lower() in haystack:
                reasons.append(f"키워드 '{kw}' → {category}")
                return category, reasons
    return DEFAULT_CATEGORY, ["특정 키워드 없음 → 기타로 분류"]


def _is_newsletter(email: EmailMessage) -> bool:
    body = email.body.lower()
    return "unsubscribe" in body or "수신거부" in body


def _score_importance(
    email: EmailMessage, category: str
) -> tuple[str, int, list[str], bool]:
    haystack = f"{email.subject}\n{email.body}".lower()
    score = 50
    reasons: list[str] = []

    for kw in HIGH_KEYWORDS:
        if kw.lower() in haystack:
            score += 25
            reasons.append(f"긴급/중요 키워드 '{kw}'")
            break

    action_required = False
    for kw in ACTION_KEYWORDS:
        if kw.lower() in haystack:
            action_required = True
            score += 10
            reasons.append(f"액션 키워드 '{kw}'")
            break

    if category in ("회의/약속", "보안/계정"):
        score += 15
        reasons.append(f"중요 카테고리({category})")

    if category == "뉴스레터/프로모션" or _is_newsletter(email):
        score -= 35
        reasons.append("뉴스레터/프로모션 성격")

    score = max(0, min(100, score))
    if score >= 70:
        level = "high"
    elif score >= 40:
        level = "medium"
    else:
        level = "low"
    return level, score, reasons, action_required


_SIG_MARKERS = ("--", "—", "감사합니다", "thanks", "regards", "보낸 사람", "from:", "wrote:")


def _summarize(email: EmailMessage, max_chars: int = 220) -> str:
    """본문에서 인용/서명/공백을 정리하고 앞부분 핵심 문장을 발췌."""
    text = email.body or email.snippet or ""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):  # 인용된 이전 메일
            continue
        low = line.lower()
        if any(low.startswith(m) for m in _SIG_MARKERS):
            break
        lines.append(line)

    cleaned = " ".join(lines)
    cleaned = re.sub(r"https?://\S+", "[링크]", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        cleaned = email.snippet.strip()

    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rsplit(" ", 1)[0] + "…"
    return cleaned or "(요약할 본문 없음)"


def _extract_events(email: EmailMessage) -> list[SuggestedEvent]:
    text = f"{email.subject}\n{email.body}"
    events: list[SuggestedEvent] = []
    for dt in extract_datetimes(text):
        all_day = dt.hour == 0 and dt.minute == 0
        events.append(
            SuggestedEvent(
                title=email.subject,
                start=dt,
                all_day=all_day,
                source_subject=email.subject,
            )
        )
    return events


def analyze(email: EmailMessage) -> EmailAnalysis:
    category, cat_reasons = _classify(email)
    level, score, imp_reasons, action_required = _score_importance(email, category)
    return EmailAnalysis(
        email=email,
        category=category,
        importance=level,
        importance_score=score,
        reasons=cat_reasons + imp_reasons,
        summary=_summarize(email),
        action_required=action_required,
        events=_extract_events(email),
    )


def analyze_all(emails: list[EmailMessage]) -> list[EmailAnalysis]:
    analyses = [analyze(e) for e in emails]
    # 중요도 높은 순 → 점수 높은 순으로 정렬
    analyses.sort(key=lambda a: a.importance_score, reverse=True)
    return analyses
