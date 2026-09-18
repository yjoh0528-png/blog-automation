from __future__ import annotations

import logging

from .config import Settings, env
from .content.generator import ContentGenerator
from .content.llm import (
    AnthropicLLMClient,
    ClaudePrintModeLLMClient,
    LLMClient,
    TemplateLLMClient,
)
from .history.store import HistoryStore
from .keyword_research.base import KeywordResearchProvider
from .keyword_research.naver_datalab import NaverDataLabProvider
from .keyword_research.seed_provider import SeedKeywordProvider
from .models import Keyword, Platform, Post, Product
from .product_sources.base import ProductSource as ProductSourceProtocol
from .product_sources.coupang_partners import CoupangPartnersSource
from .product_sources.naver_shopping import NaverShoppingSource
from .product_sources.ohouse_curator import OhouseCuratorCsvSource
from .publishing.base import Publisher
from .publishing.draft_export import DraftExportPublisher
from .qa.pipeline import QAFailedError, generate_with_verification

logger = logging.getLogger(__name__)

_PLATFORM_MAP: dict[str, Platform] = {
    "google_blogger": Platform.GOOGLE_BLOGGER,
    "naver_blog": Platform.NAVER_BLOG,
    "tistory": Platform.TISTORY,
}


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        keyword_provider: KeywordResearchProvider,
        product_sources: list[ProductSourceProtocol],
        generator: ContentGenerator,
        publishers: dict[Platform, Publisher],
        history: HistoryStore,
    ):
        self._settings = settings
        self._keyword_provider = keyword_provider
        self._product_sources = product_sources
        self._generator = generator
        self._publishers = publishers
        self._history = history

    def run_daily(self) -> list[str]:
        results: list[str] = []
        keywords = self._keyword_provider.suggest(self._settings.seed_keywords, limit=20)
        if not keywords:
            logger.warning("추천 키워드가 없어 이번 실행을 건너뜁니다.")
            return results

        for platform_name, cfg in self._settings.platforms.items():
            platform = _PLATFORM_MAP.get(platform_name)
            if platform is None or not cfg.enabled:
                continue
            publisher = self._publishers.get(platform)
            if publisher is None:
                logger.warning("'%s' 발행기가 설정되지 않아 건너뜁니다.", platform_name)
                continue

            already_today = self._history.count_today(platform)
            remaining = max(cfg.daily_post_cap - already_today, 0)
            for _ in range(remaining):
                post_url = self._run_one(platform, publisher, keywords)
                if post_url:
                    results.append(post_url)
        return results

    def _run_one(
        self, platform: Platform, publisher: Publisher, keywords: list[Keyword]
    ) -> str | None:
        recent_ids = self._history.recent_product_ids(self._settings.duplicate_lookback_days)
        post = generate_post_for_keywords(
            self._generator,
            self._product_sources,
            keywords,
            self._settings.target_audience_map,
            recent_ids,
        )
        if post is None:
            logger.warning(
                "[%s] 사용 가능한 키워드/상품 조합을 찾지 못했습니다.", platform.value
            )
            return None

        url = publisher.publish(post)
        self._history.record(platform, post.product.product_id, post.title)
        logger.info("[%s] 게시 완료: %s", platform.value, url)
        return url


def find_unused_product(
    product_sources: list[ProductSourceProtocol], keyword_term: str, recent_ids: set[str]
) -> Product | None:
    for source in product_sources:
        for product in source.search(keyword_term, limit=5):
            if product.product_id not in recent_ids:
                return product
    return None


def generate_post_for_keywords(
    generator: ContentGenerator,
    product_sources: list[ProductSourceProtocol],
    keywords: list[Keyword],
    target_audience_map: dict[str, str],
    recent_ids: set[str],
) -> Post | None:
    """주어진 키워드들을 순서대로 시도해, QA를 통과하는 첫 게시물을 생성해 반환한다.

    Orchestrator의 자동 발행 루프와 대시보드의 수동 "생성" 버튼이 모두
    이 함수를 공유한다.
    """
    for keyword in keywords:
        product = find_unused_product(product_sources, keyword.term, recent_ids)
        if product is None:
            continue
        target_audience = target_audience_map.get(keyword.term, "실용적인 선물을 찾는 분")
        try:
            return generate_with_verification(
                generator, keyword, product, target_audience, recent_ids
            )
        except QAFailedError as exc:
            logger.error("QA 통과 실패, 다음 키워드로 넘어갑니다: %s", exc)
            continue
    return None


