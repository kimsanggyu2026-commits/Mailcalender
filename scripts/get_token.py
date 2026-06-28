"""[1회용] 로컬에서 Gmail OAuth 인증 → token.json 생성 + Secret용 출력.

사용법:
  1) Google Cloud Console에서 OAuth 클라이언트(데스크톱)를 만들고
     credentials.json 으로 저장 (이 폴더에 둠).
  2) python scripts/get_token.py 실행 → 브라우저 로그인.
  3) 생성된 token.json 의 '한 줄 내용'이 출력됨.
     → GitHub 저장소 Settings > Secrets > Actions 에
        GMAIL_TOKEN 이라는 이름으로 그 값을 붙여넣으면 무인 실행 준비 완료.
"""
from __future__ import annotations

import os
import sys

# 프로젝트 루트를 import 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google_auth_oauthlib.flow import InstalledAppFlow

from config import GMAIL_SCOPES, load_config


def main() -> None:
    config = load_config()
    if not os.path.exists(config.credentials_file):
        raise SystemExit(
            f"'{config.credentials_file}' 가 없습니다. "
            "Google Cloud Console에서 OAuth 클라이언트(데스크톱) JSON을 내려받아 "
            "이 이름으로 저장하세요."
        )

    flow = InstalledAppFlow.from_client_secrets_file(config.credentials_file, GMAIL_SCOPES)
    creds = flow.run_local_server(port=0)

    with open(config.token_file, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    print(f"\n✅ {config.token_file} 생성 완료 (로컬 실행용).")
    print("\n── GitHub Actions(무인 실행)용 ──")
    print("아래 한 줄을 그대로 복사해 GMAIL_TOKEN Secret 으로 등록하세요:\n")
    print(creds.to_json())


if __name__ == "__main__":
    main()
