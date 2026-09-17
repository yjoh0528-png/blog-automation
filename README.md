# blog-automation

쿠팡 파트너스 / 오늘의집 큐레이터 / 네이버 쇼핑커넥트 제휴 링크를 활용한
실용 상품 리뷰 블로그 콘텐츠 자동 생성·발행 시스템.

## 설계 원칙

- **계정당 1개, 품질 우선**: 차단 회피용 다중 계정 자동화는 지원하지 않는다.
  일일 게시량은 "탐지 회피"가 아니라 "콘텐츠 품질/독자 경험" 기준으로
  `config/settings.yaml`의 `daily_post_cap`으로 설정한다.
- **제휴 사실 고지**: 모든 게시글 하단에 제휴 프로그램별 고지 문구를
  자동으로 삽입한다 (`src/blogauto/disclosure.py`). 문구를 숨기거나
  생략하지 않는다.
- **플랫폼별 발행 방식이 다르다**:
  - **Google Blogger**: 공식 Blogger API(OAuth2)로 완전 자동 발행.
  - **네이버 블로그 / 티스토리**: 공식 자동 포스팅 API가 없다. 로그인
    자동화(매크로)는 각 플랫폼 이용약관 위반 소지가 있어 구현하지 않았다.
    대신 `drafts/naver_blog/`, `drafts/tistory/`에 Markdown/HTML 초안을
    자동 생성하며, 사람이 검수 후 직접 게시한다.
- **과장광고 필터**: "100% 효과", "무조건", "완치" 등 표시광고법상
  문제될 수 있는 과장 표현을 QA 단계에서 자동 차단한다
  (`src/blogauto/policy.py`).
- **중복/스팸 방지**: 최근 N일(`duplicate_lookback_days`) 이내 다룬
  상품은 플랫폼을 가리지 않고 재사용하지 않는다.

## 아키텍처

```
config/settings.yaml        # 시드 키워드, 타겟 독자 매핑, 플랫폼별 일일 게시 한도
src/blogauto/
  models.py                 # Keyword / Product / Post 데이터 모델
  policy.py                 # 과장광고 금지어, 필수 소제목 구조
  disclosure.py             # 제휴 프로그램별 고지 문구
  config.py                 # 설정 로더 + 환경변수 헬퍼
  keyword_research/         # 네이버 데이터랩 API / 시드 폴백
  product_sources/          # 쿠팡 파트너스 / 네이버 쇼핑 / 오늘의집(CSV)
  content/                  # LLM 기반 본문 생성 (Claude API 또는 템플릿 폴백)
  qa/                       # 과장광고·필수 구조·중복·고지문구 검증 + 재시도 루프
  publishing/               # Blogger 완전 자동 발행 / 네이버·티스토리 초안 내보내기
  history/                  # 발행 이력(JSON) - 중복 방지, 일일 한도 체크
  orchestrator.py           # 전체 파이프라인 조립 및 실행
scripts/run_daily.py        # 매일 실행되는 엔트리포인트
.github/workflows/
  tests.yml                 # push/PR마다 테스트 실행
  daily-post.yml            # 매일 자동 실행 + 초안/이력 커밋
```

## 시작하기

```bash
pip install -r requirements.txt
cp .env.example .env   # 값 채워넣기
```

### 필요한 제휴/API 키

| 항목 | 용도 | 없을 때 동작 |
|---|---|---|
| `COUPANG_ACCESS_KEY` / `COUPANG_SECRET_KEY` | 쿠팡 파트너스 Open API | 쿠팡 상품 소스 건너뜀 |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 네이버 데이터랩(키워드) + 쇼핑검색 API | 시드 키워드 폴백 사용 |
| `NAVER_SHOPPING_AFFILIATE_LINK_TEMPLATE` | 쇼핑커넥트 딥링크 변환 (파트너센터에서 확인) | 원본 링크 그대로 사용 |
| `ANTHROPIC_API_KEY` | 본문 생성 (Claude) | 결정론적 템플릿 폴백 사용 |
| `BLOGGER_BLOG_ID` / `BLOGGER_CLIENT_ID` / `BLOGGER_CLIENT_SECRET` / `BLOGGER_REFRESH_TOKEN` | Google Blogger 자동 발행 | 구글 자동 발행 비활성화 |

오늘의집 큐레이터는 공개 Open API가 확인되지 않아, 큐레이터 대시보드에서
받은 CSV를 `data/ohouse_products.csv`로 저장해 사용한다
(`data/ohouse_products.csv.example` 참고).

### 실행

```bash
PYTHONPATH=src python3 scripts/run_daily.py
```

### 테스트

```bash
pip install -e ".[dev]"
pytest -q
```

## 네이버/티스토리 게시 워크플로

1. GitHub Actions가 매일 초안을 생성해 `drafts/naver_blog/`,
   `drafts/tistory/`에 저장하고 커밋한다.
2. 사람이 초안(Markdown 또는 HTML)을 검수한다 — 특히 제휴 고지 문구와
   과장 표현 여부.
3. 문제 없으면 네이버 블로그/티스토리 에디터에 붙여넣어 직접 게시한다.

이 흐름을 완전 자동화하려면 브라우저 로그인 자동화가 필요한데, 이는
각 플랫폼 이용약관을 위반할 소지가 있어 이 프로젝트에서는 의도적으로
구현하지 않았다.

## 법적 고지 관련 참고

- 표시광고법 및 공정거래위원회 "추천보증 등에 관한 표시광고 심사지침"에
  따라 대가성 콘텐츠임을 명확히 표시해야 한다.
- `src/blogauto/disclosure.py`의 문구는 각 제휴 프로그램의 최신 운영
  정책이 바뀌면 함께 갱신해야 한다. 실제 운영 전 각 파트너센터 공지사항을
  재확인할 것.
