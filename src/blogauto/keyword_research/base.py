from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Keyword


class KeywordResearchProvider(ABC):
    @abstractmethod
    def suggest(self, seeds: list[str], limit: int = 20) -> list[Keyword]:
        """시드 키워드를 바탕으로 점수화된 추천 키워드 목록을 반환한다."""
