from __future__ import annotations

import re

import requests

from .models import SourceArticle

_NEWS_ENDPOINT = "https://openapi.naver.com/v1/search/news.json"
_BLOG_ENDPOINT = "https://openapi.naver.com/v1/search/blog.json"


class NaverNewsBlogResearch:
    """네이버 뉴스검색/블로그검색 API(공식)로 글감 참고 자료를 수집한다.

    화면 스크래핑이 아니라 공식 Open API를 쓰므로 안정적이고 약관 리스크가
    낮다. 쇼핑검색/데이터랩과 같은 NAVER_CLIENT_ID/SECRET 자격증명을 쓴다.
    """

    def __init__(self, client_id: str, client_secret: str, timeout: float = 10.0):
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout

    def search_news(self, query: str, display: int = 10) -> list[SourceArticle]:
        return self._search(_NEWS_ENDPOINT, query, display, "news")

    def search_blogs(self, query: str, display: int = 10) -> list[SourceArticle]:
        return self._search(_BLOG_ENDPOINT, query, display, "blog")

    def _search(
        self, endpoint: str, query: str, display: int, source_type: str
    ) -> list[SourceArticle]:
        response = requests.get(
            endpoint,
            params={"query": query, "display": display, "sort": "sim"},
            headers={
                "X-Naver-Client-Id": self._client_id,
                "X-Naver-Client-Secret": self._client_secret,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()

        return [
            SourceArticle(
                title=_strip_html(item.get("title", "")),
                description=_strip_html(item.get("description", "")),
                link=item.get("link", ""),
                source_type=source_type,
            )
            for item in payload.get("items", [])
        ]


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)
