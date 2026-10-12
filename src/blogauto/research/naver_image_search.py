from __future__ import annotations

import re

import requests

from .models import ImageCandidate

_ENDPOINT = "https://openapi.naver.com/v1/search/image"


class NaverImageSearch:
    """네이버 이미지검색 API(공식)로 본문 대표 이미지 후보를 모은다.

    화면 스크래핑이 아니라 공식 Open API지만, 검색 결과 이미지는 각
    웹사이트의 저작물이라 저작권이 네이버나 이 프로젝트에 있지 않다.
    그래서 제휴 상품의 공식 이미지를 1순위 후보로 항상 포함하고, 검색
    결과는 "AI가 더 잘 맞는 사진을 고르기 위한 추가 후보"로만 쓴다.
    최종 발행 전 사람이 스크린샷으로 이미지를 직접 확인하는 체크포인트가
    있으니, 상업적 재배포가 꺼려지는 이미지라면 그 단계에서 걸러야 한다.
    """

    def __init__(self, client_id: str, client_secret: str, timeout: float = 10.0):
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout

    def search(self, query: str, display: int = 5) -> list[ImageCandidate]:
        response = requests.get(
            _ENDPOINT,
            params={"query": query, "display": display, "sort": "sim", "filter": "medium"},
            headers={
                "X-Naver-Client-Id": self._client_id,
                "X-Naver-Client-Secret": self._client_secret,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()

        candidates = []
        for item in payload.get("items", []):
            link = item.get("link", "")
            if not link:
                continue
            candidates.append(
                ImageCandidate(
                    url=link,
                    title=_strip_html(item.get("title", "")),
                    width=int(item["sizewidth"]) if item.get("sizewidth") else None,
                    height=int(item["sizeheight"]) if item.get("sizeheight") else None,
                )
            )
        return candidates


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)
