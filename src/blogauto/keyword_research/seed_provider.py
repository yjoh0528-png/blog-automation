from __future__ import annotations

from .base import KeywordResearchProvider
from ..models import Keyword


class SeedKeywordProvider(KeywordResearchProvider):
    """외부 API 키가 없을 때 사용하는 폴백: 설정 파일의 시드 키워드를 그대로 점수화한다."""

    def suggest(self, seeds: list[str], limit: int = 20) -> list[Keyword]:
        scored = [
            Keyword(term=term, score=float(len(seeds) - idx)) for idx, term in enumerate(seeds)
        ]
        return scored[:limit]
