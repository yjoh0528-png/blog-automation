from __future__ import annotations

import re

import requests

from .base import ProductSource as ProductSourceProtocol
from ..models import Product, ProductSource

_ENDPOINT = "https://openapi.naver.com/v1/search/shop.json"


class NaverShoppingSource(ProductSourceProtocol):
    """네이버 쇼핑검색 API (공식) 기반 상품 소스.

    쇼핑커넥트의 실제 제휴 딥링크 변환 방식은 파트너센터 대시보드에서 확인해야
    하므로, 여기서는 `affiliate_link_template` ("{url}" 플레이스홀더 포함 문자열)을
    설정으로 주입받는 방식을 사용한다. 템플릿이 없으면 원본 링크를 그대로 사용한다.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        affiliate_link_template: str | None = None,
        timeout: float = 10.0,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._affiliate_link_template = affiliate_link_template
        self._timeout = timeout

    def search(self, keyword: str, limit: int = 10) -> list[Product]:
        response = requests.get(
            _ENDPOINT,
            params={"query": keyword, "display": limit, "sort": "sim"},
            headers={
                "X-Naver-Client-Id": self._client_id,
                "X-Naver-Client-Secret": self._client_secret,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()

        products = []
        for item in payload.get("items", []):
            title = _strip_html(item.get("title", ""))
            link = item.get("link", "")
            products.append(
                Product(
                    source=ProductSource.NAVER_SHOPPING_CONNECT,
                    product_id=item.get("productId", title),
                    title=title,
                    original_url=link,
                    affiliate_url=self._to_affiliate_link(link),
                    price=int(item["lprice"]) if item.get("lprice") else None,
                    image_url=item.get("image"),
                    category=item.get("category1"),
                )
            )
        return products

    def _to_affiliate_link(self, url: str) -> str:
        if not self._affiliate_link_template or not url:
            return url
        return self._affiliate_link_template.format(url=url)


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)
