from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Product


class ProductSource(ABC):
    @abstractmethod
    def search(self, keyword: str, limit: int = 10) -> list[Product]:
        """키워드에 맞는 상품 목록을 반환한다."""
