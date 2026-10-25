# US Stock Study Bot

한국어 Discord 학습 봇입니다. 28일 기초 코스와 별도로 계속 학습 트랙을 유지하고, RSS 경제·시장 뉴스, 개인별 퀴즈 기록과 취약 개념 복습을 제공합니다. 투자 매매를 권유하지 않습니다.

## 주요 기능

- Nasdaq·S&P 500·Dow Jones 및 거시경제·기업분석·NVIDIA·위험관리로 이어지는 28개 기초 학습
- 기초 코스는 28일차 이후 완료 상태를 유지하며 자동 재시작하지 않음. `/foundation_review`는 재시작 없이 복습
- 완료 후에도 작동하는 계속 학습 콘텐츠, 기사 RSS, 퀴즈 채점, 오답/취약 개념 복습
- SQLite 사용자별 데이터 분리와 기사 URL·내용 해시, 사용자·일자 브리핑 중복 방지
- 한국시간 등 설정한 시간대의 매일 브리핑 예약. 사용자 상호작용 이력이 있는 이용자에게 DM 시도
- 한 RSS·시세·일정 공급원이 실패해도 나머지 공급원과 봇 기능 계속 동작
- S&P 500, Nasdaq Composite, Dow Jones의 최근 종가와 직전 종가 대비 변동률
- BLS, BEA, 연준의 공식 일정에서 향후 14일 내 주요 발표 안내
- 선택형 OpenAI 기사 해설과 서술형 채점. AI 또는 네트워크 오류 시 기본 RSS 해설·로컬 채점으로 전환

## 요구사항 및 로컬 실행

Python 3.11 이상이 필요합니다. 의존성 범위는 `pyproject.toml`에 기록되어 있습니다 (`discord.py` 2.x, feedparser 6.x, APScheduler 3.x).

```bash
cd US-Stock-Study-Bot
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
cp .env.example .env
# .env에서 DISCORD_BOT_TOKEN을 설정
python main.py
```

테스트:

```bash
pytest
```

필수 환경변수는 `DISCORD_BOT_TOKEN`입니다. 나머지 지원 값은 `.env.example`을 참조하세요.

- `DISCORD_GUILD_ID`: 개발 중 명령어를 빠르게 동기화할 선택 값
- `DATABASE_PATH`: SQLite 파일 경로. 기본 `data/studybot.sqlite3`
- `TIMEZONE`: IANA 시간대. 기본 `Asia/Seoul`
- `DAILY_BRIEFING_TIME`: 현지 예약 시각. 기본 `08:00`
- `NEWS_MAX_ARTICLES`: RSS 최대 기사 수 (1~20)
- `AI_ENABLED`, `OPENAI_API_KEY`, `OPENAI_MODEL`: AI 기능을 쓸 때 설정합니다. AI를 선택했다면 `python -m pip install -e '.[ai]'`로 설치하고, `.env`에 `AI_ENABLED=true`와 본인이 발급한 API 키를 넣으세요. 기본 모델은 `gpt-5.5`입니다. API 키가 없거나 호출이 실패하면 로컬 채점과 RSS 해설로 돌아갑니다.

`.env`와 `data/`는 Git에서 제외됩니다. 운영에서 SQLite를 쓰면 `DATABASE_PATH`가 호스트의 영구 디스크 경로여야 합니다. 컨테이너 임시 파일시스템은 재배포 때 데이터가 없어질 수 있습니다. 정기 백업을 권장합니다.

## Discord 애플리케이션 설정

Discord 봇 토큰은 **각자 자기 봇 앱에서 발급**해야 합니다. 다른 사람은 저장소 코드를 복사해 자기 Discord 봇으로 실행합니다. 저장소 소유자의 토큰이나 OpenAI API 키를 받을 필요가 없습니다.

### 1) 각자의 Discord 봇 만들기

