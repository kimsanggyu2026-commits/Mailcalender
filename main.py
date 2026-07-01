"""메일 확인 → 규칙 기반 분류·요약 → 보고서 + 일정(.ics) 생성.

로컬:  python main.py
CI:    GMAIL_TOKEN 환경변수(Secret)로 무인 실행
"""
from __future__ import annotations

import os
from datetime import datetime

from config import load_config
from src.analyzer import analyze_all
from src.calendar_ics import write_ics
from src.gmail_client import fetch_emails
from src.report import build_report, build_telegram_summary
from src import notify_telegram, notify_notion


def main() -> None:
    config = load_config()
    os.makedirs(config.output_dir, exist_ok=True)

    print(f"[1/4] Gmail에서 메일 가져오는 중...  (쿼리: {config.gmail_query})")
    emails = fetch_emails(config)
    print(f"      → {len(emails)}통 수신")

    if not emails:
        print("처리할 메일이 없습니다. GMAIL_QUERY 를 확인하세요.")
        return

    print("[2/4] 규칙 기반 분류·요약·일정 추출 중...")
    analyses = analyze_all(emails)

    print("[3/4] 요약 보고서 작성 중...")
    report = build_report(analyses)
    report_path = os.path.join(config.output_dir, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    # 최신본과 함께, 날짜별 보관본도 남긴다.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = os.path.join(config.output_dir, f"report_{stamp}.md")
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(report)

    print("[4/4] 일정 제안(.ics) 생성 중...")
    events = [ev for a in analyses for ev in a.events]
    ics_path = os.path.join(config.output_dir, "events.ics")
    write_ics(events, ics_path)

    # 텔레그램 알림 (설정된 경우에만)
    if notify_telegram.is_configured(config):
        print("[+] 텔레그램으로 결과 전송 중...")
        summary = build_telegram_summary(analyses)
        if notify_telegram.send_message(config, summary):
            notify_telegram.send_document(config, report_path, caption="📄 전체 요약 보고서")
            if events:
                notify_telegram.send_document(
                    config, ics_path, caption="🗓️ 일정 제안 (캘린더에서 가져오기)"
                )
            print("      → 전송 완료")
    else:
        print("[i] 텔레그램 미설정 (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID) → 알림 건너뜀")

    # Notion 누적 저장 (설정된 경우에만)
    if notify_notion.is_configured(config):
        mode = "DB(새 페이지)" if config.notion_database_id else "페이지(이어쓰기)"
        print(f"[+] Notion에 누적 저장 중... ({mode})")
        if notify_notion.export(config, analyses):
            print("      → 저장 완료")
    else:
        print("[i] Notion 미설정 (NOTION_TOKEN + DATABASE_ID/PAGE_ID) → 저장 건너뜀")

    print("\n완료 ✅")
    print(f"  - 보고서:      {report_path}")
    print(f"  - 보관본:      {archive_path}")
    print(f"  - 일정 제안:   {ics_path}  ({len(events)}건)")
    print("\n캘린더 앱에서 events.ics 를 '가져오기'하면 일정 후보를 한 번에 등록할 수 있습니다.")


if __name__ == "__main__":
    main()