def build_keyword_provider_from_env() -> KeywordResearchProvider:
    naver_client_id = env("NAVER_CLIENT_ID")
    naver_client_secret = env("NAVER_CLIENT_SECRET")
    if naver_client_id and naver_client_secret:
        return NaverDataLabProvider(naver_client_id, naver_client_secret)
    logger.warning("NAVER_CLIENT_ID/SECRET 미설정 - 시드 키워드 폴백을 사용합니다.")
    return SeedKeywordProvider()


def build_product_sources_from_env(settings: Settings) -> list[ProductSourceProtocol]:
    product_sources: list[ProductSourceProtocol] = []

    coupang_access = env("COUPANG_ACCESS_KEY")
    coupang_secret = env("COUPANG_SECRET_KEY")
    if coupang_access and coupang_secret:
        product_sources.append(CoupangPartnersSource(coupang_access, coupang_secret))
    else:
        logger.warning("COUPANG_ACCESS_KEY/SECRET_KEY 미설정 - 쿠팡 상품 소스를 건너뜁니다.")

    naver_client_id = env("NAVER_CLIENT_ID")
    naver_client_secret = env("NAVER_CLIENT_SECRET")
    if naver_client_id and naver_client_secret:
        product_sources.append(
            NaverShoppingSource(
                naver_client_id,
                naver_client_secret,
                affiliate_link_template=env("NAVER_SHOPPING_AFFILIATE_LINK_TEMPLATE"),
            )
        )

    product_sources.append(OhouseCuratorCsvSource(settings.ohouse_csv_path))
    return product_sources


def build_llm_client_from_env() -> LLMClient:
    """LLM_BACKEND 환경변수로 콘텐츠 생성 백엔드를 선택한다.

    기본값은 claude_print - 로컬에 로그인된 Claude 구독(Pro/Max) 세션을
    쓰는 `claude -p` CLI 헤드리스 모드다. API 키 과금이 필요 없다.
    """
    backend = env("LLM_BACKEND", "claude_print")
    if backend == "claude_print":
        return ClaudePrintModeLLMClient(model=env("CLAUDE_MODEL", "sonnet"))
    if backend == "anthropic_api":
        anthropic_key = env("ANTHROPIC_API_KEY", required=True)
        return AnthropicLLMClient(anthropic_key)
    if backend == "template":
        return TemplateLLMClient()
    raise RuntimeError(
        f"알 수 없는 LLM_BACKEND 값: {backend!r} (claude_print|anthropic_api|template 중 하나)"
    )


def build_orchestrator_from_env(settings_path: str = "config/settings.yaml") -> Orchestrator:
    """환경변수/설정 파일로부터 실제 운영용 Orchestrator를 조립한다."""
    settings = Settings.load(settings_path)

    keyword_provider = build_keyword_provider_from_env()
    product_sources = build_product_sources_from_env(settings)
    generator = ContentGenerator(build_llm_client_from_env())
    history = HistoryStore(settings.history_path)

    publishers: dict[Platform, Publisher] = {}
    blogger_blog_id = env("BLOGGER_BLOG_ID")
    if blogger_blog_id:
        from .publishing.blogger import BloggerPublisher
        from .publishing.blogger_auth import load_blogger_credentials

        publishers[Platform.GOOGLE_BLOGGER] = BloggerPublisher(
            blogger_blog_id, load_blogger_credentials()
        )
    else:
        logger.warning("BLOGGER_BLOG_ID 미설정 - 구글 Blogger 자동 발행을 건너뜁니다.")

    publishers[Platform.NAVER_BLOG] = DraftExportPublisher(
        f"{settings.draft_output_dir}/naver_blog", "네이버 블로그"
    )
    publishers[Platform.TISTORY] = DraftExportPublisher(
        f"{settings.draft_output_dir}/tistory", "티스토리"
    )

    return Orchestrator(settings, keyword_provider, product_sources, generator, publishers, history)
