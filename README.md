# blog-automation

쿠팡 파트너스 / 오늘의집 큐레이터 / 네이버 쇼핑커넥트 제휴 링크를 활용한
실용 상품 리뷰 블로그 콘텐츠 자동 생성·발행 시스템. **사용자 본인의 PC에서
직접 실행하는 로컬 대시보드**로 동작한다 (클라우드 무인 자동화 아님).

## 설계 원칙

- **로컬 실행, 사람이 매 건 트리거**: 클라우드에서 무인으로 반복 게시하지
  않는다. 대시보드에서 사람이 "생성", "게시" 버튼을 직접 눌러야 동작한다.
  일일 게시량도 "탐지 회피"가 아니라 "콘텐츠 품질/독자 경험 + 실수 방지"
  기준으로 `config/settings.yaml`의 `daily_post_cap`/`min_publish_interval_min`으로
  설정한다.
- **발행 안전장치가 기본값**: `dry_run: true`가 기본값이라, 처음 설정한
  상태로는 "게시"를 눌러도 실제로 올라가지 않는다. 실제 게시를 원하면
  `config/settings.yaml`에서 명시적으로 `dry_run: false`로 바꿔야 한다.
  `kill_switch`로 전체 발행을 즉시 차단할 수 있다.
- **제휴 사실 고지**: 모든 게시글 하단에 제휴 프로그램별 고지 문구를
  자동으로 삽입한다 (`src/blogauto/disclosure.py`). 문구를 숨기거나
  생략하지 않는다.
- **로그인은 사람이 직접, 자동화는 세션 재사용만**: 대시보드의 "로그인"
  버튼을 누르면 Playwright가 실제 브라우저 창을 띄우고, **사람이 직접**
  아이디/비밀번호를 입력해 로그인한다. 자격증명을 코드가 대신 입력하지
  않는다. 로그인 완료 버튼을 누르면 그 세션(쿠키)만 로컬에 저장해 재사용한다.
- **네이버 게시 자동화는 "안정적 신호 우선 + 막히면 사람에게 넘김"**:
  네이버 스마트에디터의 정확한 DOM(CSS 클래스명 등)은 이 프로젝트를 만든
  환경에서 라이브로 검증할 수 없었다. 그래서 자동입력 로직은 빌드마다
  바뀔 수 있는 클래스명이 아니라 **버튼 텍스트/접근성 role처럼 비교적
  안정적인 신호**로 요소를 찾고(`dashboard/naver_automation/locators.py`),
  브라우저 창은 항상 사람이 볼 수 있게 띄워두며, 어떤 단계든 확신 있게
  다음 동작을 결정하지 못하면 **자동화를 멈추고 대시보드에서 사람이 직접
  이어받게** 한다. 실제 "발행" 버튼은 자동 입력이 끝난 뒤 항상 사람이
  스크린샷을 보고 확인한 다음에만 눌린다.
- **과장광고 필터**: "100% 효과", "무조건", "완치" 등 표시광고법상
  문제될 수 있는 과장 표현을 QA 단계에서 자동 차단한다
  (`src/blogauto/policy.py`).
- **중복 방지**: 최근 N일(`duplicate_lookback_days`) 이내 다룬 상품은
  플랫폼을 가리지 않고 재사용하지 않는다.
- **네이버 자동 게시의 법적 주의사항**: 브라우저 자동화로 실제 글을
  게시하는 것은 네이버 이용약관상 "자동화된 접근"에 해당해 계정 제재
  위험이 있을 수 있다. 이 프로젝트는 그 위험을 사용자 본인의 단일 계정에
  대한 사용자 본인의 선택으로 남겨두며, 대신 `dry_run`/`kill_switch`/
  일일 한도/최소 발행 간격 같은 안전장치를 기본으로 제공한다.

## 아키텍처

