"""Notion에 결과를 누적 저장한다.

두 가지 모드 (둘 중 하나만 설정해도 동작):
  - NOTION_DATABASE_ID : 실행마다 DB에 '새 페이지(행)'를 만들어 일별로 누적 (권장)
  - NOTION_PAGE_ID     : 지정한 한 페이지 하단에 매번 '새 섹션'을 이어붙여 누적

공통:
  - NOTION_TOKEN : Notion 통합(Integration) 시크릿. 대상 DB/페이지를 이 통합과 '연결'해야 함.

설정이 없으면 조용히 건너뛴다.
"""
from __future__ import annotations

from datetime import datetime

import requests

from config import Config
from src.models import EmailAnalysis

_BASE = "https://api.notion.com/v1"
_VERSION = "2022-06-28"
_TIMEOUT = 30
_IMPORTANCE_LABEL = {"high": "🔴 높음", "medium": "🟡 보통", "low": "⚪ 낮음"}


def is_configured(config: Config) -> bool:
    return bool(config.notion_token and (config.notion_database_id or config.notion_page_id))


def _headers(config: Config) -> dict:
    return {
        "Authorization": f"Bearer {config.notion_token}",
        "Notion-Version": _VERSION,
        "Content-Type": "application/json",
    }


# ── 블록 빌더 ─────────────────────────────────────────────
def _rt(text: str, bold: bool = False) -> list[dict]:
    return [
        {
            "type": "text",
            "text": {"content": text[:2000]},
            "annotations": {"bold": bold},
        }
    ]


def _heading(text: str, level: int = 2) -> dict:
    return {
        "object": "block",
        "type": f"heading_{level}",
        f"heading_{level}": {"rich_text": _rt(text)},
    }


def _paragraph(text: str) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rt(text)}}


def _bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _rt(text)},
    }


def _todo(text: str) -> dict:
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {"rich_text": _rt(text), "checked": False},
    }


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def build_blocks(analyses: list[EmailAnalysis], header: str | None = None) -> list[dict]:
    total = len(analyses)
    high = [a for a in analyses if a.importance == "high"]
    action = [a for a in analyses if a.action_required]
    events = sorted((ev for a in analyses for ev in a.events), key=lambda e: e.start)

    blocks: list[dict] = []
    if header:
        blocks.append(_heading(header, level=2))
    blocks.append(
        _paragraph(
            f"총 {total}통 · 주요 {len(high)}통 · 액션 {len(action)}통 · 일정 {len(events)}건"
        )
    )

    if high:
        blocks.append(_heading("⭐ 주요 메일", level=3))
        for a in high[:10]:
            blocks.append(_bullet(f"{a.email.subject} — {a.email.sender}"))
            blocks.append(_paragraph(a.summary))

    if action:
        blocks.append(_heading("✅ 액션 필요", level=3))
        for a in action[:15]:
            blocks.append(_todo(f"{a.email.subject} ({_IMPORTANCE_LABEL[a.importance]})"))

    if events:
        blocks.append(_heading("🗓️ 일정 제안", level=3))
        for ev in events[:20]:
            when = (
                ev.start.strftime("%Y-%m-%d")
                if ev.all_day
                else ev.start.strftime("%Y-%m-%d %H:%M")
            )
            blocks.append(_bullet(f"{when} — {ev.title}"))

    return blocks


# ── API 호출 ──────────────────────────────────────────────
def _title_property_name(config: Config, database_id: str) -> str:
    """DB의 제목(title) 속성 이름을 찾는다 (기본은 'Name'이지만 다를 수 있음)."""
    try:
        resp = requests.get(
            f"{_BASE}/databases/{database_id}", headers=_headers(config), timeout=_TIMEOUT
        )
        if resp.status_code == 200:
            props = resp.json().get("properties", {})
            for name, meta in props.items():
                if meta.get("type") == "title":
                    return name
    except requests.RequestException:
        pass
    return "Name"


def _append_children(config: Config, block_id: str, blocks: list[dict]) -> bool:
    """블록을 100개씩 나눠 page/block 하위에 추가한다."""
    ok = True
    for i in range(0, len(blocks), 100):
        chunk = blocks[i : i + 100]
        resp = requests.patch(
            f"{_BASE}/blocks/{block_id}/children",
            headers=_headers(config),
            json={"children": chunk},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            print(f"  ⚠️ Notion 블록 추가 실패: {resp.status_code} {resp.text[:200]}")
            ok = False
            break
    return ok


def _create_database_page(config: Config, title: str, blocks: list[dict]) -> bool:
    db_id = config.notion_database_id
    title_prop = _title_property_name(config, db_id)
    payload = {
        "parent": {"database_id": db_id},
        "properties": {title_prop: {"title": _rt(title)}},
        "children": blocks[:100],
    }
    resp = requests.post(
        f"{_BASE}/pages", headers=_headers(config), json=payload, timeout=_TIMEOUT
    )
    if resp.status_code != 200:
        print(f"  ⚠️ Notion 페이지 생성 실패: {resp.status_code} {resp.text[:300]}")
        return False
    page_id = resp.json().get("id")
    if len(blocks) > 100 and page_id:
        return _append_children(config, page_id, blocks[100:])
    return True


def _append_to_page(config: Config, header: str, blocks: list[dict]) -> bool:
    # 섹션 구분용 구분선 + 헤더를 앞에 붙인다.
    section = [_divider(), _heading(header, level=2)] + blocks
    return _append_children(config, config.notion_page_id, section)


def check(config: Config) -> tuple[bool, str]:
    """연결 점검: 토큰 + 대상 DB/페이지 접근 확인 (통합 연결 여부 포함)."""
    try:
        if config.notion_database_id:
            resp = requests.get(
                f"{_BASE}/databases/{config.notion_database_id}",
                headers=_headers(config),
                timeout=_TIMEOUT,
            )
            target = "DB"
        elif config.notion_page_id:
            resp = requests.get(
                f"{_BASE}/pages/{config.notion_page_id}",
                headers=_headers(config),
                timeout=_TIMEOUT,
            )
            target = "페이지"
        else:
            return False, "DATABASE_ID/PAGE_ID 둘 다 없음"

        if resp.status_code == 200:
            return True, f"{target} 접근 OK"
        if resp.status_code in (401, 403):
            return False, f"인증 실패/권한 없음 ({resp.status_code}) — 통합을 대상에 'Connections'로 연결했는지 확인"
        if resp.status_code == 404:
            return False, f"대상을 찾을 수 없음(404) — ID 확인 또는 통합 미연결"
        return False, f"HTTP {resp.status_code} {resp.text[:150]}"
    except requests.RequestException as e:
        return False, str(e)


def export(config: Config, analyses: list[EmailAnalysis]) -> bool:
    """설정된 모드에 따라 Notion에 누적 저장한다."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"📬 메일 요약 — {now}"

    if config.notion_database_id:
        blocks = build_blocks(analyses, header=None)
        return _create_database_page(config, title, blocks)
    if config.notion_page_id:
        blocks = build_blocks(analyses, header=None)
        return _append_to_page(config, title, blocks)
    return False
