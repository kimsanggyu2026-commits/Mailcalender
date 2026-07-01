"""텔레그램 봇으로 결과를 전송한다.

설정(둘 다 있어야 동작):
  - TELEGRAM_BOT_TOKEN : @BotFather 로 만든 봇 토큰
  - TELEGRAM_CHAT_ID    : 메시지를 받을 채팅 ID

둘 중 하나라도 없으면 조용히 건너뛴다(로컬에서 텔레그램 없이도 실행 가능).
"""
from __future__ import annotations

import os

import requests

from config import Config

_API = "https://api.telegram.org/bot{token}/{method}"
_TIMEOUT = 30


def is_configured(config: Config) -> bool:
    return bool(config.telegram_bot_token and config.telegram_chat_id)


def check(config: Config) -> tuple[bool, str]:
    """연결 점검: getMe 로 봇 토큰 유효성 확인."""
    url = _API.format(token=config.telegram_bot_token, method="getMe")
    try:
        resp = requests.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code} {resp.text[:150]}"
        name = resp.json().get("result", {}).get("username", "?")
        return True, f"봇 @{name} 연결 OK"
    except requests.RequestException as e:
        return False, str(e)


def send_message(config: Config, text: str, parse_mode: str = "HTML") -> bool:
    url = _API.format(token=config.telegram_bot_token, method="sendMessage")
    try:
        resp = requests.post(
            url,
            data={
                "chat_id": config.telegram_chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": "true",
            },
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            print(f"  ⚠️ 텔레그램 메시지 전송 실패: {resp.status_code} {resp.text[:200]}")
            return False
        return True
    except requests.RequestException as e:
        print(f"  ⚠️ 텔레그램 메시지 전송 오류: {e}")
        return False


def send_document(config: Config, path: str, caption: str = "") -> bool:
    if not os.path.exists(path):
        return False
    url = _API.format(token=config.telegram_bot_token, method="sendDocument")
    try:
        with open(path, "rb") as f:
            resp = requests.post(
                url,
                data={"chat_id": config.telegram_chat_id, "caption": caption[:1024]},
                files={"document": (os.path.basename(path), f)},
                timeout=_TIMEOUT,
            )
        if resp.status_code != 200:
            print(f"  ⚠️ 텔레그램 파일 전송 실패: {resp.status_code} {resp.text[:200]}")
            return False
        return True
    except requests.RequestException as e:
        print(f"  ⚠️ 텔레그램 파일 전송 오류: {e}")
        return False