```
config/
  settings.yaml              # 키워드, 타겟 독자, 일일 게시 한도, 발행 안전장치
  sites.yaml                 # 로그인 대상 사이트 목록(라벨 + 로그인 URL)
src/blogauto/
  models.py                  # Keyword / Product / Post 데이터 모델
  policy.py                  # 과장광고 금지어, 필수 소제목 구조
  disclosure.py              # 제휴 프로그램별 고지 문구
  config.py                  # 설정 로더 + 환경변수 헬퍼
  keyword_research/          # 네이버 데이터랩 API / 시드 폴백
  research/                  # 네이버 뉴스·블로그 검색(글감) + 이미지검색(이미지 후보) API
  product_sources/           # 쿠팡 파트너스 / 네이버 쇼핑 / 오늘의집(CSV)
  content/llm.py             # LLM 백엔드: claude -p CLI / Anthropic API / 템플릿 (+비전 입력)
  content/generator.py       # 소제목 구조를 강제하고 참고자료를 반영하는 본문 생성기
  content/image_picker.py    # 여러 이미지 후보 중 AI가 글 맥락에 맞는 것을 고르는 로직
  qa/                        # 과장광고·필수 구조·중복·고지문구 검증 + 재시도 루프
  publishing/                # Blogger 완전 자동 발행 / 티스토리 초안 내보내기
  history/                   # 발행 이력(JSON) - 중복 방지, 일일 한도, 최소 간격 체크
  orchestrator.py            # 파이프라인 조립 (Orchestrator, 재사용 가능한 빌더 함수들)
dashboard/
  app.py                     # Flask 대시보드 (로그인, 생성, 자동 편집·발행 제어)
  sites.py                   # config/sites.yaml 로더
  generate.py                # 대시보드용 단건 생성 헬퍼 (관심분야/키워드 입력 처리)
  pending_posts.py           # 생성된 초안을 로컬 JSON으로 관리
  playwright_setup.py        # Playwright/Chromium 준비 여부 확인 + 자동 설치
  naver_automation/
    locators.py               # 텍스트/role 기반 "안정적 신호 우선" 요소 탐색 헬퍼
  templates/index.html
scripts/
  run_daily.py                 # (선택) Blogger 등 완전 자동 발행 채널용 수동 실행 스크립트
  browser_login.py             # 범용 Playwright 로그인 세션 캡처
  naver_auto_publish.py        # 네이버 에디터 자동 입력 + 사람 확인 후 발행 (막히면 일시정지)
data/
  sessions/                    # 로그인 세션(쿠키) - git에 절대 커밋되지 않음
  pending_posts/               # 생성된 초안(JSON) + <id>.control/ 진행상태·스크린샷
.github/workflows/
  tests.yml                    # push/PR마다 테스트 실행 (클라우드 자동 발행 워크플로 없음)
```

## 시작하기

```bash
pip install -e ".[dev]"          # 또는: pip install -r requirements.txt
cp .env.example .env             # 값 채워넣기
```

### 콘텐츠 생성 백엔드 (`LLM_BACKEND`)

| 값 | 설명 | 비용 |
|---|---|---|
| `claude_print` (기본값) | 로컬에 로그인된 Claude Code CLI(`claude -p`)를 사용. `claude` 명령이 설치되어 있고 로그인되어 있어야 한다 (`claude auth login` 또는 `claude`로 최초 실행 시 로그인). | Pro/Max **구독** 사용량 |
| `anthropic_api` | `ANTHROPIC_API_KEY`로 Anthropic Messages API 직접 호출. | **API 종량 과금** |
| `template` | 오프라인/테스트용 결정론적 템플릿. | 무료 |

`claude_print`는 로컬에서 사용자 본인이 직접 실행하는 용도로만 쓸 것 —
Anthropic 정책상 구독 OAuth 세션은 무인 클라우드 자동화(예: CI에서 매일
자동 실행) 용도가 아니다. 이 프로젝트가 GitHub Actions 자동 발행 워크플로를
두지 않고 로컬 대시보드로 만든 이유이기도 하다.

### 필요한 제휴/API 키

