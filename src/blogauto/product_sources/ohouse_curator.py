from __future__ import annotations

import csv
from pathlib import Path

from .base import ProductSource as ProductSourceProtocol
from ..models import Product, ProductSource


class OhouseCuratorCsvSource(ProductSourceProtocol):
    """오늘의집 큐레이터 상품 소스.

    오늘의집 큐레이터는 일반 개발자용 공개 Open API가 확인되지 않으므로,
    큐레이터 대시보드에서 내려받은 CSV(title, url, affiliate_url, price,
    image_url, category, product_id 컬럼)를 입력으로 받는 방식으로 구현한다.
    추후 공식 API가 제공되면 동일한 ProductSource 인터페이스로 교체하면 된다.
    """

    def __init__(self, csv_path: str | Path):
        self._csv_path = Path(csv_path)

    def search(self, keyword: str, limit: int = 10) -> list[Product]:
        if not self._csv_path.exists():
            return []
        products: list[Product] = []
        with self._csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get("title", "")
                if keyword and keyword not in title:
                    continue
                products.append(
                    Product(
                        source=ProductSource.OHOUSE_CURATOR,
                        product_id=row.get("product_id") or title,
                        title=title,
                        original_url=row.get("url", ""),
                        affiliate_url=row.get("affiliate_url") or row.get("url", ""),
                        price=int(row["price"]) if row.get("price") else None,
                        image_url=row.get("image_url"),
                        category=row.get("category"),
                    )
                )
                if len(products) >= limit:
                    break
        return products
