from __future__ import annotations

from datetime import date, timedelta

import requests

from .base import KeywordResearchProvider
from ..models import Keyword

_ENDPOINT = "https://openapi.naver.com/v1/datalab/search"
_MAX_GROUPS = 5  # 네이버 데이터랩 API 제한: keywordGroups 최대 5개


class NaverDataLabProvider(KeywordResearchProvider):
    """네이버 데이터랩 검색어 트렌드 API (공식) 기반 키워드 추천.

    https://developers.naver.com/docs/serviceapi/datalab/search/search.md
    """

    def __init__(self, client_id: str, client_secret: str, timeout: float = 10.0):
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout

    def suggest(self, seeds: list[str], limit: int = 20) -> list[Keyword]:
        if not seeds:
            return []
        groups = [{"groupName": term, "keywords": [term]} for term in seeds[:_MAX_GROUPS]]
        payload = {
            "startDate": self._one_month_ago(),
            "endDate": self._today(),
            "timeUnit": "date",
            "keywordGroups": groups,
        }
        response = requests.post(
            _ENDPOINT,
            json=payload,
            headers={
                "X-Naver-Client-Id": self._client_id,
                "X-Naver-Client-Secret": self._client_secret,
                "Content-Type": "application/json",
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()

        keywords: list[Keyword] = []
        for result in data.get("results", []):
            values = result.get("data", [])
            avg_ratio = sum(p["ratio"] for p in values) / len(values) if values else 0.0
            keywords.append(Keyword(term=result["title"], score=avg_ratio))
        keywords.sort(key=lambda k: k.score, reverse=True)
        return keywords[:limit]

    @staticmethod
    def _today() -> str:
        return date.today().isoformat()

    @staticmethod
    def _one_month_ago() -> str:
        return (date.today() - timedelta(days=30)).isoformat()
