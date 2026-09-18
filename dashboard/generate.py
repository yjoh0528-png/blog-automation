from __future__ import annotations

from blogauto.config import Settings
from blogauto.content.generator import ContentGenerator
from blogauto.history.store import HistoryStore
from blogauto.models import Keyword, Post
from blogauto.orchestrator import (
    build_keyword_provider_from_env,
    build_llm_client_from_env,
    build_product_sources_from_env,
    generate_post_for_keywords,
)


class NoContentGeneratedError(Exception):
    pass


def generate_one_post(
    settings: Settings, history: HistoryStore, keyword_term: str | None = None
) -> Post:
    """대시보드의 "생성" 버튼에서 호출: 키워드 하나에 대한 글을 만들어 반환한다.

    Orchestrator.run_daily()와 동일한 파이프라인(키워드 리서치 -> 상품 매칭
    -> 콘텐츠 생성 -> QA 재시도)을 공유하되, 발행은 하지 않는다.
    """
    keyword_provider = build_keyword_provider_from_env()
    product_sources = build_product_sources_from_env(settings)
    generator = ContentGenerator(build_llm_client_from_env())

    keywords = keyword_provider.suggest(settings.seed_keywords, limit=20)
    if keyword_term:
        matched = [k for k in keywords if k.term == keyword_term]
        keywords = matched or [Keyword(term=keyword_term)]
    if not keywords:
        raise NoContentGeneratedError("사용 가능한 키워드가 없습니다.")

    recent_ids = history.recent_product_ids(settings.duplicate_lookback_days)
    post = generate_post_for_keywords(
        generator, product_sources, keywords, settings.target_audience_map, recent_ids
    )
    if post is None:
        raise NoContentGeneratedError("사용 가능한 키워드/상품 조합을 찾지 못했습니다.")
    return post
