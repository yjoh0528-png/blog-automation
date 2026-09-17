from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

import requests

from .base import ProductSource as ProductSourceProtocol
from ..models import Product, ProductSource

_DOMAIN = "https://api-gateway.coupang.com"
_SEARCH_PATH = "/v2/providers/affiliate_open_api/apis/openapi/v1/products/search"


class CoupangPartnersSource(ProductSourceProtocol):
    """쿠팡 파트너스 Open API 어댑터.

    인증은 쿠팡이 공개한 HMAC 서명 스펙(HmacSHA256)을 따른다. 쿠팡 측 스펙은
    개정될 수 있으므로, 실제 연동 전 파트너스 개발자센터 최신 문서로
    서명 로직을 재확인할 것.
    """

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        sub_id: str | None = None,
        timeout: float = 10.0,
    ):
        self._access_key = access_key
        self._secret_key = secret_key
        self._sub_id = sub_id
        self._timeout = timeout

    def search(self, keyword: str, limit: int = 10) -> list[Product]:
        params = {"keyword": keyword, "limit": limit}
        if self._sub_id:
            params["subId"] = self._sub_id
        query = urlencode(params)
        headers = self._auth_headers("GET", _SEARCH_PATH, query)
        response = requests.get(
            f"{_DOMAIN}{_SEARCH_PATH}?{query}",
            headers=headers,
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()

        products = []
        for item in payload.get("data", {}).get("productData", []):
            products.append(
                Product(
                    source=ProductSource.COUPANG_PARTNERS,
                    product_id=str(item.get("productId")),
                    title=item.get("productName", ""),
                    original_url=item.get("productUrl", ""),
                    affiliate_url=item.get("productUrl", ""),
                    price=item.get("productPrice"),
                    image_url=item.get("productImage"),
                    category=item.get("categoryName"),
                )
            )
        return products

    def _auth_headers(self, method: str, path: str, query: str) -> dict[str, str]:
        signed_date = time.strftime("%y%m%dT%H%M%SZ", time.gmtime())
        message = signed_date + method + path + query
        signature = hmac.new(
            self._secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        authorization = (
            f"CEA algorithm=HmacSHA256, access-key={self._access_key}, "
            f"signed-date={signed_date}, signature={signature}"
        )
        return {"Authorization": authorization, "Content-Type": "application/json"}
