"""환경 설정 로드."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Gmail 읽기 전용 스코프. 일정은 보고서에 '제안'만 하므로 캘린더 쓰기 권한은 요구하지 않는다.
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


@dataclass(frozen=True)
class Config:
    max_emails: int
    gmail_query: str
    output_dir: str
    credentials_file: str
    token_file: str
    telegram_bot_token: str
    telegram_chat_id: str
    notion_token: str
    notion_database_id: str
    notion_page_id: str


def load_config() -> Config:
    return Config(
        max_emails=int(os.getenv("MAX_EMAILS", "30")),
        gmail_query=os.getenv("GMAIL_QUERY", "is:unread newer_than:2d").strip(),
        output_dir=os.getenv("OUTPUT_DIR", "output").strip(),
        credentials_file=os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json").strip(),
        token_file=os.getenv("GOOGLE_TOKEN_FILE", "token.json").strip(),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        notion_token=os.getenv("NOTION_TOKEN", "").strip(),
        notion_database_id=os.getenv("NOTION_DATABASE_ID", "").strip(),
        notion_page_id=os.getenv("NOTION_PAGE_ID", "").strip(),
    )
