from __future__ import annotations

import logging

from .checks import run_checks
from ..content.generator import ContentGenerationError, ContentGenerator
from ..models import Keyword, Post, Product
from ..research.models import SourceArticle

logger = logging.getLogger(__name__)


class QAFailedError(Exception):
    pass


def generate_with_verification(
    generator: ContentGenerator,
    keyword: Keyword,
    product: Product,
    target_audience: str,
    recent_product_ids: set[str],
    max_attempts: int = 3,
    source_articles: list[SourceArticle] | None = None,
) -> Post:
    """콘텐츠를 생성하고 QA 체크를 통과할 때까지 재시도한다."""
    last_errors: list[str] = []
    for attempt in range(1, max_attempts + 1):
        try:
            post = generator.generate(keyword, product, target_audience, source_articles)
        except ContentGenerationError as exc:
            last_errors = [str(exc)]
            logger.warning("콘텐츠 생성 실패 (시도 %d/%d): %s", attempt, max_attempts, exc)
            continue

        result = run_checks(post, recent_product_ids)
        if result.passed:
            return post
        last_errors = result.errors
        logger.warning("QA 실패 (시도 %d/%d): %s", attempt, max_attempts, result.errors)

    raise QAFailedError(f"{max_attempts}회 시도 후에도 QA 통과 실패: {last_errors}")