| 항목 | 용도 | 없을 때 동작 |
|---|---|---|
| `COUPANG_ACCESS_KEY` / `COUPANG_SECRET_KEY` | 쿠팡 파트너스 Open API | 쿠팡 상품 소스 건너뜀 |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 네이버 데이터랩(키워드) + 쇼핑검색 + 뉴스/블로그 검색(글감 발굴) + 이미지검색(대표 이미지 후보) API | 시드 키워드 폴백 사용, 관심분야 글감 수집·이미지 후보 검색 건너뜀 |
| `NAVER_SHOPPING_AFFILIATE_LINK_TEMPLATE` | 쇼핑커넥트 딥링크 변환 (파트너센터에서 확인) | 원본 링크 그대로 사용 |
| `BLOGGER_BLOG_ID` / `BLOGGER_CLIENT_ID` / `BLOGGER_CLIENT_SECRET` / `BLOGGER_REFRESH_TOKEN` | Google Blogger 자동 발행 (`scripts/run_daily.py`용) | 구글 자동 발행 비활성화 |

오늘의집 큐레이터는 공개 Open API가 확인되지 않아, 큐레이터 대시보드에서
받은 CSV를 `data/ohouse_products.csv`로 저장해 사용한다
(`data/ohouse_products.csv.example` 참고).

### Playwright 설치

대시보드를 `python3 -m dashboard.app`으로 직접 실행하면, 시작 시점에
Playwright 패키지/Chromium이 없는지 자동으로 확인하고 없으면
`pip install playwright && playwright install chromium`을 **자동으로
실행**한다(`dashboard/playwright_setup.py`). 네트워크 제한 등으로 자동
설치가 실패해도 대시보드 자체는 계속 켜진 채로 유지되며, 홈 화면에
경고 배너가 뜨고 로그인/자동 게시 버튼만 동작하지 않는다. 그럴 때는
아래를 수동으로 실행한 뒤 대시보드를 재시작하면 된다.

```bash
pip install playwright
playwright install chromium
```

### 대시보드 실행

```bash
PYTHONPATH=src python3 -m dashboard.app
```

브라우저에서 `http://127.0.0.1:5000`을 연다. `config/settings.yaml`에
**`naver_blog_id`**(네이버 블로그 아이디)를 먼저 채워둔다 — 글쓰기 URL을
조립하는 데 필요하다.

1. **네이버 블로그** "로그인" 버튼을 누른다 — Playwright 창이 뜨면 평소처럼
   직접 로그인한 뒤(가능하면 "로그인 상태 유지" 체크), 화면 우측 상단의
   "로그인 완료 - 세션 저장" 버튼을 누른다. 쿠팡 파트너스/오늘의집/네이버
   브랜드 커넥트도 같은 방식으로 로그인해둘 수 있다(현재는 세션 저장까지만
   지원).
2. **관심분야**를 입력하고(예: "거북목", "홈카페") "생성"을 누른다 —
   `NAVER_CLIENT_ID`/`SECRET`이 설정되어 있으면 네이버 뉴스·블로그 검색
   API로 관련 글감을 모아 AI가 참고자료로 활용한다. 관심분야 대신 기존
   방식대로 "키워드"를 직접 지정하거나 둘 다 비워 설정 파일의 시드
   키워드를 쓸 수도 있다.
3. 생성된 글(제목/소제목 구조/상품 공식 이미지)을 검토한다.
4. "게시"를 누른다.
   - `dry_run: true`(기본값)면 자동 편집이 시작되지 않고 상태만 `dry_run`으로
     표시된다.
   - `dry_run: false`면 브라우저가 열리고 제목·본문·상품 이미지를 **자동으로**
     입력한다. 이 과정에서 어떤 요소를 확신 있게 찾지 못하면 자동화가
     **"막힘" 상태로 멈추고**, 브라우저에서 직접 그 단계를 처리한 뒤
     대시보드의 [계속]을 누르면 이어서 진행된다.
   - 입력이 끝나면 **스크린샷과 함께 "발행 확인 대기"** 상태가 된다. 내용을
     확인하고 [확인했습니다 - 실제 발행]을 눌러야만 실제로 네이버에
     게시된다. [취소]를 누르면 발행하지 않고 브라우저만 닫힌다.

