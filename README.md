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
- **네이버 게시 자동화는 사용자가 직접 녹화한 스크립트로**: 네이버
  스마트에디터의 DOM은 계정·시점에 따라 다를 수 있어, 이 프로젝트가
  셀렉터를 하드코딩하지 않는다. 대신 `playwright codegen`으로 사용자가
  본인 세션 기준 1회 녹화한 스크립트를 재생하는 방식을 쓴다 (아래
  "네이버 게시 스크립트 녹화" 절 참고).
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
  product_sources/           # 쿠팡 파트너스 / 네이버 쇼핑 / 오늘의집(CSV)
  content/llm.py             # LLM 백엔드: claude -p CLI / Anthropic API / 템플릿
  content/generator.py       # 소제목 구조를 강제하는 본문 생성기
  qa/                        # 과장광고·필수 구조·중복·고지문구 검증 + 재시도 루프
  publishing/                # Blogger 완전 자동 발행 / 네이버·티스토리 초안 내보내기
  history/                   # 발행 이력(JSON) - 중복 방지, 일일 한도, 최소 간격 체크
  orchestrator.py            # 파이프라인 조립 (Orchestrator, 재사용 가능한 빌더 함수들)
dashboard/
  app.py                     # Flask 대시보드 (로그인 상태, 생성, 게시)
  sites.py                   # config/sites.yaml 로더
  generate.py                # 대시보드용 단건 생성 헬퍼 (orchestrator 파이프라인 재사용)
  pending_posts.py           # 생성된 초안을 로컬 JSON으로 관리
  templates/index.html
scripts/
  run_daily.py                # (선택) Blogger 등 완전 자동 발행 채널용 수동 실행 스크립트
  browser_login.py            # 범용 Playwright 로그인 세션 캡처
  replay_post.py              # 사용자가 녹화한 네이버 게시 스크립트 실행기
  recorded/naver_post.py      # (직접 생성) playwright codegen으로 녹화한 스크립트
data/
  sessions/                   # 로그인 세션(쿠키) - git에 절대 커밋되지 않음
  pending_posts/              # 생성된 초안(JSON)
.github/workflows/
  tests.yml                   # push/PR마다 테스트 실행 (클라우드 자동 발행 워크플로 없음)
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
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 네이버 데이터랩(키워드) + 쇼핑검색 API | 시드 키워드 폴백 사용 |
| `NAVER_SHOPPING_AFFILIATE_LINK_TEMPLATE` | 쇼핑커넥트 딥링크 변환 (파트너센터에서 확인) | 원본 링크 그대로 사용 |
| `BLOGGER_BLOG_ID` / `BLOGGER_CLIENT_ID` / `BLOGGER_CLIENT_SECRET` / `BLOGGER_REFRESH_TOKEN` | Google Blogger 자동 발행 (`scripts/run_daily.py`용) | 구글 자동 발행 비활성화 |

오늘의집 큐레이터는 공개 Open API가 확인되지 않아, 큐레이터 대시보드에서
받은 CSV를 `data/ohouse_products.csv`로 저장해 사용한다
(`data/ohouse_products.csv.example` 참고).

### Playwright 설치

```bash
pip install playwright
playwright install chromium
```

(`pip install -r requirements.txt`에 `playwright` 패키지는 포함되어 있지만,
브라우저 바이너리는 `playwright install`을 한 번 더 실행해야 받아진다.)

### 대시보드 실행

```bash
PYTHONPATH=src python3 -m dashboard.app
```

브라우저에서 `http://127.0.0.1:5000`을 연다. 화면에서:

1. 네이버 블로그(및 필요하면 쿠팡 파트너스/오늘의집/네이버 브랜드 커넥트)
   "로그인" 버튼을 누른다 — Playwright 창이 뜨면 평소처럼 직접 로그인한 뒤,
   화면 우측 상단의 "로그인 완료 - 세션 저장" 버튼을 누른다.
2. 키워드를 입력하고(비워두면 자동 추천) "생성"을 누른다.
3. 생성된 글을 검토한다.
4. "게시"를 누른다 — `dry_run`이 기본값(`true`)이라 실제로는 올라가지 않고
   상태만 `dry_run`으로 바뀐다. 실제 게시를 원하면 아래 순서를 따른다.

### 네이버 게시 스크립트 녹화 (실제 게시를 원할 때)

이 프로젝트는 네이버 에디터의 셀렉터를 하드코딩하지 않는다 — 대신 사용자가
1회 녹화한 스크립트를 재생한다.

1. 네이버 로그인을 대시보드에서 먼저 완료해 `data/sessions/naver_blog.json`을
   만든다.
2. 아래 명령으로 녹화를 시작한다 (실제 글쓰기 페이지에서 제목/본문 입력,
   발행까지 원하는 동작을 그대로 수행하면 된다):
   ```bash
   playwright codegen --load-storage=data/sessions/naver_blog.json \
     https://blog.naver.com/<본인아이디>?Redirect=Write
   ```
3. 녹화가 끝나면 생성된 Python 스크립트를 `scripts/recorded/naver_post.py`로
   저장한다.
4. 스크립트에서 **제목을 입력했던 자리**를 `os.environ["BLOGAUTO_TITLE"]`로,
   **본문을 입력했던 자리**를 `os.environ["BLOGAUTO_CONTENT"]`로 바꾼다
   (파일 상단에 `import os` 추가). 예:
   ```python
   # 녹화된 그대로 (예시)
   page.fill("#title-input", "테스트 제목")
   # ↓ 이렇게 수정
   page.fill("#title-input", os.environ["BLOGAUTO_TITLE"])
   ```
5. `config/settings.yaml`에서 `dry_run: false`로 바꾼다.
6. 대시보드에서 다시 "게시"를 누르면 이 스크립트가 실행되어 실제로 게시된다.

**처음에는 반드시 비공개 테스트 글로 확인하고, 발행 후 실제 글 주소를 열어
서식이 제대로 들어갔는지 직접 확인할 것.** 이 저장소를 만든 환경에서는
네이버 로그인 페이지에 실제 네트워크로 접근할 수 없어(샌드박스 네트워크
제한), 이 흐름 전체를 실사용 환경에서 직접 검증한 적이 없다.

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
