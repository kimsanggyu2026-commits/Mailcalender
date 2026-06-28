"""Gmail 읽기 전용 클라이언트."""
from __future__ import annotations

import base64
import json
import os
from email.utils import parsedate_to_datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import GMAIL_SCOPES, Config
from src.models import EmailMessage


def _load_creds_from_env() -> Credentials | None:
    """CI(GitHub Actions)용: token.json 내용을 GMAIL_TOKEN 환경변수로 받는다.

    브라우저가 없는 서버 환경에서는 대화형 로그인을 할 수 없으므로,
    로컬에서 1회 만든 token.json 내용을 Secret으로 주입한다.
    """
    raw = os.getenv("GMAIL_TOKEN", "").strip()
    if not raw:
        return None
    info = json.loads(raw)
    return Credentials.from_authorized_user_info(info, GMAIL_SCOPES)


def _authenticate(config: Config):
    """OAuth 흐름.

    우선순위:
      1) GMAIL_TOKEN 환경변수 (CI/서버, 무인 실행)
      2) token.json 파일 (로컬 재사용)
      3) 최초 1회 브라우저 인증 (로컬)
    """
    creds = _load_creds_from_env()

    if creds is None and os.path.exists(config.token_file):
        creds = Credentials.from_authorized_user_file(config.token_file, GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif os.getenv("GMAIL_TOKEN"):
            # CI인데 토큰이 만료/무효 → refresh 토큰까지 있어야 한다.
            raise SystemExit(
                "GMAIL_TOKEN 으로 인증할 수 없습니다. 로컬에서 token.json 을 다시 생성해 "
                "Secret을 갱신하세요 (refresh_token 포함 여부 확인)."
            )
        else:
            if not os.path.exists(config.credentials_file):
                raise SystemExit(
                    f"'{config.credentials_file}' 파일이 없습니다. "
                    "Google Cloud Console에서 OAuth 클라이언트(데스크톱) 자격증명을 "
                    "내려받아 이 이름으로 저장하세요. (README 참고)"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                config.credentials_file, GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(config.token_file, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return creds


def _decode_part(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")


def _extract_body(payload: dict) -> str:
    """multipart 메일 본문에서 text/plain 우선, 없으면 text/html을 추출."""
    plain: str | None = None
    html: str | None = None

    def walk(part: dict) -> None:
        nonlocal plain, html
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")
        if data:
            if mime == "text/plain" and plain is None:
                plain = _decode_part(data)
            elif mime == "text/html" and html is None:
                html = _decode_part(data)
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)

    if plain:
        return plain
    if html:
        return _strip_html(html)
    return ""


def _strip_html(html: str) -> str:
    """아주 가벼운 HTML 제거 (외부 의존성 없이)."""
    import re

    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    # HTML 엔티티 일부 복원
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"')):
        text = text.replace(a, b)
    return text


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _parse_sender(raw: str) -> tuple[str, str]:
    """'홍길동 <a@b.com>' -> ('홍길동', 'a@b.com')."""
    from email.utils import parseaddr

    name, addr = parseaddr(raw)
    return (name or addr or raw, addr.lower())


def fetch_emails(config: Config) -> list[EmailMessage]:
    """검색 쿼리에 맞는 메일을 최대 max_emails개 가져온다."""
    creds = _authenticate(config)
    service = build("gmail", "v1", credentials=creds)

    listing = (
        service.users()
        .messages()
        .list(userId="me", q=config.gmail_query, maxResults=config.max_emails)
        .execute()
    )
    message_refs = listing.get("messages", [])

    results: list[EmailMessage] = []
    for ref in message_refs:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=ref["id"], format="full")
            .execute()
        )
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])

        sender_name, sender_email = _parse_sender(_header(headers, "From"))
        date_raw = _header(headers, "Date")
        try:
            date = parsedate_to_datetime(date_raw) if date_raw else None
        except (TypeError, ValueError):
            date = None

        results.append(
            EmailMessage(
                id=msg["id"],
                thread_id=msg.get("threadId", ""),
                sender=sender_name,
                sender_email=sender_email,
                subject=_header(headers, "Subject") or "(제목 없음)",
                date=date,
                snippet=msg.get("snippet", ""),
                body=_extract_body(payload),
            )
        )

    return results
