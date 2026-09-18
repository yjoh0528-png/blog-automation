from __future__ import annotations

import logging

from blogauto.config import Settings, env
from blogauto.content.generator import ContentGenerator
from blogauto.history.store import HistoryStore
from blogauto.models import Keyword, Post
from blogauto.orchestrator import (
    build_keyword_provider_from_env,
    build_llm_client_from_env,
    build_product_sources_from_env,
    generate_post_for_keywords,
)
from blogauto.research.naver_search import NaverNewsBlogResearch

logger = logging.getLogger(__name__)


class NoContentGeneratedError(Exception):
    pass


def _collect_source_articles(interest_area: str) -> list:
    """관심분야로 네이버 뉴스/블로그 검색 API를 조회해 참고 자료를 모은다.

    NAVER_CLIENT_ID/SECRET이 없으면 조용히 빈 목록을 반환한다 (글감 발굴은
    선택 기능이지 필수 기능이 아니다).
    """
    client_id = env("NAVER_CLIENT_ID")
    client_secret = env("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.warning(
            "NAVER_CLIENT_ID/SECRET 미설정 - 관심분야 글감 수집을 건너뜁니다."
        )
        return []

    research = NaverNewsBlogResearch(client_id, client_secret)
    articles = research.search_news(interest_area, display=5)
    articles += research.search_blogs(interest_area, display=5)
    return articles


def generate_one_post(
    settings: Settings,
    history: HistoryStore,
    keyword_term: str | None = None,
    interest_area: str | None = None,
) -> Post:
    """대시보드의 "생성" 버튼에서 호출: 글 한 편을 만들어 반환한다.

    keyword_term이 주어지면 기존 시드 키워드 방식(정확히 일치하는 키워드
    우선, 없으면 그 문자열 자체를 키워드로 사용). interest_area가 주어지면
    네이버 뉴스/블로그 검색 API로 글감 자료를 모아 콘텐츠 생성에 참고자료로
    넘기고, 상품 매칭 키워드로도 사용한다. 둘 다 없으면 설정 파일의
    seed_keywords를 순서대로 시도한다.

    Orchestrator.run_daily()와 동일한 파이프라인(키워드 리서치 -> 상품 매칭
    -> 콘텐츠 생성 -> QA 재시도)을 공유하되, 발행은 하지 않는다.
    """
    keyword_provider = build_keyword_provider_from_env()
    product_sources = build_product_sources_from_env(settings)
    generator = ContentGenerator(build_llm_client_from_env())

    source_articles: list = []
    if interest_area:
        keywords = [Keyword(term=interest_area)]
        source_articles = _collect_source_articles(interest_area)
    else:
        keywords = keyword_provider.suggest(settings.seed_keywords, limit=20)
        if keyword_term:
            matched = [k for k in keywords if k.term == keyword_term]
            keywords = matched or [Keyword(term=keyword_term)]

    if not keywords:
        raise NoContentGeneratedError("사용 가능한 키워드가 없습니다.")

    recent_ids = history.recent_product_ids(settings.duplicate_lookback_days)
    post = generate_post_for_keywords(
        generator,
        product_sources,
        keywords,
        settings.target_audience_map,
        recent_ids,
        source_articles=source_articles or None,
    )
    if post is None:
        raise NoContentGeneratedError("사용 가능한 키워드/상품 조합을 찾지 못했습니다.")
    return post