**처음에는 반드시 비공개 테스트 글로 확인할 것.** 이 저장소를 만든 환경은
네이버 로그인 페이지/에디터에 실제 네트워크로 접근할 수 없어(샌드박스
네트워크 제한), 자동 입력 로직(`scripts/naver_auto_publish.py`,
`dashboard/naver_automation/locators.py`)의 요소 탐색 문구는 **라이브
검증 없이 작성된 최선의 추정치**다. 안정적 신호(버튼 텍스트/role) 우선 +
막히면 사람에게 넘기는 방식으로 설계했지만, 첫 실행에서는 여러 단계가
"막힘"으로 넘어갈 수 있다. 그때마다 브라우저에서 직접 이어가면 되고,
자주 막히는 단계가 있다면 `dashboard/naver_automation/locators.py`의
후보 문구를 실제 화면에 맞게 추가/수정하면 된다.

### (선택) Google Blogger 완전 자동 발행

Google Blogger는 공식 OAuth2 API로 완전 자동 발행이 가능해, 로그인 세션
재사용 없이도 `scripts/run_daily.py`로 바로 실행할 수 있다.

```bash
PYTHONPATH=src python3 scripts/run_daily.py
```

네이버/티스토리는 이 스크립트에서 여전히 `drafts/naver_blog/`,
`drafts/tistory/`에 초안만 생성한다 — 대시보드의 실제 게시 경로를 쓰려면
위 대시보드 절차를 따를 것.

### 테스트

```bash
pip install -e ".[dev]"
pytest -q
```

## 법적 고지 관련 참고

- 표시광고법 및 공정거래위원회 "추천보증 등에 관한 표시광고 심사지침"에
  따라 대가성 콘텐츠임을 명확히 표시해야 한다.
- `src/blogauto/disclosure.py`의 문구는 각 제휴 프로그램의 최신 운영
  정책이 바뀌면 함께 갱신해야 한다. 실제 운영 전 각 파트너센터 공지사항을
  재확인할 것.
- `config/sites.yaml`의 `login_url` 값들은 확인되지 않은 참고용 기본값이다.
  실제 로그인 페이지로 바로 연결되지 않으면 직접 수정할 것.

## 이미지 선택 방식

- **후보 1: 제휴 프로그램이 API로 공식 제공하는 상품 이미지** (`Product.image_url`) -
  항상 최우선 후보로 포함된다.
- **후보 2 (선택): 네이버 이미지검색 API** (`NAVER_CLIENT_ID/SECRET` 설정 시,
  `상품명 + 키워드`로 검색) - `src/blogauto/research/naver_image_search.py`.
  화면 스크래핑이 아니라 공식 Open API지만, 검색 결과 이미지는 각
  웹사이트의 저작물이지 네이버나 이 프로젝트의 소유가 아니다. 상업적
  재배포 소지가 걱정되는 이미지가 섞일 수 있으니, 발행 전 사람이 스크린샷
  미리보기로 이미지를 직접 확인하는 기존 체크포인트에서 함께 확인할 것.
- 후보가 2개 이상이면 `src/blogauto/content/image_picker.py`가 후보들을
  로컬로 내려받아 LLM(`claude -p` 등)에게 **직접 보여주고** 글 주제에
  가장 잘 맞는 사진을 고르게 한다. 다운로드/판단 중 하나라도 실패하면
  조용히 폴백하며(공식 이미지 우선) 전체 생성 파이프라인을 막지 않는다.
  후보가 1개뿐이면(이미지검색 미설정 등) AI 판단 없이 그대로 쓴다.
- `NAVER_CLIENT_ID/SECRET`이 없으면 이미지검색 후보 수집을 건너뛰어
  기존처럼 공식 상품 이미지 하나만 쓴다(완전히 하위 호환).

## 이번 버전의 스코프 축소 (알아두면 좋은 것)

- **인라인 서식(형광펜 강조 등)은 자동 입력에서 생략된다.** contenteditable
  안에서 정확한 부분 문자열을 선택해 색을 입히는 동작은 가장 깨지기 쉬운
  부분이라, 소제목/문단/이미지 삽입까지만 자동화했다.
- **글감 발굴은 네이버 뉴스/블로그 검색 API의 제목+요약만 사용한다.**
  원문 전체를 가져오지 않고, AI에게 "그대로 베끼지 말고 트렌드만
  참고하라"고 명시적으로 지시한다.
