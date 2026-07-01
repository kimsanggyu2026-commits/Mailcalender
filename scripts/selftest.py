"""연결 점검(self-test): Gmail · 텔레그램 · Notion 연결을 한 번에 진단.

사용법:
  python scripts/selftest.py            # 연결만 확인
  python scripts/selftest.py --send     # 텔레그램에 테스트 메시지도 전송

키/설정을 .env (또는 환경변수)에 넣은 뒤 실행하면, 각 항목의 연결 상태를
✅/⚠️/❌ 로 보여줍니다. 미설정 항목은 건너뜁니다.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import load_config
from src import notify_notion, notify_telegram

OK = "✅"
WARN = "⚠️"
SKIP = "⏭️ "
FAIL = "❌"


def _check_gmail(config) -> bool:
    print("\n[Gmail]")
    try:
        from src.gmail_client import get_profile

        profile = get_profile(config)
        email = profile.get("emailAddress", "?")
        total = profile.get("messagesTotal", "?")
        print(f"  {OK} 연결 OK — {email} (총 {total}통)")
        return True
    except SystemExit as e:
        print(f"  {FAIL} {e}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"  {FAIL} 인증/연결 실패: {e}")
        return False


def _check_telegram(config, send: bool) -> bool:
    print("\n[Telegram]")
    if not notify_telegram.is_configured(config):
        print(f"  {SKIP}미설정 (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")
        return True
    ok, msg = notify_telegram.check(config)
    print(f"  {OK if ok else FAIL} {msg}")
    if ok and send:
        sent = notify_telegram.send_message(config, "✅ Mailcalender 연결 테스트 메시지입니다.")
        print(f"  {OK if sent else WARN} 테스트 메시지 전송 {'성공' if sent else '실패'}")
    return ok


def _check_notion(config) -> bool:
    print("\n[Notion]")
    if not notify_notion.is_configured(config):
        print(f"  {SKIP}미설정 (NOTION_TOKEN + DATABASE_ID/PAGE_ID)")
        return True
    ok, msg = notify_notion.check(config)
    print(f"  {OK if ok else FAIL} {msg}")
    return ok


def main() -> None:
    send = "--send" in sys.argv
    config = load_config()

    print("=" * 48)
    print(" Mailcalender 연결 점검")
    print("=" * 48)

    results = [
        _check_gmail(config),
        _check_telegram(config, send),
        _check_notion(config),
    ]

    print("\n" + "=" * 48)
    if all(results):
        print(f" {OK} 모든 점검 통과 — `python main.py` 실행 준비 완료")
    else:
        print(f" {FAIL} 일부 점검 실패 — 위 메시지를 확인하세요")
    print("=" * 48)
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
