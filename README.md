# 📬 Mailcalender — Gmail 자동 분류 · 요약 보고서 · 일정 제안

Gmail 메일을 가져와 **규칙 기반**으로 분류하고, 주요 메일을 **요약 보고서(Markdown)** 로 정리하며,
메일에서 날짜/시간을 찾아 **캘린더 일정(.ics)** 으로 제안합니다.

- ✅ **API 비용 0원** — Claude/OpenAI 등 외부 AI를 쓰지 않고 발신자·키워드 규칙과 정규식만 사용
- ✅ **PC 없이 자동 실행** — GitHub Actions(cron)로 클라우드에서 정해진 시각마다 무인 실행
- ✅ **텔레그램 알림** — 매일 결과(요약·일정)와 보고서/`.ics` 파일을 텔레그램으로 자동 전송
- ✅ **Notion 누적** — 매 실행 결과를 Notion DB(새 페이지) 또는 한 페이지에 계속 쌓아 기록
- ✅ **캘린더 안전** — 캘린더에 직접 쓰지 않고 `.ics` 로 '제안'만 (가져오기로 사용자가 등록)

> 규칙 기반은 무료·즉시 동작이 장점이고, 요약 품질은 AI 방식보다 단순합니다.
> 나중에 Claude API 등을 옵션으로 얹어 요약 품질을 높일 수 있는 구조입니다.

---

## 📂 구조

```
Mailcalender/
├── main.py                  # 전체 파이프라인 (가져오기→분석→보고서→ics)
├── config.py                # 환경설정 로드
├── requirements.txt
├── .env.example             # 설정 예시 (.env 로 복사해서 사용)
├── scripts/
│   └── get_token.py         # [1회용] Gmail 인증 → token.json 생성
├── src/
│   ├── gmail_client.py      # Gmail 읽기 (로컬/CI 인증 모두 지원)
│   ├── analyzer.py          # 규칙 기반 분류·중요도·요약·일정추출
│   ├── dateparse.py         # 날짜/시간 정규식 파서
│   ├── report.py            # Markdown 보고서 + 텔레그램 요약 생성
│   ├── calendar_ics.py      # .ics 캘린더 파일 생성
│   ├── notify_telegram.py   # 텔레그램 알림 전송
│   ├── notify_notion.py     # Notion 누적 저장
│   └── models.py            # 데이터 모델
└── .github/workflows/
    └── triage.yml           # GitHub Actions 자동 실행
```

---