1. [Discord Developer Portal](https://discord.com/developers/applications)에서 **New Application**을 눌러 자기 앱을 만듭니다.
2. 왼쪽의 **Bot** 메뉴에서 봇을 추가하고 **Reset Token** 또는 **View Token**으로 토큰을 발급·복사합니다. 이 토큰은 비밀번호처럼 다루고 다른 사람에게 보내거나 GitHub에 올리지 마세요.
3. **OAuth2 → URL Generator**에서 `bot`과 `applications.commands`를 선택합니다. 권한은 최소한 `View Channels`, `Send Messages`, `Embed Links`를 선택하고, 생성된 링크를 열어 자기 Discord 서버에 봇을 초대합니다.
4. 여러 서버에 초대할 계획이라면 Developer Portal의 **Bot** 설정에서 공개 초대를 허용해야 합니다. 초대하는 사람은 해당 서버에서 봇을 추가할 권한이 있어야 합니다.

### 2) 코드 내려받고 키 입력하기 (macOS)

저장소 페이지에서 **Code → HTTPS** 주소를 복사한 뒤 터미널에서 실행합니다. `<저장소 주소>` 부분은 복사한 주소로 바꿉니다.

```bash
git clone <저장소 주소>
cd US-Stock-Study-Bot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[ai]'
cp .env.example .env
open -e .env
```

열린 `.env` 파일에서 자기 설정을 입력하고 저장합니다.

```dotenv
DISCORD_BOT_TOKEN=여기에_자기_Discord_봇_토큰
DISCORD_GUILD_ID=
AI_ENABLED=true
OPENAI_API_KEY=여기에_자기_OpenAI_API_키
```

OpenAI API 키는 [OpenAI API 플랫폼](https://platform.openai.com/api-keys)에서 각자 발급합니다. API 사용료는 각자의 OpenAI 계정에 청구됩니다. AI 기능을 사용하지 않으려면 `AI_ENABLED=false`로 두고 OpenAI 키를 비워도 봇의 기본 기능은 작동합니다.

`DISCORD_GUILD_ID`는 비워 두면 전역 슬래시 명령어를 동기화해 초대한 서버에서 사용할 수 있습니다. 개발 중 특정 서버에 빠르게 명령어를 등록하려는 경우에만 해당 서버 ID를 입력하세요.

### 3) 봇 실행하기

```bash
python main.py
```

터미널에 Discord 연결 완료 메시지가 나오면 실행 중입니다. Discord 서버에서 `/help`를 입력해 확인하세요. 이 방식은 터미널과 컴퓨터가 켜져 있는 동안 작동합니다. 컴퓨터를 꺼도 계속 실행하려면 각자 Render 같은 상시 실행 호스팅에 자기 봇 토큰과 필요한 API 키를 등록해야 합니다.

### 비밀 키 안전하게 보관하기

`.env`에는 봇 토큰과 API 키가 들어 있으므로 **GitHub에 올리지 마세요**. 이 저장소는 `.env`를 Git에서 제외하도록 설정되어 있습니다. 커밋 전에 `git status`를 확인하고 `.env`가 목록에 없는지 확인하세요. 키를 실수로 공개 저장소에 올렸다면 파일을 지우는 것만으로 끝나지 않으므로 Discord Developer Portal에서 봇 토큰을 재발급하고 OpenAI 키도 폐기한 뒤 새 키로 바꾸세요.

## 명령어

`/help`, `/briefing`, `/news`, `/article`, `/lesson`, `/quiz`, `/answer`, `/review`, `/progress`, `/foundation`, `/foundation_review`, `/weekly`, `/settings`

`/lesson`은 해당 일자 학습 기록을 남기고 다음 일차로 진도를 이동합니다. 같은 한국시간 날짜에 다시 호출해도 진도가 추가로 움직이지 않습니다. 28일차 이후에는 기초 진행 상태를 건드리지 않고 계속 학습 트랙의 콘텐츠를 기록합니다. `/quiz`는 한 번에 한 문제를 출제합니다. 첫 문제는 A/B/C/D 객관식이고 다음 두 문제는 짧은 서술형입니다. `/answer`에 답을 제출합니다. 현재 서술형 평가는 한국어 핵심어 일치 기반의 간단한 로컬 채점입니다.

## RSS·시장 데이터 한계

현재 뉴스 공급원은 Federal Reserve, BLS, CNBC 경제/기술, MarketWatch RSS입니다. 지수 종가는 FRED 일간 CSV 내보내기를 통해 가져옵니다. 이는 장중 실시간 수치가 아니며 공급 지연과 공급원 장애가 있을 수 있습니다. 각 지수별 실제 최근 거래 날짜를 표시하고, 값을 받지 못하면 수치를 꾸며내지 않고 오류를 표시합니다. 원자료인 S&P Dow Jones Indices LLC 및 Nasdaq, Inc.의 저작권 표시를 포함합니다. 이 피드는 개인 비상업 학습용으로만 사용하고 원자료의 이용 조건을 준수하세요.

향후 14일 일정은 BLS의 공식 ICS 일정, BEA의 기계 판독 JSON 일정, Federal Reserve의 FOMC 회의 일정을 가져옵니다. 공급원이 장애를 겪으면 나머지 일정은 표시하고 실패한 공급원을 알려줍니다. 날짜와 시각은 설정된 시간대로 변환합니다.

OpenAI가 켜져 있으면 기사 제목과 RSS 요약을 기준으로 중요성, 관련 업종, 가능한 시장 영향과 반대 조건, 학습 개념을 작성합니다. 기사 원문 전체를 읽는 방식이 아니므로 원문 링크로 확인해야 합니다. AI가 주식 매매를 권유하지 않도록 지시하고, API 오류 때는 기본 RSS 해설과 로컬 핵심어 채점으로 대체합니다. OpenAI API 사용에는 사용자의 별도 API 키와 계정 사용량/비용이 적용됩니다.

## Render Background Worker 배포

저장소 루트의 `render.yaml`에 Background Worker, Singapore 리전, SQLite 영구 디스크, 비밀값 입력 항목을 준비했습니다.

1. GitHub에 프로젝트 파일을 커밋하고 푸시합니다. `.env`는 `.gitignore`에서 제외되어야 하며, 절대 푸시하지 마세요.
2. Render에서 **New → Blueprint**를 선택하고 GitHub 저장소를 연결합니다.
3. Blueprint가 `DISCORD_BOT_TOKEN`과 `OPENAI_API_KEY`를 입력하라고 하면 Render 대시보드의 비밀 환경변수 칸에 입력합니다. 이 키들을 GitHub에 넣지 마세요.
4. Render가 생성할 Worker와 영구 디스크를 확인하고 서비스를 생성합니다. `render.yaml`은 `python main.py`를 실행하고 데이터베이스를 `/var/data/studybot.sqlite3`에 저장합니다.
5. 배포 로그에 Discord 연결 완료가 나오는지 확인합니다. 이후 맥을 꺼도 Worker가 계속 실행됩니다.

Render의 상시 Background Worker와 영구 디스크는 무료 플랜에서 제공되지 않습니다. 시작 Worker는 현재 가격표 기준 월 $7, 1GB 디스크는 월 $0.25로 약 $7.25/월이며 세금·추가 사용량은 별도일 수 있습니다. 가격 확인 후 Blueprint를 생성하세요. 같은 DB를 사용하는 Worker는 한 개만 유지합니다.

## GitHub Actions로 매일 수업 보내기 (무료/저비용 대안)

맥을 꺼도 매일 오전 8시(Asia/Seoul)에 Discord 채널로 게시하는 workflow가 `.github/workflows/daily-lesson.yml`에 있습니다. 설정한 시작일부터 28일 동안은 학습목표·설명·사례·시장 연결·혼동 주의, 퀴즈 3개와 정답/해설이 있는 수업을 보냅니다. 29일째부터는 매일 실제 RSS 뉴스, 최근 완료 거래일의 지수 종가, 확인 가능한 향후 경제 일정을 브리핑합니다. 이 뉴스 기능은 28일 코스와 독립적으로 계속 실행됩니다.

1. Discord 채널 설정에서 **연동 → 웹후크 → 새 웹후크**를 만들고 웹후크 URL을 복사합니다.
2. GitHub 저장소의 **Settings → Secrets and variables → Actions**에서 `DISCORD_WEBHOOK_URL` Secret을 만들고 URL을 값으로 저장합니다.
3. 같은 화면의 **Variables**에 `FOUNDATION_START_DATE`를 만들고 첫 수업 날짜를 `YYYY-MM-DD`로 설정합니다. 해당 날짜를 1일 차로 세어 28일간 기초 코스를 게시하고, 29일째부터는 뉴스 브리핑으로 자동 전환합니다.
4. 프로젝트를 기본 브랜치에 커밋/푸시합니다. GitHub의 **Actions** 탭에서 workflow가 활성화됐는지 확인합니다. `workflow_dispatch`로 수동 시험도 가능합니다.

이 대안은 Discord에서 slash command를 상시 받거나, 개인 답변을 저장·채점하는 기능은 제공하지 않습니다. 뉴스는 각 실행 때 RSS 등 공개 공급원에서 새로 가져오며, 공급원 장애 시 누락 또는 오류 표시가 생길 수 있습니다. GitHub 예약 실행은 혼잡 시 지연될 수 있습니다. 표준 runner는 공개 저장소에서 무료이고, 비공개 저장소의 GitHub Free 계정에는 월 2,000분이 포함됩니다. GitHub Actions는 테스트와 정기 작업에 적합하며, 지속 연결 봇 프로세스를 대신하지 않습니다.

프로세스 재시작 후 APScheduler는 다음 예정 시각에 다시 예약합니다. 과거 발송분을 자동으로 백필하지 않습니다. 사용자별 일자 중복 키로 중복 발송을 제한하며, Discord 전송 실패 시 해당 일자 예약은 제거되어 재시도 가능합니다. 여러 조각으로 나눈 메시지 도중 전송이 끊기면 일부 중복/누락 가능성이 있습니다.

## 개발 상태

SQLite 스키마는 기존 학습 기록을 지우지 않는 추가형 마이그레이션을 사용합니다. 외부 RSS·시세·일정·AI 호출은 테스트에서 모킹합니다. 시장 데이터는 일간 기준으로 장중 정보가 아니고, 개별 기업의 실적 발표 일정이나 모든 경제 일정을 망라하지 않습니다. BLS·BEA·Federal Reserve 일정은 공급원 갱신 지연이나 수정이 가능하므로 원문 일정도 확인하세요. Discord에서 개인별로 DM 구독이나 시간대를 변경하는 설정 UI는 아직 구현되지 않았습니다. 일일 브리핑 예약은 매일 동작하며, 미국 주말·휴장일에는 가장 최근에 확인된 지수 종가와 향후 일정을 안내합니다.