## 🚀 로컬에서 실행하기

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. Google OAuth 자격증명 준비 (1회)
1. [Google Cloud Console](https://console.cloud.google.com/) → 프로젝트 생성
2. **APIs & Services → Library** 에서 **Gmail API** 사용 설정
3. **APIs & Services → Credentials → OAuth client ID → Desktop app** 생성
4. JSON 내려받아 프로젝트 폴더에 **`credentials.json`** 으로 저장
5. (테스트 단계라면) **OAuth consent screen → Test users** 에 본인 Gmail 추가

### 3. 인증 (1회)
```bash
python scripts/get_token.py
```
브라우저 로그인 후 `token.json` 이 생성됩니다.
(출력되는 한 줄은 GitHub Actions용 Secret 값이니 보관하세요.)

### 4. 연결 점검 (선택, 권장)
키를 `.env`에 넣은 뒤 Gmail·텔레그램·Notion 연결을 한 번에 확인:
```bash
python scripts/selftest.py          # 연결만 확인
python scripts/selftest.py --send   # 텔레그램 테스트 메시지까지 전송
```
각 항목이 `✅`(OK) / `⚠️`(경고) / `❌`(실패) / `⏭️`(미설정 건너뜀)로 표시됩니다.

### 5. 실행
```bash
cp .env.example .env   # 필요 시 쿼리/개수 수정
python main.py
```

결과:
- `output/report.md` — 요약 보고서 (분류 현황, 주요 메일, 액션 체크리스트, 일정 제안, 전체 목록)
- `output/events.ics` — 일정 제안 → 캘린더 앱에서 **가져오기**로 등록

---

## ☁️ PC 없이 자동 실행 (GitHub Actions)

1. 이 저장소를 본인 GitHub로 푸시
2. 로컬에서 `python scripts/get_token.py` 로 얻은 **token.json 한 줄 내용**을 복사
3. 저장소 **Settings → Secrets and variables → Actions → New repository secret**
   - 이름: `GMAIL_TOKEN`, 값: 복사한 token.json 내용
4. (선택) **Variables** 탭에서 `GMAIL_QUERY`, `MAX_EMAILS` 조정
5. 끝 — `.github/workflows/triage.yml` 의 cron 시각마다 자동 실행되어
   `output/report.md` 가 저장소에 자동 커밋되고, 실행 결과는 **Actions → Artifacts** 로도 받을 수 있습니다.

> 기본 cron 은 `0 23 * * *` (UTC) = **한국시간 매일 오전 8시**. 시각은 워크플로 파일에서 변경.
> **Actions 탭에서 "Run workflow"** 로 즉시 수동 실행도 가능합니다.

> ⚠️ `credentials.json`, `token.json`, `.env` 는 **절대 커밋하지 마세요** (`.gitignore` 에 이미 제외됨).
> 자격증명은 GitHub Secret 으로만 보관합니다.

---

## 📨 텔레그램 알림 설정 (선택)

매일 결과를 텔레그램으로 받아보려면:

1. 텔레그램에서 **@BotFather** 에게 `/newbot` → 봇 이름 정하면 **봇 토큰** 발급
2. 만든 봇과 **대화 시작**(아무 메시지나 전송)
3. 브라우저에서 `https://api.telegram.org/bot<봇토큰>/getUpdates` 접속 →
   결과 JSON 의 `"chat":{"id": ...}` 값이 **chat id**
4. 설정 등록
   - **로컬**: `.env` 에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 입력
   - **GitHub Actions**: 저장소 Secret 으로 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 등록

설정하면 실행 시 다음이 텔레그램으로 전송됩니다:
- 요약 메시지 (총계 · 주요 메일 · 액션 필요 · 일정 제안)
- `report.md` 전체 보고서 파일
- 일정이 있으면 `events.ics` 파일

> 두 값 중 하나라도 비어 있으면 알림은 자동으로 건너뜁니다.

---

## 🗂️ Notion 누적 저장 설정 (선택)

매 실행 결과를 Notion에 계속 쌓아둘 수 있습니다. **두 가지 모드** 중 하나를 고르세요.

| 모드 | 설정 변수 | 동작 |
|--|--|--|
| **DB 모드 (권장)** | `NOTION_DATABASE_ID` | 실행마다 DB에 **새 페이지(행)** 생성 → 일별 보고서가 목록으로 누적 |
| **페이지 모드** | `NOTION_PAGE_ID` | 지정한 **한 페이지 하단**에 매번 섹션 추가 → 한 페이지에 누적 |

설정 방법:
1. [notion.so/my-integrations](https://www.notion.so/my-integrations) → **New integration** 생성 → **Internal Integration Secret** 복사 = `NOTION_TOKEN`
2. Notion에서 대상 **데이터베이스(또는 페이지)** 를 열고 우측 상단 **`···` → Connections → 만든 통합 연결**
3. 대상 ID 확인 (URL에서):
   - 데이터베이스: `notion.so/<workspace>/<DATABASE_ID>?v=...` 의 `DATABASE_ID`
   - 페이지: `notion.so/<제목>-<PAGE_ID>` 의 끝 32자리 `PAGE_ID`
4. 설정 등록
   - **로컬**: `.env` 에 `NOTION_TOKEN` + (`NOTION_DATABASE_ID` 또는 `NOTION_PAGE_ID`)
   - **GitHub Actions**: 같은 이름으로 저장소 Secret 등록

> DB 모드를 쓰려면 데이터베이스에 **제목(title) 속성**만 있으면 됩니다(기본 'Name'). 속성 이름은 자동 감지합니다.
> `NOTION_TOKEN` 이 없거나 DB/PAGE ID가 둘 다 없으면 저장은 자동으로 건너뜁니다.

---

## ⚙️ 설정 (.env)

| 변수 | 설명 | 기본값 |
|--|--|--|
| `GMAIL_QUERY` | 가져올 메일 검색 (Gmail 검색 문법) | `is:unread newer_than:2d` |
| `MAX_EMAILS` | 한 번에 처리할 최대 메일 수 | `30` |
| `OUTPUT_DIR` | 보고서/ics 출력 폴더 | `output` |
| `TELEGRAM_BOT_TOKEN` | (선택) 텔레그램 봇 토큰 | _(없으면 알림 생략)_ |
| `TELEGRAM_CHAT_ID` | (선택) 텔레그램 채팅 ID | _(없으면 알림 생략)_ |
| `NOTION_TOKEN` | (선택) Notion 통합 시크릿 | _(없으면 저장 생략)_ |
| `NOTION_DATABASE_ID` | (선택) DB 모드 대상 DB | _(DB 모드)_ |
| `NOTION_PAGE_ID` | (선택) 페이지 모드 대상 페이지 | _(페이지 모드)_ |

검색 쿼리 예시: `in:inbox newer_than:1d`, `is:important newer_than:7d`, `from:boss@company.com`

---

## 🧠 규칙 기반 동작 방식

- **분류**: 제목·본문 키워드로 `보안/계정`, `결제/청구`, `회의/약속`, `예약/주문`, `뉴스레터/프로모션`, `개인/기타` 판정
- **중요도**: 긴급/마감 키워드, 액션 요청 키워드, 카테고리 가중치로 점수화 → 높음/보통/낮음
- **요약**: 인용·서명·링크를 제거하고 본문 앞부분 핵심 발췌
- **일정 추출**: `2026-06-30`, `6월 30일`, `내일`, `오후 3시`, `15:00`, `3pm` 등을 정규식으로 인식

키워드/규칙은 `src/analyzer.py` 상단에서 자유롭게 추가·수정할 수 있습니다.
